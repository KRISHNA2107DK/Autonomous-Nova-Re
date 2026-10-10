"""
SimulatedTelemetry — feature vectors derived from SimulatedCluster state.

Healthy operating points mirror what the real ShopFusion deployment reports
(measured from Prometheus), with Gaussian noise. Fault effects reproduce the
signatures observed on the live cluster, including how they cascade:
  * isolated service      -> its traffic vanishes, its scrape fails, callers time out
  * CPU-starved replicas  -> CFS throttling, latency and queueing climb, callers slow down
  * netem replica         -> that replica's latency climbs; its *outbound* calls look
                             slow from the callee's caller-side metrics
  * lost / unready pods   -> reported through replica counts (structural signals)
"""

from __future__ import annotations

import json
import random
import threading
import time
from datetime import datetime, timezone

from novasurge import topology
from novasurge.telemetry import ServiceState, Snapshot

BASE: dict[str, dict[str, float | None]] = {
    "api-gateway":          {"request_rate": 20.0, "error_rate": 0.0, "p99_latency_ms": 243.0, "inflight": 1.0,
                             "cpu_cores": 0.025, "cpu_throttle_ratio": 0.0, "memory_mb": 50.0,
                             "caller_error_rate": 0.0, "caller_p99_ms": 243.0},
    "product-service":      {"request_rate": 21.0, "error_rate": 0.0, "p99_latency_ms": 15.0, "inflight": 0.3,
                             "cpu_cores": 0.020, "cpu_throttle_ratio": 0.0, "memory_mb": 78.0,
                             "caller_error_rate": 0.0, "caller_p99_ms": 16.0},
    "order-service":        {"request_rate": 7.5, "error_rate": 0.0, "p99_latency_ms": 247.0, "inflight": 1.0,
                             "cpu_cores": 0.022, "cpu_throttle_ratio": 0.0, "memory_mb": 86.0,
                             "caller_error_rate": 0.0, "caller_p99_ms": 247.0},
    "payment-service":      {"request_rate": 7.5, "error_rate": 0.0, "p99_latency_ms": 246.0, "inflight": 1.0,
                             "cpu_cores": 0.018, "cpu_throttle_ratio": 0.0, "memory_mb": 80.0,
                             "caller_error_rate": 0.0, "caller_p99_ms": 246.0},
    "notification-service": {"request_rate": 10.3, "error_rate": 0.0, "p99_latency_ms": 0.5, "inflight": 0.0,
                             "cpu_cores": 0.008, "cpu_throttle_ratio": 0.0, "memory_mb": 22.0,
                             "caller_error_rate": 0.0, "caller_p99_ms": None},
}
NOISE = {"request_rate": 0.03, "p99_latency_ms": 0.03, "inflight": 0.0, "cpu_cores": 0.08, "memory_mb": 0.01,
         "caller_p99_ms": 0.03}
CALLS = {"api-gateway->product-service": 10.0, "api-gateway->order-service": 7.5,
         "api-gateway->payment-service": 2.0, "order-service->product-service": 10.0,
         "order-service->payment-service": 5.0}


def _noisy(rng: random.Random, feats: dict) -> dict:
    out = {}
    for k, v in feats.items():
        if v is None:
            out[k] = None
            continue
        rel = NOISE.get(k, 0.0)
        out[k] = max(0.0, v * (1 + rng.gauss(0, rel))) if rel else v
        if k == "inflight":
            out[k] = max(0.0, v + rng.gauss(0, 0.3))
    return out


class SimulatedTelemetry:
    def __init__(self, cluster, seed: int = 5):
        self.cluster = cluster
        self._rng = random.Random(seed)
        self._lock = threading.Lock()
        self._impact: list[tuple[float, float, float]] = []    # (epoch, rps, failure_ratio)

    # ── fault model ──────────────────────────────────────────────────────────
    def _effects(self) -> tuple[dict[str, dict], dict[str, float], dict[str, float], float]:
        c = self.cluster
        feats = {s: _noisy(self._rng, BASE[s]) for s in topology.SERVICES}
        scrape = {s: 1.0 for s in topology.SERVICES}
        calls = dict(CALLS)
        failure = 0.0
        for svc in topology.SERVICES:
            pods = [p for p in c.pods.values() if p.app == svc and p.deleting_at is None]
            serving = c.serving_pods(svc)
            isolated = any(c.isolated(p) for p in pods)
            declared = c.cpu_limit_millis_declared(svc)
            throttled = [p for p in serving if c.cpu_limit_millis(p) < 0.5 * declared]
            slow = [p for p in serving if p.netem]
            f_t = len(throttled) / len(serving) if serving else 0.0
            f_n = len(slow) / len(serving) if serving else 0.0
            f = feats[svc]
            if isolated:
                f["request_rate"] *= 0.05
                f["p99_latency_ms"] = None
                f["caller_error_rate"], f["caller_p99_ms"] = 0.65, 5000.0
                scrape[svc] = 0.0
                for k in [k for k in calls if k.endswith(svc) or k.startswith(svc)]:
                    calls[k] = 0.0
                for caller in topology.upstream_closure(svc):
                    feats[caller]["p99_latency_ms"] = max(feats[caller]["p99_latency_ms"] or 0, 4500.0)
                    feats[caller]["error_rate"] = max(feats[caller]["error_rate"], 0.3)
                    feats[caller]["inflight"] += 15
                    feats[caller]["caller_error_rate"] = max(feats[caller]["caller_error_rate"] or 0, 0.3)
                if svc == "api-gateway":
                    for down in topology.downstream_closure(svc):
                        feats[down]["request_rate"] *= 0.05
                failure = max(failure, topology.USER_TRAFFIC_SHARE.get(svc, 0.0) * 0.8)
            if f_t:
                f["cpu_throttle_ratio"] = 0.6 * f_t
                f["p99_latency_ms"] = (f["p99_latency_ms"] or 0) * (1 + 8 * f_t)
                f["inflight"] += 8 * f_t
                f["caller_p99_ms"] = (f["p99_latency_ms"] or 0) * 1.05
                f["caller_error_rate"] = 0.04 * f_t
                for caller in topology.upstream_closure(svc):
                    feats[caller]["p99_latency_ms"] = (feats[caller]["p99_latency_ms"] or 0) + 0.8 * f["p99_latency_ms"]
                failure = max(failure, 0.04 * f_t)
            if f_n:
                f["p99_latency_ms"] = max(f["p99_latency_ms"] or 0, BASE[svc]["p99_latency_ms"] + 3000 * min(1, 2 * f_n))
                f["caller_p99_ms"] = (f["p99_latency_ms"] or 0) + 200
                for callee in topology.callees_of(svc):
                    own = feats[callee]["p99_latency_ms"] or 0.0
                    feats[callee]["caller_p99_ms"] = max(feats[callee]["caller_p99_ms"] or 0, own + 220.0)
                for caller in topology.upstream_closure(svc):
                    feats[caller]["p99_latency_ms"] = max(feats[caller]["p99_latency_ms"] or 0, f["p99_latency_ms"])
                failure = max(failure, 0.003)
            ready = len(serving)
            base_min = json.loads(c.hpas[svc].annotations["novasurge.io/baseline"])["minReplicas"]
            if ready and ready < base_min:
                f["cpu_cores"] *= base_min / ready
        return feats, scrape, calls, failure

    # ── TelemetrySource contract ─────────────────────────────────────────────
    def snapshot(self) -> Snapshot:
        with self.cluster._lock:
            feats, scrape, calls, failure = self._effects()
            states = {}
            for svc in topology.SERVICES:
                dep = self.cluster.get_deployment(svc)
                hpa = self.cluster.get_hpa(f"{svc}-hpa")
                pods = self.cluster.list_pods(svc)
                live = [p for p in pods if not p.deleting]
                states[svc] = ServiceState(
                    service=svc, features=feats[svc], desired_replicas=dep.replicas,
                    ready_replicas=dep.ready_replicas,
                    baseline_min_replicas=json.loads(hpa.annotations["novasurge.io/baseline"])["minReplicas"],
                    hpa_min=hpa.min_replicas, hpa_max=hpa.max_replicas, scrape_up=scrape[svc],
                    restarts=sum(p.restarts for p in live), pods=len(live),
                    ready_pods=sorted(p.name for p in live if p.ready), pod_names=sorted(p.name for p in live),
                    quarantined_pods=sorted(p.name for p in self.cluster.list_pods()
                                            if p.labels.get("novasurge.io/quarantined-from") == svc),
                    generation=dep.generation)
        rps = 20.0 * (1 + self._rng.gauss(0, 0.02))
        with self._lock:
            self._impact.append((time.time(), rps, failure))
            self._impact = self._impact[-5000:]
        sli = {"rps": rps, "failure_ratio": failure, "p99_ms": feats["api-gateway"]["caller_p99_ms"]}
        return Snapshot(timestamp=datetime.now(timezone.utc), services=states, user_sli=sli,
                        call_rates={k: round(v, 2) for k, v in calls.items()})

    def history(self, start: float, end: float, step: int) -> dict[str, list[tuple[float, dict]]]:
        rng = random.Random(int(start))
        out: dict[str, list[tuple[float, dict]]] = {s: [] for s in topology.SERVICES}
        t = start
        while t <= end:
            for svc in topology.SERVICES:
                out[svc].append((t, _noisy(rng, BASE[svc])))
            t += step
        return out

    def per_pod(self, service: str) -> dict[str, dict[str, float | None]]:
        out = {}
        declared = self.cluster.cpu_limit_millis_declared(service)
        for p in self.cluster.serving_pods(service):
            out[p.name] = {
                "p99_ms": BASE[service]["p99_latency_ms"] + (3000.0 if p.netem else 0.0),
                "error_rate": 0.0,
                "cpu_throttle_ratio": 0.6 if self.cluster.cpu_limit_millis(p) < 0.5 * declared else 0.0,
            }
        return out

    def caller_breakdown(self, target: str) -> dict[str, dict[str, float | None]]:
        out = {}
        isolated = any(self.cluster.isolated(p) for p in self.cluster.pods.values() if p.app == target)
        for caller in topology.callers_of(target):
            slow_caller = any(p.netem for p in self.cluster.serving_pods(caller))
            base = BASE[target]["p99_latency_ms"] or 0.0
            out[caller] = {"p99_ms": 5000.0 if isolated else (base + 220.0 if slow_caller else base + 2.0),
                           "error_rate": 0.65 if isolated else 0.0}
        return out

    def probe(self, service: str) -> dict:
        serving = self.cluster.serving_pods(service)
        if not serving or any(self.cluster.isolated(p) for p in serving):
            return {"ok": False, "status": 504, "latency_ms": 3000.0}
        slow = any(p.netem for p in serving) or any(self.cluster.cpu_limit_millis(p) < 250 for p in serving)
        return {"ok": not slow, "status": 200, "latency_ms": 1800.0 if slow else 8.0}

    def user_impact(self, start: float, end: float) -> dict:
        with self._lock:
            pts = [(t, r, f) for t, r, f in self._impact if start <= t <= end]
        if len(pts) < 2:
            return {"total_requests": 0.0, "failed_requests": 0.0, "failure_ratio": None, "p99_ms": None,
                    "window_seconds": int(end - start)}
        total = failed = 0.0
        for (t0, r0, f0), (t1, _, _) in zip(pts, pts[1:]):
            dt = t1 - t0
            total += r0 * dt
            failed += r0 * dt * f0
        return {"total_requests": round(total, 1), "failed_requests": round(failed, 1),
                "failure_ratio": round(failed / total, 4) if total else None, "p99_ms": None,
                "window_seconds": int(end - start)}

    def healthy(self) -> bool:
        return True

