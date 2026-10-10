"""pod_restart — delete the worst replica and wait for its replacement to be Ready."""

from __future__ import annotations

import time

from novasurge.remediators import (RemediationContext, RemediationResult, deployment_converged,
                                   note_own_action, now_iso, wait_until, worst_pod)

NAME = "pod_restart"


async def remediate(service: str, ctx: RemediationContext) -> RemediationResult:
    started, t0 = now_iso(), time.monotonic()
    victim, why = worst_pod(ctx, service)
    if victim is None:
        return RemediationResult(NAME, service, False, "no pods to restart", started, now_iso(),
                                 time.monotonic() - t0)
    note_own_action([victim.name])
    ctx.cluster.delete_pod(victim.name, grace_seconds=5)

    def replaced() -> bool:
        names = {p.name for p in ctx.cluster.list_pods(service) if not p.deleting}
        return victim.name not in names and deployment_converged(ctx.cluster, service)

    ok = await wait_until(replaced, ctx.timeout_s, ctx.poll_s)
    new = sorted(p.name for p in ctx.cluster.list_pods(service) if p.ready)
    summary = (f"restarted {victim.name} ({why}); replacement Ready" if ok
               else f"restarted {victim.name} but replacement not Ready within {ctx.timeout_s:.0f}s")
    return RemediationResult(NAME, service, ok, summary, started, now_iso(), time.monotonic() - t0,
                             {"deleted_pod": victim.name, "selection": why, "ready_pods": new})
