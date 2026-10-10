"""
Target selection for "auto" campaign rounds.

    score = 0.35 * dependency blast   (upstream closure size / 4)
          + 0.25 * business impact     (/10)
          + 0.20 * user traffic share
          + 0.10 * load                (current / baseline, capped at 2x, halved)
          + 0.10 * low redundancy      (1 / Ready replicas)
          - 0.60 * already targeted in this campaign (coverage)

Only services for which the injector is applicable (compatible()) are scored.
The full breakdown is returned so the decision is auditable.
"""

from __future__ import annotations

from novasurge import topology


def score_targets(injector_mod, cluster, snapshot, baseline_rps: dict[str, float],
                  already_targeted: set[str]) -> list[dict]:
    rows = []
    for svc in topology.SERVICES:
        ok, why = injector_mod.compatible(cluster, svc)
        if not ok:
            rows.append({"service": svc, "eligible": False, "reason": why, "total": None})
            continue
        st = snapshot.services.get(svc) if snapshot else None
        blast = len(topology.upstream_closure(svc)) / 4.0
        impact = topology.BUSINESS_IMPACT.get(svc, 5) / 10.0
        users = topology.USER_TRAFFIC_SHARE.get(svc, 0.0)
        rps = (st.features.get("request_rate") if st else None) or 0.0
        base = baseline_rps.get(svc) or 0.0
        load = min(rps / base, 2.0) / 2.0 if base > 0 else 0.5
        ready = max(st.ready_replicas if st else 1, 1)
        redundancy = 1.0 / ready
        coverage = 1.0 if svc in already_targeted else 0.0
        total = 0.35 * blast + 0.25 * impact + 0.20 * users + 0.10 * load + 0.10 * redundancy - 0.60 * coverage
        rows.append({
            "service": svc, "eligible": True, "reason": why,
            "blast": round(blast, 3), "impact": round(impact, 3), "users": round(users, 3),
            "load": round(load, 3), "redundancy": round(redundancy, 3), "coverage_penalty": coverage,
            "total": round(total, 4),
        })
    rows.sort(key=lambda r: (r["total"] is None, -(r["total"] or 0), topology.SERVICES.index(r["service"])))
    return rows


def select_target(injector_mod, cluster, snapshot, baseline_rps, already_targeted) -> tuple[str | None, list[dict]]:
    rows = score_targets(injector_mod, cluster, snapshot, baseline_rps, already_targeted)
    eligible = [r for r in rows if r["eligible"]]
    return (eligible[0]["service"] if eligible else None), rows
