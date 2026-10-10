"""
latency_injection — add 200ms +/- 50ms (normal) egress delay on eth0 of ONE
replica with `tc netem` (container has iproute2 + NET_ADMIN).

Every packet leaving that pod is delayed: responses to callers and the pod's
own calls to Postgres / Redis / other services. Server-side latency of that
replica climbs (its dependency calls slow down) and callers see the delay on
top. The delay is sized so the replica stays Ready (its readiness probe still
answers within its timeout): a slow-but-serving replica, the hard case.
Only one replica is degraded, so the right fix is to take that replica out of
rotation — not to scale or restart everything.
"""

from __future__ import annotations

import os
import random

from novasurge.chaos.injectors import Injection, now_iso

NAME = "latency_injection"
DESCRIPTION = "tc netem egress delay on one replica"
EXPECTED_SIGNATURE = "high_latency"
DELAY = os.environ.get("NOVASURGE_NETEM_DELAY", "200ms")
JITTER = os.environ.get("NOVASURGE_NETEM_JITTER", "50ms")


def compatible(cluster, service: str) -> tuple[bool, str]:
    ready = [p for p in cluster.list_pods(service) if p.ready and not p.deleting]
    if not ready:
        return False, "no Ready pods"
    probe = cluster.exec(ready[0].name, ["tc", "qdisc", "show", "dev", "eth0"], timeout=10)
    if not probe.ok:
        return False, f"tc unavailable in container: {probe.stderr.strip()[:120]}"
    return True, "tc available"


def inject(cluster, service: str) -> Injection:
    ready = [p for p in cluster.list_pods(service) if p.ready and not p.deleting]
    if not ready:
        return Injection(NAME, service, False, now_iso(), error="no Ready pods")
    pod = random.choice(ready)
    cmd = ["tc", "qdisc", "replace", "dev", "eth0", "root", "netem",
           "delay", DELAY, JITTER, "distribution", "normal"]
    at = now_iso()
    res = cluster.exec(pod.name, cmd, timeout=15)
    if not res.ok:
        return Injection(NAME, service, False, at, target=pod.name,
                         error=f"tc failed (rc={res.returncode}): {res.stderr.strip()[:200]}")
    return Injection(NAME, service, True, at, target=pod.name,
                     details={"pod": pod.name, "delay": DELAY, "jitter": JITTER,
                              "command": " ".join(cmd), "replicas_ready": len(ready)})


def still_active(cluster, injection: Injection) -> bool:
    pods = {p.name: p for p in cluster.list_pods()}
    pod = pods.get(injection.target)
    if pod is None or pod.deleting:
        return False
    if pod.labels.get("app") != injection.service:
        return False   # quarantined: no longer serving traffic
    res = cluster.exec(pod.name, ["tc", "qdisc", "show", "dev", "eth0"], timeout=10)
    return res.ok and "netem" in res.stdout


def reverse(cluster, injection: Injection) -> dict:
    pods = {p.name for p in cluster.list_pods()}
    if injection.target not in pods:
        return {"pod": injection.target, "note": "pod no longer exists (replaced)"}
    res = cluster.exec(injection.target, ["tc", "qdisc", "del", "dev", "eth0", "root"], timeout=10)
    return {"pod": injection.target, "removed": res.ok,
            "note": res.stderr.strip()[:120] if not res.ok else "netem qdisc deleted"}
