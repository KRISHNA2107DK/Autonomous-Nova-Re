"""
hpa_scaleout — restore the autoscaler to (at least) its declared bounds and add
one replica of surge capacity, then wait until that capacity is Ready.

Fixes replica exhaustion (bounds clamped too low) and mitigates capacity loss.
The surge is handed back to the autoscaler at round teardown.
"""

from __future__ import annotations

import time

from novasurge.remediators import (RemediationContext, RemediationResult, baseline_hpa, now_iso,
                                   wait_until)

NAME = "hpa_scaleout"


async def remediate(service: str, ctx: RemediationContext) -> RemediationResult:
    started, t0 = now_iso(), time.monotonic()
    name = f"{service}-hpa"
    hpa = ctx.cluster.get_hpa(name)
    dep = ctx.cluster.get_deployment(service)
    base = baseline_hpa(ctx.cluster, service)
    new_max = max(base["maxReplicas"], hpa.max_replicas)
    new_min = min(max(base["minReplicas"], dep.ready_replicas) + 1, new_max)
    ctx.cluster.patch_hpa(name, {"spec": {"minReplicas": new_min, "maxReplicas": new_max}})

    def scaled() -> bool:
        d = ctx.cluster.get_deployment(service)
        ready = [p for p in ctx.cluster.list_pods(service) if p.ready and not p.deleting]
        return d.ready_replicas >= new_min and len(ready) >= new_min

    ok = await wait_until(scaled, ctx.timeout_s, ctx.poll_s)
    final = ctx.cluster.get_deployment(service)
    summary = (f"autoscaler {hpa.min_replicas}-{hpa.max_replicas} -> {new_min}-{new_max}; "
               f"{dep.ready_replicas} -> {final.ready_replicas} Ready replicas")
    if not ok:
        summary += f" (target {new_min} not reached within {ctx.timeout_s:.0f}s)"
    return RemediationResult(NAME, service, ok, summary, started, now_iso(), time.monotonic() - t0, {
        "hpa_before": {"minReplicas": hpa.min_replicas, "maxReplicas": hpa.max_replicas},
        "hpa_after": {"minReplicas": new_min, "maxReplicas": new_max},
        "declared": base,
        "ready_before": dep.ready_replicas,
        "ready_after": final.ready_replicas,
    })
