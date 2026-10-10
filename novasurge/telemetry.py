"""
Telemetry: turns Prometheus + Kubernetes state into per-service feature vectors.

Features (per service, per 5s tick)
  request_rate        req/s served           (notification-service: events consumed/s)
  error_rate          5xx / total            (notification-service: malformed events ratio)
  p99_latency_ms      server-side p99        (notification-service: event handling p99)
  inflight            concurrent requests
  cpu_cores           CPU per pod            (cAdvisor)
  cpu_throttle_ratio  CFS throttled periods / periods
  memory_mb           working set per pod
  caller_error_rate   failures seen by *callers* of this service (gateway: by users)
  caller_p99_ms       p99 seen by callers                         (gateway: by users)

The caller-side view matters: a partitioned or crashed service cannot report on
itself (its scrape fails), but its callers still observe the failures.

Structural state (replicas, readiness, scrape health, restarts) comes from the
Kubernetes API and Prometheus `up`, and feeds the rule-based detectors.

Missing data is never replaced with invented "typical" values: absent request
series mean zero traffic, absent latency means "unknown" and is reported as
such so the detector can treat it neutrally while other signals carry it.
"""

from __future__ import annotations

import json
import logging
import math
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Protocol

import httpx

from novasurge import config
from novasurge.topology import SERVICES

log = logging.getLogger("novasurge.telemetry")

FEATURES: list[str] = [
    "request_rate",
    "error_rate",
    "p99_latency_ms",
    "inflight",
    "cpu_cores",
    "cpu_throttle_ratio",
    "memory_mb",
    "caller_error_rate",
    "caller_p99_ms",
]

_NS = f'namespace="{config.NAMESPACE}"'
_W = config.RATE_WINDOW
# cAdvisor refreshes idle containers only every ~10-15s, so a 30s window can hold a
# single sample; CPU/throttling rates use a 1m window to stay defined.
_CW = "1m"
_HTTP = f'{_NS},service!="notification-service"'
_POD_TO_SERVICE = '"service", "$1", "pod", "(.+)-[a-z0-9]+-[a-z0-9]+"'
_CONTAINER = f'{_NS},container!=""'
_FAILED = 'status_code=~"5..|transport_error"'
_USER_FAILED = 'outcome=~"server_error|timeout|connection_error"'

# feature -> list of PromQL expressions, each returning a vector labelled by
# `service` (or `target`, renamed). The first expression that yields a value
# for a service wins.
QUERIES: dict[str, list[str]] = {
    "request_rate": [
        f"sum by (service) (rate(http_requests_total{{{_HTTP}}}[{_W}]))",
        f"sum by (service) (rate(notifications_received_total{{{_NS}}}[{_W}]))",
    ],
    "error_rate": [
        f"sum by (service) (rate(http_requests_total{{{_HTTP},status_code=~\"5..\"}}[{_W}]))"
        f" / sum by (service) (rate(http_requests_total{{{_HTTP}}}[{_W}]))",
        f"sum by (service) (rate(notifications_received_total{{{_NS},status=\"malformed\"}}[{_W}]))"
        f" / sum by (service) (rate(notifications_received_total{{{_NS}}}[{_W}]))",
    ],
    "p99_latency_ms": [
        f"histogram_quantile(0.99, sum by (service, le) (rate(http_request_duration_seconds_bucket{{{_HTTP}}}[{_W}]))) * 1000",
        f"histogram_quantile(0.99, sum by (service, le) (rate(notification_processing_seconds_bucket{{{_NS}}}[{_W}]))) * 1000",
    ],
    "inflight": [
        f"sum by (service) (http_requests_in_flight{{{_NS}}})",
    ],
    "cpu_cores": [
        f"avg by (service) (label_replace(sum by (pod) (rate(container_cpu_usage_seconds_total{{{_CONTAINER}}}[{_CW}])), {_POD_TO_SERVICE}))",
    ],
    "cpu_throttle_ratio": [
        f"avg by (service) (label_replace(sum by (pod) (rate(container_cpu_cfs_throttled_periods_total{{{_CONTAINER}}}[{_CW}]))"
        f" / sum by (pod) (rate(container_cpu_cfs_periods_total{{{_CONTAINER}}}[{_CW}])), {_POD_TO_SERVICE}))",
    ],
    "memory_mb": [
        f"avg by (service) (label_replace(sum by (pod) (container_memory_working_set_bytes{{{_CONTAINER}}}), {_POD_TO_SERVICE})) / 1048576",
    ],
    "caller_error_rate": [
        f"label_replace(sum by (target) (rate(http_client_requests_total{{{_NS},{_FAILED}}}[{_W}]))"
        f" / sum by (target) (rate(http_client_requests_total{{{_NS}}}[{_W}])), \"service\", \"$1\", \"target\", \"(.*)\")",
        f"label_replace(sum(rate(loadgen_requests_total{{{_USER_FAILED}}}[{_W}])) / sum(rate(loadgen_requests_total[{_W}])),"
        f" \"service\", \"api-gateway\", \"\", \"\")",
    ],
    "caller_p99_ms": [
        f"label_replace(histogram_quantile(0.99, sum by (target, le) (rate(http_client_request_duration_seconds_bucket{{{_NS}}}[{_W}]))) * 1000,"
        f" \"service\", \"$1\", \"target\", \"(.*)\")",
        f"label_replace(histogram_quantile(0.99, sum by (le) (rate(loadgen_request_duration_seconds_bucket[{_W}]))) * 1000,"
        f" \"service\", \"api-gateway\", \"\", \"\")",
    ],
}

SCRAPE_UP_QUERY = f'avg by (service) (up{{job="pods",{_NS}}})'
CALL_RATE_QUERY = (f"sum by (service, target) (rate(http_client_requests_total{{{_NS}}}[{_W}]))")
USER_SLI_QUERIES = {
    "rps": f"sum(rate(loadgen_requests_total[{_W}]))",
    "failure_ratio": f"sum(rate(loadgen_requests_total{{{_USER_FAILED}}}[{_W}])) / sum(rate(loadgen_requests_total[{_W}]))",
    "p99_ms": f"histogram_quantile(0.99, sum by (le) (rate(loadgen_request_duration_seconds_bucket[{_W}]))) * 1000",
}

# Features where "no series" genuinely means zero (no traffic / no failures observed).
ZERO_WHEN_MISSING = {"request_rate", "error_rate", "inflight", "caller_error_rate"}

# Functional probe per service: a real request through nginx -> api-gateway whose
# handling requires that service. 4xx (e.g. unknown id) still proves it serves.
PROBES: dict[str, tuple[str, str]] = {
    "api-gateway": ("GET", "/health/dependencies"),
    "product-service": ("GET", "/products/1"),
    "order-service": ("GET", "/orders/1"),
    "payment-service": ("GET", "/payments/1"),
    "notification-service": ("GET", "/notifications/stats"),
}
PROBE_TIMEOUT_S = 3.0
PROBE_MAX_LATENCY_MS = 1000.0


@dataclass
class ServiceState:
    service: str
    features: dict[str, float | None]
    desired_replicas: int = 0
    ready_replicas: int = 0
    baseline_min_replicas: int = 1
    hpa_min: int = 0
    hpa_max: int = 0
    scrape_up: float | None = None
    restarts: int = 0
    pods: int = 0
    ready_pods: list[str] = field(default_factory=list)
    pod_names: list[str] = field(default_factory=list)
    quarantined_pods: list[str] = field(default_factory=list)
    generation: int = 0

    @property
    def ready_ratio(self) -> float:
        return self.ready_replicas / self.desired_replicas if self.desired_replicas else 0.0


@dataclass
class Snapshot:
    timestamp: datetime
    services: dict[str, ServiceState]
    user_sli: dict[str, float | None] = field(default_factory=dict)
    call_rates: dict[str, float] = field(default_factory=dict)   # "caller->callee": req/s
    prometheus_ok: bool = True

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "services": {k: asdict(v) | {"ready_ratio": v.ready_ratio} for k, v in self.services.items()},
            "user_sli": self.user_sli,
            "call_rates": self.call_rates,
            "prometheus_ok": self.prometheus_ok,
        }


class TelemetrySource(Protocol):
    def snapshot(self) -> Snapshot: ...
    def history(self, start: float, end: float, step: int) -> dict[str, list[tuple[float, dict]]]: ...
    def per_pod(self, service: str) -> dict[str, dict[str, float | None]]: ...
    def caller_breakdown(self, target: str) -> dict[str, dict[str, float | None]]: ...
    def probe(self, service: str) -> dict: ...
    def user_impact(self, start: float, end: float) -> dict: ...


def _finite(v: float | None) -> float | None:
    return v if v is not None and math.isfinite(v) else None


class PrometheusTelemetry:
    """Real telemetry from Prometheus (metrics) + Kubernetes API (structure)."""

    def __init__(self, url: str | None = None, cluster=None):
        self.url = (url or config.PROMETHEUS_URL).rstrip("/")
        self._http = httpx.Client(timeout=4.0)
        self._cluster = cluster

    @property
    def cluster(self):
        if self._cluster is None:
            from novasurge.cluster import get_cluster
            self._cluster = get_cluster()
        return self._cluster

    # ── Prometheus primitives ────────────────────────────────────────────────
    def query(self, promql: str, at: float | None = None) -> list[dict]:
        params = {"query": promql}
        if at is not None:
            params["time"] = f"{at:.3f}"
        resp = self._http.get(f"{self.url}/api/v1/query", params=params)
        resp.raise_for_status()
        body = resp.json()
        if body.get("status") != "success":
            raise RuntimeError(f"prometheus error: {body.get('error')}")
        return body["data"]["result"]

    def query_range(self, promql: str, start: float, end: float, step: int) -> list[dict]:
        resp = self._http.get(
            f"{self.url}/api/v1/query_range",
            params={"query": promql, "start": f"{start:.3f}", "end": f"{end:.3f}", "step": str(step)},
            timeout=30.0,
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("status") != "success":
            raise RuntimeError(f"prometheus error: {body.get('error')}")
        return body["data"]["result"]

    def per_pod(self, service: str) -> dict[str, dict[str, float | None]]:
        """Per-pod p99 (ms) and 5xx ratio — used to pick which replica to heal."""
        sel = f'{_NS},service="{service}"'
        exprs = {
            "p99_ms": f"histogram_quantile(0.99, sum by (pod, le) (rate(http_request_duration_seconds_bucket{{{sel}}}[{_W}]))) * 1000",
            "error_rate": f"sum by (pod) (rate(http_requests_total{{{sel},status_code=~\"5..\"}}[{_W}]))"
                          f" / sum by (pod) (rate(http_requests_total{{{sel}}}[{_W}]))",
            "cpu_throttle_ratio": f"sum by (pod) (rate(container_cpu_cfs_throttled_periods_total{{{_CONTAINER}}}[{_CW}]))"
                                  f" / sum by (pod) (rate(container_cpu_cfs_periods_total{{{_CONTAINER}}}[{_CW}]))",
        }
        out: dict[str, dict[str, float | None]] = {}
        for name, expr in exprs.items():
            try:
                for series in self.query(expr):
                    pod = series["metric"].get("pod")
                    if pod and pod.startswith(service):
                        out.setdefault(pod, {})[name] = _finite(float(series["value"][1]))
            except (httpx.HTTPError, RuntimeError):
                continue
        return out

    def caller_breakdown(self, target: str) -> dict[str, dict[str, float | None]]:
        """How each calling service currently experiences `target` (p99 ms, failure ratio)."""
        sel = f'{_NS},target="{target}"'
        exprs = {
            "p99_ms": f"histogram_quantile(0.99, sum by (service, le) "
                      f"(rate(http_client_request_duration_seconds_bucket{{{sel}}}[{_W}]))) * 1000",
            "error_rate": f"sum by (service) (rate(http_client_requests_total{{{sel},{_FAILED}}}[{_W}]))"
                          f" / sum by (service) (rate(http_client_requests_total{{{sel}}}[{_W}]))",
        }
        out: dict[str, dict[str, float | None]] = {}
        for name, expr in exprs.items():
            try:
                for series in self.query(expr):
                    caller = series["metric"].get("service")
                    if caller:
                        out.setdefault(caller, {})[name] = _finite(float(series["value"][1]))
            except (httpx.HTTPError, RuntimeError):
                continue
        return out

    def healthy(self) -> bool:
        try:
            return self._http.get(f"{self.url}/-/ready").status_code == 200
        except httpx.HTTPError:
            return False

    # ── user-path probes & impact ────────────────────────────────────────────
    def probe(self, service: str) -> dict:
        """One real request through nginx -> gateway that exercises `service`."""
        method, path = PROBES[service]
        start = time.perf_counter()
        try:
            resp = self._http.request(method, f"{config.GATEWAY_URL}{path}", timeout=PROBE_TIMEOUT_S)
            ms = (time.perf_counter() - start) * 1000
            ok = resp.status_code < 500 and ms <= PROBE_MAX_LATENCY_MS
            return {"ok": ok, "status": resp.status_code, "latency_ms": round(ms, 1)}
        except httpx.HTTPError as exc:
            return {"ok": False, "status": None, "latency_ms": round((time.perf_counter() - start) * 1000, 1),
                    "error": type(exc).__name__}

    def user_impact(self, start: float, end: float) -> dict:
        """Synthetic-user requests and failures between two epoch timestamps."""
        span = max(int(end - start), 10)
        try:
            total = self.query(f"sum(increase(loadgen_requests_total[{span}s]))", at=end)
            failed = self.query(f"sum(increase(loadgen_requests_total{{{_USER_FAILED}}}[{span}s]))", at=end)
            p99 = self.query("histogram_quantile(0.99, sum by (le) "
                             f"(increase(loadgen_request_duration_seconds_bucket[{span}s]))) * 1000", at=end)
        except (httpx.HTTPError, RuntimeError):
            return {"total_requests": None, "failed_requests": None, "failure_ratio": None, "p99_ms": None}
        t = float(total[0]["value"][1]) if total else 0.0
        f = float(failed[0]["value"][1]) if failed else 0.0
        p = _finite(float(p99[0]["value"][1])) if p99 else None
        return {"total_requests": round(t, 1), "failed_requests": round(f, 1),
                "failure_ratio": round(f / t, 4) if t > 0 else None, "p99_ms": round(p, 1) if p else None,
                "window_seconds": span}

    @staticmethod
    def _by_service(result: list[dict]) -> dict[str, float | None]:
        out: dict[str, float | None] = {}
        for series in result:
            svc = series["metric"].get("service")
            if svc in SERVICES:
                out[svc] = _finite(float(series["value"][1]))
        return out

    # ── Snapshot ─────────────────────────────────────────────────────────────
    def snapshot(self) -> Snapshot:
        ts = datetime.now(timezone.utc)
        features: dict[str, dict[str, float | None]] = {s: {} for s in SERVICES}
        prometheus_ok = True
        try:
            for feat, exprs in QUERIES.items():
                for expr in exprs:
                    for svc, val in self._by_service(self.query(expr)).items():
                        features[svc].setdefault(feat, val)
            scrape_up = self._by_service(self.query(SCRAPE_UP_QUERY))
            sli = {}
            for name, expr in USER_SLI_QUERIES.items():
                res = self.query(expr)
                sli[name] = _finite(float(res[0]["value"][1])) if res else None
            call_rates = {}
            for series in self.query(CALL_RATE_QUERY):
                m = series["metric"]
                val = _finite(float(series["value"][1]))
                if val is not None:
                    call_rates[f"{m.get('service')}->{m.get('target')}"] = round(val, 3)
        except (httpx.HTTPError, RuntimeError, KeyError, ValueError) as exc:
            log.warning("prometheus query failed: %s", exc)
            prometheus_ok, scrape_up, sli, call_rates = False, {}, {}, {}

        for svc in SERVICES:
            for feat in FEATURES:
                if features[svc].get(feat) is None and feat in ZERO_WHEN_MISSING and prometheus_ok:
                    features[svc][feat] = 0.0
                features[svc].setdefault(feat, None)

        states = {svc: ServiceState(service=svc, features=features[svc], scrape_up=scrape_up.get(svc))
                  for svc in SERVICES}
        self._attach_structure(states)
        return Snapshot(timestamp=ts, services=states, user_sli=sli, call_rates=call_rates,
                        prometheus_ok=prometheus_ok)

    def _attach_structure(self, states: dict[str, ServiceState]) -> None:
        try:
            pods = self.cluster.list_pods()
        except Exception as exc:  # noqa: BLE001 - API hiccup must not kill detection
            log.warning("pod listing failed: %s", exc)
            pods = []
        for svc, st in states.items():
            svc_pods = [p for p in pods if p.app == svc and not p.deleting]
            st.pods = len(svc_pods)
            st.restarts = sum(p.restarts for p in svc_pods)
            st.ready_pods = sorted(p.name for p in svc_pods if p.ready)
            st.pod_names = sorted(p.name for p in svc_pods)
            st.quarantined_pods = sorted(p.name for p in pods
                                         if p.labels.get("novasurge.io/quarantined-from") == svc)
            try:
                dep = self.cluster.get_deployment(svc)
                st.desired_replicas = dep.replicas
                st.ready_replicas = dep.ready_replicas
                st.generation = dep.generation
            except Exception as exc:  # noqa: BLE001
                log.debug("deployment read failed for %s: %s", svc, exc)
            try:
                hpa = self.cluster.get_hpa(f"{svc}-hpa")
                st.hpa_min, st.hpa_max = hpa.min_replicas, hpa.max_replicas
                baseline = json.loads(hpa.annotations.get("novasurge.io/baseline", "{}"))
                st.baseline_min_replicas = int(baseline.get("minReplicas", hpa.min_replicas))
            except Exception as exc:  # noqa: BLE001
                log.debug("hpa read failed for %s: %s", svc, exc)

    # ── History (training data) ──────────────────────────────────────────────
    def history(self, start: float, end: float, step: int = config.STEP_SECONDS
                ) -> dict[str, list[tuple[float, dict]]]:
        """Feature matrix over [start, end] from range queries — identical
        PromQL to the live snapshot, so training and inference see the same thing."""
        grid: dict[str, dict[float, dict]] = {s: {} for s in SERVICES}
        for feat, exprs in QUERIES.items():
            for expr in exprs:
                for series in self.query_range(expr, start, end, step):
                    svc = series["metric"].get("service")
                    if svc not in SERVICES:
                        continue
                    for t, v in series["values"]:
                        row = grid[svc].setdefault(float(t), {})
                        row.setdefault(feat, _finite(float(v)))
        out: dict[str, list[tuple[float, dict]]] = {}
        for svc, rows in grid.items():
            series = []
            for t in sorted(rows):
                row = rows[t]
                for feat in FEATURES:
                    if row.get(feat) is None and feat in ZERO_WHEN_MISSING:
                        row[feat] = 0.0
                    row.setdefault(feat, None)
                series.append((t, row))
            out[svc] = series
        return out


_source: TelemetrySource | None = None


def get_telemetry() -> TelemetrySource:
    global _source
    if _source is None:
        if config.SIMULATION:
            from novasurge.sim import get_simulated_telemetry
            _source = get_simulated_telemetry()
        else:
            _source = PrometheusTelemetry()
    return _source


def set_telemetry(source: TelemetrySource | None) -> None:
    global _source
    _source = source


def wait_for_prometheus(timeout: float = 120.0) -> bool:
    src = PrometheusTelemetry()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if src.healthy():
            return True
        time.sleep(2)
    return False
