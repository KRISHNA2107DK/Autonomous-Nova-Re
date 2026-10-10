"""
cpu_throttle — starve every replica of CPU by resizing its CPU limit in place
(Kubernetes in-place pod resize: the cgroup quota changes live, no restart).

This models a bad resource-limit change / noisy-neighbour starvation: requests
queue behind the CFS quota, so throttled periods and latency climb while the
pods stay Ready. The Deployment template is left untouched, which is exactly
why a rollout of the declared spec (or an in-place restore) heals it.
"""

from __future__ import annotations

import os

from novasurge.chaos.injectors import Injection, now_iso

NAME = "cpu_throttle"
DESCRIPTION = "In-place resize of every replica's CPU limit to a starvation value"
EXPECTED_SIGNATURE = "cpu_throttle"
THROTTLED_CPU = os.environ.get("NOVASURGE_THROTTLE_CPU", "25m")
MARK = "novasurge.io/chaos"


def compatible(cluster, service: str) -> tuple[bool, str]:
    pods = [p for p in cluster.list_pods(service) if p.ready and not p.deleting]
    if not pods:
        return False, "no Ready pods"
    return True, f"{len(pods)} pod(s) can be resized in place"


def inject(cluster, service: str) -> Injection:
    pods = [p for p in cluster.list_pods(service) if not p.deleting and p.phase == "Running"]
    if not pods:
        return Injection(NAME, service, False, now_iso(), error="no running pods")
    at = now_iso()
    original, throttled = {}, []
    for pod in pods:
        original[pod.name] = pod.resources
        for container, res in pod.resources.items():
            requests = dict(res.get("requests", {}))
            limits = dict(res.get("limits", {}))
            requests["cpu"] = THROTTLED_CPU          # requests must stay <= limits
            limits["cpu"] = THROTTLED_CPU
            cluster.resize_pod(pod.name, container, {"requests": requests, "limits": limits})
        cluster.annotate_pod(pod.name, {MARK: NAME})
        throttled.append(pod.name)
    return Injection(NAME, service, True, at, target=",".join(throttled),
                     details={"pods": throttled, "cpu_limit": THROTTLED_CPU, "original": original})


def still_active(cluster, injection: Injection) -> bool:
    for pod in cluster.list_pods(injection.service):
        if pod.name in injection.details.get("pods", []) and not pod.deleting:
            for res in pod.resources.values():
                if res.get("limits", {}).get("cpu") == injection.details["cpu_limit"]:
                    return True
    return False


def reverse(cluster, injection: Injection) -> dict:
    restored = []
    live = {p.name: p for p in cluster.list_pods(injection.service)}
    for name, containers in injection.details.get("original", {}).items():
        pod = live.get(name)
        if pod is None or pod.deleting:
            continue
        for container, res in containers.items():
            if pod.resources.get(container, {}).get("limits", {}).get("cpu") != res.get("limits", {}).get("cpu"):
                cluster.resize_pod(name, container, res)
                restored.append(name)
        cluster.annotate_pod(name, {MARK: None})
    return {"restored_pods": restored}
