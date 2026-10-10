"""
rolling_restart — re-roll every replica from the declared pod template
(maxUnavailable=0, so capacity never drops). Clears any per-pod drift: live
resizes, injected qdiscs, wedged processes.
"""

from __future__ import annotations

import time

from novasurge.remediators import (RemediationContext, RemediationResult, deployment_converged,
                                   note_own_action, now_iso, wait_until)

NAME = "rolling_restart"


async def remediate(service: str, ctx: RemediationContext) -> RemediationResult:
    started, t0 = now_iso(), time.monotonic()
    before = {p.name for p in ctx.cluster.list_pods(service) if not p.deleting}
    note_own_action(sorted(before))
    ctx.cluster.patch_deployment(service, {"spec": {"template": {"metadata": {"annotations": {
        "novasurge.io/restarted-at": started}}}}})

    def rolled() -> bool:
        live = {p.name for p in ctx.cluster.list_pods(service) if not p.deleting}
        return not (live & before) and deployment_converged(ctx.cluster, service)

    ok = await wait_until(rolled, ctx.timeout_s * 1.5, ctx.poll_s)
    after = sorted(p.name for p in ctx.cluster.list_pods(service) if p.ready)
    summary = (f"rolled {len(before)} replica(s) onto the declared template" if ok
               else f"rollout did not complete within {ctx.timeout_s * 1.5:.0f}s")
    return RemediationResult(NAME, service, ok, summary, started, now_iso(), time.monotonic() - t0,
                             {"replaced": sorted(before), "ready_pods": after})
