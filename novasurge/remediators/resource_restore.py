"""
resource_restore — reconcile CPU/memory to the declared baseline.

  1. Deployment template: patched back if it drifted (triggers a safe rollout).
  2. Running pods: resized in place if their live resources drifted, so the fix
     takes effect in seconds without restarting healthy processes.
"""

from __future__ import annotations

import time

from novasurge.remediators import (RemediationContext, RemediationResult, baseline_resources,
                                   deployment_converged, now_iso, wait_until)

NAME = "resource_restore"


def _cpu_mem(res: dict) -> tuple:
    return (res.get("requests", {}).get("cpu"), res.get("limits", {}).get("cpu"),
            res.get("requests", {}).get("memory"), res.get("limits", {}).get("memory"))


async def remediate(service: str, ctx: RemediationContext) -> RemediationResult:
    started, t0 = now_iso(), time.monotonic()
    declared = baseline_resources(ctx.cluster, service)
    dep = ctx.cluster.get_deployment(service)

    template_drift = [c.name for c in dep.containers
                      if c.name in declared and _cpu_mem({"requests": c.requests, "limits": c.limits})
                      != _cpu_mem(declared[c.name])]
    if template_drift:
        ctx.cluster.patch_deployment(service, {"spec": {"template": {"spec": {"containers": [
            {"name": c, "resources": declared[c]} for c in template_drift]}}}})

    resized = []
    for pod in ctx.cluster.list_pods(service):
        if pod.deleting:
            continue
        for container, live in pod.resources.items():
            want = declared.get(container)
            if want and _cpu_mem(live) != _cpu_mem(want):
                ctx.cluster.resize_pod(pod.name, container, want)
                resized.append(f"{pod.name}/{container}")
        if pod.annotations.get("novasurge.io/chaos"):
            ctx.cluster.annotate_pod(pod.name, {"novasurge.io/chaos": None})

    def reconciled() -> bool:
        for pod in ctx.cluster.list_pods(service):
            if pod.deleting:
                continue
            for container, live in pod.resources.items():
                want = declared.get(container)
                if want and _cpu_mem(live) != _cpu_mem(want):
                    return False
        return deployment_converged(ctx.cluster, service)

    ok = await wait_until(reconciled, ctx.timeout_s, ctx.poll_s)
    if not template_drift and not resized:
        summary = "resources already match the declared baseline (nothing to restore)"
        ok = False
    else:
        parts = []
        if resized:
            parts.append(f"resized {len(resized)} container(s) in place")
        if template_drift:
            parts.append("rolled out the declared template")
        summary = " and ".join(parts) + f" to {declared}"
        if not ok:
            summary += " — not converged in time"
    return RemediationResult(NAME, service, ok, summary, started, now_iso(), time.monotonic() - t0,
                             {"declared": declared, "resized": resized, "template_drift": template_drift})
