"""
Root-cause analysis.

Input: the detector's view of every service (deviations, structural flags,
first-flagged time) plus evidence gathered from the cluster. Output: the most
likely origin service, a refined fault type, a confidence and a narrative.

Principles
  * Failures propagate *upstream*: when a callee breaks, its callers show
    errors/latency too. So a caller is only the origin if none of its callees
    explains its symptoms (the original implementation walked to callers and
    therefore blamed the gateway for every backend fault).
  * Earlier onset is evidence of causality (temporal precedence).
  * Recent changes are the most common root cause: NetworkPolicies selecting
    the service, live resource drift from the declared baseline, autoscaler
    bounds below the declared minimum, container restarts / kills.
  * Error logs from the service's own pods corroborate it.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone

from novasurge import state_db, topology
from novasurge.cluster import pod_selector_matches
from novasurge.ml.detector import DetectionResult, ServiceDetection

log = logging.getLogger("novasurge.rca")


@dataclass
class Candidate:
    service: str
    score: float
    reasons: list[str] = field(default_factory=list)


@dataclass
class RcaResult:
    origin: str
    anomaly_type: str
    confidence: float
    call_path: list[str]
    affected: list[str]
    evidence: list[str]
    candidates: list[dict]
    narrative: str

    def to_dict(self) -> dict:
        return asdict(self)


FAILURE_FLAGS = {"all_replicas_down", "replicas_lost", "container_restarted", "capacity_below_baseline",
                 "metrics_unreachable"}
EXCESS_LATENCY_MS = 100.0
SYMPTOM_FEATURES = ("error_rate", "p99_latency_ms", "caller_error_rate", "caller_p99_ms",
                    "cpu_throttle_ratio", "memory_mb", "inflight")


def is_failing(d: ServiceDetection) -> bool:
    """Failure symptoms of its own — as opposed to merely receiving less traffic."""
    if any(f in FAILURE_FLAGS for f in d.flags + d.episode_flags):
        return True
    return any(d.z.get(f, 0.0) >= 4.0 for f in SYMPTOM_FEATURES)


def caller_side_only(d: ServiceDetection) -> bool:
    """Callers see it degraded, but its own handlers are fine and it is reachable."""
    if any(f in FAILURE_FLAGS for f in d.flags + d.episode_flags):
        return False
    own = max(d.z.get("p99_latency_ms", 0.0), d.z.get("error_rate", 0.0), d.z.get("cpu_throttle_ratio", 0.0))
    seen = max(d.z.get("caller_p99_ms", 0.0), d.z.get("caller_error_rate", 0.0))
    return own < 3.0 and seen >= 4.0


def degraded_callers(telemetry, service: str, d: ServiceDetection) -> dict[str, dict]:
    """Callers whose own view of `service` is degraded (per-caller breakdown)."""
    if telemetry is None or not hasattr(telemetry, "caller_breakdown"):
        return {}
    try:
        views = telemetry.caller_breakdown(service)
    except Exception:  # noqa: BLE001
        return {}
    # Excess latency = what the caller sees minus what the callee's own handlers
    # take. Healthy in-cluster overhead is a few ms; >100ms is network/caller-side.
    own_p99 = d.raw.get("p99_latency_ms") or 0.0
    out = {}
    for caller, view in views.items():
        p99, err = view.get("p99_ms") or 0.0, view.get("error_rate") or 0.0
        if caller in topology.SERVICES and (p99 - own_p99 > EXCESS_LATENCY_MS or err > 0.05):
            out[caller] = view | {"excess_ms": round(p99 - own_p99, 1)}
    return out


def _cpu_millis(value: str | None) -> float | None:
    if value is None:
        return None
    value = str(value)
    if value.endswith("m"):
        return float(value[:-1])
    try:
        return float(value) * 1000
    except ValueError:
        return None


class EvidenceCollector:
    """Read-only cluster evidence for a service (changes, events, logs)."""

    def __init__(self, cluster):
        self.cluster = cluster

    def collect(self, service: str, window_s: int = 300) -> list[tuple[str, str, float]]:
        """List of (kind, description, weight)."""
        out: list[tuple[str, str, float]] = []
        try:
            pods = [p for p in self.cluster.list_pods(service) if not p.deleting]
        except Exception as exc:  # noqa: BLE001
            log.warning("evidence: pod listing failed: %s", exc)
            return out
        labels = pods[0].labels if pods else {"app": service}

        # 1. isolating NetworkPolicies
        try:
            for np_ in self.cluster.list_network_policies():
                if pod_selector_matches(np_.pod_selector, labels) and np_.denies_all \
                        and np_.labels.get("novasurge.io/baseline") != "true":
                    age = ""
                    if np_.created_at:
                        age = f", created {int((datetime.now(timezone.utc) - np_.created_at).total_seconds())}s ago"
                    out.append(("network_policy",
                                f"NetworkPolicy '{np_.name}' denies all {'/'.join(np_.policy_types)} traffic "
                                f"for pods of {service}{age}", 3.0))
        except Exception as exc:  # noqa: BLE001
            log.debug("evidence: network policies unavailable: %s", exc)

        # 2. live resource drift vs declared baseline
        try:
            dep = self.cluster.get_deployment(service)
            declared = json.loads(dep.annotations.get("novasurge.io/baseline-resources", "{}"))
            for pod in pods:
                for container, live in pod.resources.items():
                    want = declared.get(container)
                    if not want:
                        continue
                    live_cpu = _cpu_millis(live.get("limits", {}).get("cpu"))
                    want_cpu = _cpu_millis(want.get("limits", {}).get("cpu"))
                    if live_cpu is not None and want_cpu and live_cpu < want_cpu * 0.5:
                        out.append(("resource_drift",
                                    f"pod {pod.name} CPU limit is {live.get('limits', {}).get('cpu')} "
                                    f"vs declared {want['limits']['cpu']}", 2.5))
        except Exception as exc:  # noqa: BLE001
            log.debug("evidence: resource drift check failed: %s", exc)

        # 3. autoscaler bounds below the declared minimum
        try:
            hpa = self.cluster.get_hpa(f"{service}-hpa")
            base = json.loads(hpa.annotations.get("novasurge.io/baseline", "{}"))
            if base and hpa.max_replicas < base.get("minReplicas", 0):
                out.append(("autoscaler_drift",
                            f"HPA bounds {hpa.min_replicas}-{hpa.max_replicas} are below the declared "
                            f"{base['minReplicas']}-{base['maxReplicas']}", 2.5))
        except Exception as exc:  # noqa: BLE001
            log.debug("evidence: hpa check failed: %s", exc)

        # 4. recent pod lifecycle events (generic, so capped; AutoHeal's own actions excluded)
        try:
            since = datetime.now(timezone.utc) - timedelta(seconds=window_s)
            own = set(state_db.kv_get("own_pod_actions", {}))
            interesting = [ev for ev in self.cluster.list_events(since)
                           if ev.name.startswith(service) and ev.name not in own
                           and ev.reason in {"Killing", "OOMKilling", "BackOff", "Unhealthy", "FailedScheduling"}]
            for ev in interesting[:3]:
                out.append(("k8s_event", f"{ev.kind} {ev.name}: {ev.reason} — {ev.message[:120]}",
                            1.0 / max(len(interesting[:3]), 1)))
        except Exception as exc:  # noqa: BLE001
            log.debug("evidence: events unavailable: %s", exc)

        # 5. error logs from the service's own pods
        errors, sample = 0, None
        for pod in pods[:3]:
            try:
                text = self.cluster.pod_logs(pod.name, since_seconds=60, tail_lines=400)
            except Exception:  # noqa: BLE001 - unreachable pods can't serve logs
                continue
            for line in text.splitlines():
                if '"level": "ERROR"' in line or '"level":"ERROR"' in line:
                    errors += 1
                    if sample is None:
                        m = re.search(r'"message":\s*"([^"]+)"', line)
                        d = re.search(r'"(?:detail|error|target)":\s*"([^"]+)"', line)
                        sample = (m.group(1) if m else line[:80]) + (f" ({d.group(1)[:60]})" if d else "")
        if errors:
            out.append(("error_logs", f"{errors} ERROR log lines in the last 60s, e.g. '{sample}'",
                        min(1.5, 0.5 + errors / 200)))
        return out


def analyze(detection: DetectionResult, cluster, telemetry=None) -> RcaResult | None:
    services = detection.services
    # Confirmed anomalies plus services deviating in the current window: in a
    # cascade the culprit's own signal can trail its callers' by a tick.
    affected = list(detection.anomalous) + [s for s in topology.SERVICES
                                            if services[s].window_anomalous and s not in detection.anomalous]
    if not affected:
        return None
    collector = EvidenceCollector(cluster)

    onset = {s: _ts(services[s].first_flagged_at) for s in affected}
    earliest = min((t for t in onset.values() if t), default=None)
    window_s = int((datetime.now(timezone.utc) - earliest).total_seconds()) + 30 if earliest else 120

    evidence_by_svc = {s: collector.collect(s, window_s) for s in affected}
    caller_bonus: dict[str, float] = {}
    caller_notes: dict[str, list[str]] = {}
    candidates: list[Candidate] = []
    for svc in affected:
        d = services[svc]
        c = Candidate(svc, 0.0)
        c.score += 2.0 * d.severity
        c.reasons.append(f"severity {d.severity:.2f}")

        if not is_failing(d):
            c.score -= 1.0
            c.reasons.append("only symptom is reduced traffic — consistent with an upstream failure")
        elif caller_side_only(d):
            c.score -= 1.5
            c.reasons.append("its own server-side latency/errors are normal; the degradation is only "
                             "visible from callers (network or caller-side problem)")
            for caller, view in degraded_callers(telemetry, svc, d).items():
                caller_bonus[caller] = caller_bonus.get(caller, 0.0) + 1.5
                caller_notes.setdefault(caller, []).append(
                    f"its calls to {svc} take {view.get('excess_ms', 0):.0f}ms longer than {svc} itself "
                    f"needs to serve them (caller-side or network problem)")

        # Does a deeper (callee) failure explain this service's symptoms?
        anomalous_callees = [x for x in topology.downstream_closure(svc)
                             if x in affected and is_failing(services[x])]
        if anomalous_callees:
            c.score -= 1.5
            c.reasons.append(f"its dependencies {anomalous_callees} are also anomalous (likely a victim)")
        else:
            c.score += 1.0
            c.reasons.append("no anomalous dependency explains it")

        # Victims of this service
        victims = [x for x in topology.upstream_closure(svc) if x in affected]
        if victims:
            c.score += 0.3 * len(victims)
            c.reasons.append(f"explains anomalies in callers {victims}")

        if earliest and onset[svc] and (onset[svc] - earliest).total_seconds() <= 5:
            c.score += 0.75
            c.reasons.append("earliest onset")

        if any(f in d.flags + d.episode_flags for f in FAILURE_FLAGS):
            c.score += 0.75
            c.reasons.append("structural fault on the service itself")

        for kind, desc, weight in evidence_by_svc[svc]:
            c.score += weight
            c.reasons.append(desc)
        candidates.append(c)

    for c in candidates:
        if c.service in caller_bonus:
            c.score += caller_bonus[c.service]
            c.reasons += caller_notes[c.service]
    for caller, bonus in caller_bonus.items():
        if caller not in {c.service for c in candidates}:
            candidates.append(Candidate(caller, bonus, list(caller_notes[caller])))
            evidence_by_svc[caller] = collector.collect(caller, window_s)
            candidates[-1].score += sum(w for _, _, w in evidence_by_svc[caller])
    candidates.sort(key=lambda c: -c.score)
    top = candidates[0]
    second = candidates[1].score if len(candidates) > 1 else 0.0
    margin = top.score - second
    confidence = 0.55 + 0.4 * min(margin / 3.0, 1.0) if len(candidates) > 1 else 0.6 + 0.08 * min(top.score, 4.5)
    confidence = round(min(confidence, 0.97), 3)

    origin = top.service
    d: ServiceDetection = services[origin]
    anomaly_type = _refine_type(d.anomaly_type or "unknown", evidence_by_svc[origin])
    evidence = list(d.evidence) + [desc for _, desc, _ in evidence_by_svc[origin]]
    path = topology.call_path(origin)
    narrative = _narrative(origin, anomaly_type, d, candidates, affected, evidence_by_svc[origin], confidence)
    return RcaResult(origin=origin, anomaly_type=anomaly_type, confidence=confidence, call_path=path,
                     affected=affected, evidence=evidence,
                     candidates=[{"service": c.service, "score": round(c.score, 3), "reasons": c.reasons}
                                 for c in candidates],
                     narrative=narrative)


def _refine_type(detected: str, evidence: list[tuple[str, str, float]]) -> str:
    """Change evidence overrides the purely metric-based guess when it is conclusive."""
    kinds = {k for k, _, _ in evidence}
    if "network_policy" in kinds:
        return "network_partition"
    if "autoscaler_drift" in kinds:
        return "replica_exhaustion"
    if "resource_drift" in kinds:
        return "cpu_throttle"
    if any("OOMKill" in desc for _, desc, _ in evidence):
        return "oom_kill"
    return detected


def _narrative(origin: str, anomaly_type: str, d: ServiceDetection, candidates: list[Candidate],
               affected: list[str], evidence: list[tuple[str, str, float]], confidence: float) -> str:
    parts = [f"Root cause localised to {origin} ({anomaly_type.replace('_', ' ')}, confidence {confidence:.0%})."]
    others = [s for s in affected if s != origin]
    if others:
        upstream = [s for s in others if s in topology.upstream_closure(origin)]
        downstream = [s for s in others if s in topology.downstream_closure(origin)]
        unexplained = [s for s in others if s not in upstream and s not in downstream]
        if upstream:
            parts.append(f"{', '.join(upstream)} also deviate as callers of {origin}: its failure propagates to them.")
        if downstream:
            parts.append(f"{', '.join(downstream)} deviate because requests from {origin} stopped reaching them.")
        if unexplained:
            parts.append(f"{', '.join(unexplained)} also deviate without a dependency explaining it "
                         f"(lower-ranked candidates).")
    else:
        parts.append(f"No other service deviates; the fault is contained to {origin}.")
    strongest = [desc for _, desc, w in sorted(evidence, key=lambda e: -e[2])[:2]]
    if strongest:
        parts.append("Change evidence: " + "; ".join(strongest) + ".")
    elif d.evidence:
        parts.append("Signal: " + "; ".join(d.evidence[:2]) + ".")
    return " ".join(parts)


def _ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
