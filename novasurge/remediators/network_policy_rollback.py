"""
network_policy_rollback — find NetworkPolicies that select this service's pods
and deny all traffic of a type (a policyType with no rules), excluding policies
explicitly marked as part of the baseline, and delete them.

The policies are identified by their *effect* on the affected pods, not by any
label the chaos injector set, so this works for a fat-fingered policy too.
"""

from __future__ import annotations

import time

from novasurge.cluster import pod_selector_matches
from novasurge.remediators import (RemediationContext, RemediationResult, deployment_converged,
                                   now_iso, wait_until)

NAME = "network_policy_rollback"
BASELINE_LABEL = "novasurge.io/baseline"


def offending_policies(cluster, service: str) -> list:
    pods = [p for p in cluster.list_pods(service) if not p.deleting]
    labels = pods[0].labels if pods else {"app": service}
    return [np_ for np_ in cluster.list_network_policies()
            if np_.labels.get(BASELINE_LABEL) != "true"
            and pod_selector_matches(np_.pod_selector, labels)
            and np_.denies_all]


async def remediate(service: str, ctx: RemediationContext) -> RemediationResult:
    started, t0 = now_iso(), time.monotonic()
    offending = offending_policies(ctx.cluster, service)
    if not offending:
        return RemediationResult(NAME, service, False, "no deny-all NetworkPolicy selects this service",
                                 started, now_iso(), time.monotonic() - t0)
    deleted = [np_.name for np_ in offending if ctx.cluster.delete_network_policy(np_.name)]

    ok = await wait_until(lambda: deployment_converged(ctx.cluster, service), ctx.timeout_s, ctx.poll_s)
    summary = f"removed {len(deleted)} isolating NetworkPolicy(ies): {', '.join(deleted)}"
    if not ok:
        summary += "; pods not all Ready yet"
    return RemediationResult(NAME, service, ok, summary, started, now_iso(), time.monotonic() - t0, {
        "deleted": deleted,
        "policies": [{"name": p.name, "selector": p.pod_selector, "types": p.policy_types,
                      "created_at": p.created_at.isoformat() if p.created_at else None} for p in offending],
    })
