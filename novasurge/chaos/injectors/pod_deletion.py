"""
pod_deletion — kill one Ready replica with no grace period (simulates a node
loss / OOM-kill / crash). Kubernetes reschedules it; in-flight requests to the
victim fail and capacity is reduced until the replacement is Ready.
"""

from __future__ import annotations

import random

from novasurge.chaos.injectors import Injection, now_iso

NAME = "pod_deletion"
DESCRIPTION = "Force-delete one Ready pod (grace period 0)"
EXPECTED_SIGNATURE = "pod_crash"


def compatible(cluster, service: str) -> tuple[bool, str]:
    ready = [p for p in cluster.list_pods(service) if p.ready and not p.deleting]
    if not ready:
        return False, "no Ready pods to delete"
    return True, f"{len(ready)} Ready pod(s)"


def inject(cluster, service: str) -> Injection:
    ready = [p for p in cluster.list_pods(service) if p.ready and not p.deleting]
    if not ready:
        return Injection(NAME, service, False, now_iso(), error="no Ready pods")
    victim = random.choice(ready)
    at = now_iso()
    cluster.delete_pod(victim.name, grace_seconds=0)
    return Injection(NAME, service, True, at, target=victim.name,
                     details={"pod": victim.name, "pod_ip": victim.ip, "ready_pods_before": len(ready)})


def still_active(cluster, injection: Injection) -> bool:
    """The fault persists until the deployment is back at full Ready capacity."""
    dep = cluster.get_deployment(injection.service)
    victim_alive = any(p.name == injection.target for p in cluster.list_pods(injection.service))
    return victim_alive or dep.ready_replicas < dep.replicas


def reverse(cluster, injection: Injection) -> dict:
    return {"reversible": False, "note": "Kubernetes reschedules deleted pods by itself"}
