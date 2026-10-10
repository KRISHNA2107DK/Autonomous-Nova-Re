"""
traffic_reroute — quarantine the worst replica.

Relabelling the pod's `app` label takes it out of the Service's endpoints
immediately (traffic shifts to healthy replicas) and out of its ReplicaSet,
which creates a fresh replacement. The quarantined pod is kept briefly for
forensics and then deleted to free resources.
"""

from __future__ import annotations

import asyncio
import time

from novasurge.remediators import (RemediationContext, RemediationResult, deployment_converged,
                                   note_own_action, now_iso, wait_until, worst_pod)

NAME = "traffic_reroute"
FORENSICS_SECONDS = 5


async def remediate(service: str, ctx: RemediationContext) -> RemediationResult:
    started, t0 = now_iso(), time.monotonic()
    victim, why = worst_pod(ctx, service)
    if victim is None:
        return RemediationResult(NAME, service, False, "no pods", started, now_iso(), time.monotonic() - t0)
    serving = [p for p in ctx.cluster.list_pods(service) if p.ready and not p.deleting]
    if len(serving) < 2:
        return RemediationResult(NAME, service, False,
                                 "refused: quarantining the only serving replica would cause an outage",
                                 started, now_iso(), time.monotonic() - t0)

    note_own_action([victim.name])
    ctx.cluster.patch_pod_labels(victim.name, {"app": f"{service}-quarantined",
                                               "novasurge.io/quarantined-from": service})

    ok = await wait_until(lambda: deployment_converged(ctx.cluster, service), ctx.timeout_s, ctx.poll_s)
    await asyncio.sleep(FORENSICS_SECONDS if ctx.poll_s >= 1 else 0)
    try:
        ctx.cluster.delete_pod(victim.name, grace_seconds=0)
        cleaned = True
    except Exception:  # noqa: BLE001
        cleaned = False
    ready = sorted(p.name for p in ctx.cluster.list_pods(service) if p.ready)
    summary = (f"quarantined {victim.name} ({why}); traffic now on {len(ready)} healthy replica(s)"
               if ok else f"quarantined {victim.name} but replacement not Ready within {ctx.timeout_s:.0f}s")
    return RemediationResult(NAME, service, ok, summary, started, now_iso(), time.monotonic() - t0,
                             {"quarantined_pod": victim.name, "selection": why, "ready_pods": ready,
                              "quarantined_pod_deleted": cleaned})
