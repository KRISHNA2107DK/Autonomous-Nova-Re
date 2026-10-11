"""
Remediators — each fixes (or mitigates) a concrete class of fault and waits for
its own completion criterion before returning.

    pod_restart              delete the worst replica; controller replaces it
    rolling_restart          zero-downtime rollout of the declared pod template
    hpa_scaleout             restore/raise autoscaler bounds, wait for capacity
    resource_restore         reconcile live CPU/memory to the declared baseline
    network_policy_rollback  remove deny-all NetworkPolicies isolating the service
    traffic_reroute          quarantine the worst replica out of the Service
    cache_flush              drop product cache keys in Redis

Every remediator returns a RemediationResult; whether the *service* recovered is
verified separately by the orchestrator against live telemetry.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Awaitable, Callable


@dataclass
class RemediationContext:
    cluster: object
    telemetry: object | None = None
    timeout_s: float = 120.0
    poll_s: float = 2.0


@dataclass
class RemediationResult:
    remediator: str
    service: str
    success: bool
    summary: str
    started_at: str
    completed_at: str
    duration_s: float
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def note_own_action(pods: list[str]) -> None:
    """Remember pods AutoHeal itself deleted/replaced (kept 15 minutes)."""
    from novasurge import state_db
    cutoff = time.time() - 900
    own = {k: v for k, v in state_db.kv_get("own_pod_actions", {}).items() if v > cutoff}
    for p in pods:
        own[p] = time.time()
    state_db.kv_set("own_pod_actions", own)


async def wait_until(predicate: Callable[[], bool], timeout_s: float, poll_s: float) -> bool:
    deadline = time.monotonic() + timeout_s
    while True:
        try:
            if predicate():
                return True
        except Exception:  # noqa: BLE001 - transient API errors while converging
            pass
        if time.monotonic() >= deadline:
            return False
        await asyncio.sleep(poll_s)


def deployment_converged(cluster, service: str, min_ready: int | None = None) -> bool:
    dep = cluster.get_deployment(service)
    want = max(dep.replicas, min_ready or 0)
    pods = [p for p in cluster.list_pods(service) if not p.deleting]
    return (dep.observed_generation >= dep.generation and dep.updated_replicas >= dep.replicas
            and dep.ready_replicas >= want and len([p for p in pods if p.ready]) >= want)


def baseline_resources(cluster, service: str) -> dict[str, dict]:
    dep = cluster.get_deployment(service)
    raw = dep.annotations.get("novasurge.io/baseline-resources")
    if raw:
        return json.loads(raw)
    return {c.name: {"requests": c.requests, "limits": c.limits} for c in dep.containers}


def baseline_hpa(cluster, service: str) -> dict:
    hpa = cluster.get_hpa(f"{service}-hpa")
    raw = hpa.annotations.get("novasurge.io/baseline")
    return json.loads(raw) if raw else {"minReplicas": hpa.min_replicas, "maxReplicas": hpa.max_replicas}


def worst_pod(ctx: RemediationContext, service: str) -> tuple[object | None, str]:
    """Pick the replica most likely at fault: not-ready first, then worst per-pod telemetry."""
    pods = [p for p in ctx.cluster.list_pods(service) if not p.deleting]
    if not pods:
        return None, "no pods"
    not_ready = [p for p in pods if not p.ready]
    if not_ready:
        return not_ready[0], "pod is not Ready"
    per_pod = {}
    if ctx.telemetry is not None and hasattr(ctx.telemetry, "per_pod"):
        try:
            per_pod = ctx.telemetry.per_pod(service)
        except Exception:  # noqa: BLE001
            per_pod = {}
    scored = []
    for p in pods:
        m = per_pod.get(p.name, {})
        score = (m.get("p99_ms") or 0.0) + 2000.0 * (m.get("error_rate") or 0.0) \
            + 1000.0 * (m.get("cpu_throttle_ratio") or 0.0)
        scored.append((score, p, m))
    scored.sort(key=lambda t: -t[0])
    best_score, best, metrics = scored[0]
    if best_score > 0 and len(scored) > 1:
        second = scored[1][0]
        return best, (f"worst replica by live telemetry (p99={metrics.get('p99_ms') or 0:.0f}ms, "
                      f"next worst score {second:.0f} vs {best_score:.0f})")
    oldest = min(pods, key=lambda p: p.created_at or datetime.min.replace(tzinfo=timezone.utc))
    return oldest, "no per-pod signal; oldest replica"


Remediator = Callable[[str, RemediationContext], Awaitable[RemediationResult]]

from novasurge.remediators import (  # noqa: E402
    cache_flush,
    hpa_scaleout,
    network_policy_rollback,
    pod_restart,
    resource_restore,
    rolling_restart,
    traffic_reroute,
)

REGISTRY: dict[str, Remediator] = {
    "pod_restart": pod_restart.remediate,
    "rolling_restart": rolling_restart.remediate,
    "hpa_scaleout": hpa_scaleout.remediate,
    "resource_restore": resource_restore.remediate,
    "network_policy_rollback": network_policy_rollback.remediate,
    "traffic_reroute": traffic_reroute.remediate,
    "cache_flush": cache_flush.remediate,
}

# Remediators that take a serving replica out of rotation (Guardrail 2 applies).
REMOVES_CAPACITY = {"pod_restart", "traffic_reroute"}
