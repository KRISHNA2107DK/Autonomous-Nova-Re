"""
replica_reduction — clamp the service's HorizontalPodAutoscaler to exactly one
replica (minReplicas = maxReplicas = 1). Models a bad autoscaler change: the
service silently loses redundancy and headroom, and cannot scale out under
load. Only meaningful for services whose declared minimum is >= 2.
"""

from __future__ import annotations

import json

from novasurge.chaos.injectors import Injection, now_iso

NAME = "replica_reduction"
DESCRIPTION = "Clamp HPA to min=max=1"
EXPECTED_SIGNATURE = "replica_exhaustion"


def _baseline_min(hpa) -> int:
    return int(json.loads(hpa.annotations.get("novasurge.io/baseline", "{}")).get("minReplicas", hpa.min_replicas))


def compatible(cluster, service: str) -> tuple[bool, str]:
    try:
        hpa = cluster.get_hpa(f"{service}-hpa")
    except Exception as exc:  # noqa: BLE001
        return False, f"no HPA: {exc}"
    if _baseline_min(hpa) < 2:
        return False, "declared minimum is already 1 replica"
    return True, f"HPA min={hpa.min_replicas} max={hpa.max_replicas}"


def inject(cluster, service: str) -> Injection:
    name = f"{service}-hpa"
    hpa = cluster.get_hpa(name)
    original = {"minReplicas": hpa.min_replicas, "maxReplicas": hpa.max_replicas}
    at = now_iso()
    cluster.patch_hpa(name, {"spec": {"minReplicas": 1, "maxReplicas": 1}})
    return Injection(NAME, service, True, at, target=name,
                     details={"hpa": name, "original": original, "patched_to": {"minReplicas": 1, "maxReplicas": 1}})


def still_active(cluster, injection: Injection) -> bool:
    hpa = cluster.get_hpa(injection.target)
    return hpa.max_replicas < injection.details["original"]["minReplicas"]


def reverse(cluster, injection: Injection) -> dict:
    hpa = cluster.get_hpa(injection.target)
    orig = injection.details["original"]
    if hpa.max_replicas < orig["minReplicas"] or hpa.min_replicas < orig["minReplicas"]:
        cluster.patch_hpa(injection.target, {"spec": {
            "minReplicas": max(hpa.min_replicas, orig["minReplicas"]),
            "maxReplicas": max(hpa.max_replicas, orig["maxReplicas"]),
        }})
        return {"restored": True, "to": orig}
    return {"restored": False, "note": "autoscaler already at or above declared bounds"}
