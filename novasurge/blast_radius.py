"""
Pre-injection safety check (chaos-engineering "steady-state hypothesis").

GO only if:
  * the platform can observe the system (Prometheus up, models loaded)
  * no service is currently anomalous — injecting into an already-degraded
    system makes the experiment unattributable and risks a real outage
  * the target is at full Ready capacity
  * offered load is not abnormally high (load ratio <= 1.8x baseline)

Blast radius = services whose requests depend on the target (upstream
closure) and the share of user traffic that touches the target or them.
"""

from __future__ import annotations

from datetime import datetime, timezone

from novasurge import topology
from novasurge.ml.detector import DetectionResult
from novasurge.sla_tracker import SLA_TARGETS
from novasurge.telemetry import Snapshot

MAX_LOAD_RATIO = 1.8


def preflight(target: str, injector: str, detection: DetectionResult | None, snapshot: Snapshot | None,
              baseline_rps: float | None) -> dict:
    dependents = topology.upstream_closure(target)
    users = max(topology.USER_TRAFFIC_SHARE.get(s, 0.0) for s in [target, *dependents])
    blast_score = len(dependents)

    reasons: list[str] = []
    degraded: list[str] = []
    load_ratio = None
    target_ready = None
    if detection is None or snapshot is None:
        reasons.append("no live detection — refusing to inject blind")
    else:
        if not snapshot.prometheus_ok:
            reasons.append("Prometheus unreachable — refusing to inject blind")
        degraded = [s for s, d in detection.services.items() if d.confirmed or d.window_anomalous]
        if degraded:
            reasons.append(f"steady state not met: {', '.join(degraded)} currently anomalous")
        st = snapshot.services.get(target)
        if st is not None:
            target_ready = f"{st.ready_replicas}/{st.desired_replicas}"
            if st.desired_replicas and st.ready_replicas < st.desired_replicas:
                reasons.append(f"{target} is below full capacity ({target_ready} Ready)")
            rps = st.features.get("request_rate")
            if rps is not None and baseline_rps:
                load_ratio = round(rps / baseline_rps, 2)
                if load_ratio > MAX_LOAD_RATIO:
                    reasons.append(f"load is {load_ratio}x baseline — too risky")

    healthy_pct = round(100.0 * (len(topology.SERVICES) - len(degraded)) / len(topology.SERVICES), 1)
    risk_points = (2 if users >= 0.75 else 1 if users >= 0.35 else 0) + (1 if blast_score >= 2 else 0)
    risk = "HIGH" if risk_points >= 3 else "MEDIUM" if risk_points >= 1 else "LOW"
    return {
        "target": target,
        "injector": injector,
        "dependents": dependents,
        "blast_score": blast_score,
        "estimated_affected_users_pct": round(users * 100),
        "business_impact": topology.BUSINESS_IMPACT.get(target, 5),
        "system_health_pct": healthy_pct,
        "target_ready": target_ready,
        "load_ratio": load_ratio,
        "injection_risk": risk,
        "go_nogo": "NO-GO" if reasons else "GO",
        "nogo_reasons": reasons,
        "sla_target_seconds": SLA_TARGETS.get(injector, 90),
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }
