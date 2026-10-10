"""
Decision engine: fault type -> remediation plan, filtered through guardrails and
scored for confidence.

Guardrails
  G1  duplicate     — never start a second remediation on a service that is
                      already being remediated (by this or another process)
  G2  replica safety — never take a serving replica away (pod_restart /
                      traffic_reroute) when <= 1 replica is Ready; use a
                      surge-based rollout instead
  G3  failure memory — if the chosen remediator failed on this service in the
                      last 5 minutes, try the fallback first
  G4  cascade       — with >= 2 remediations already in flight, only the
                      highest business-priority service may proceed now

Confidence = smoothed historical success rate (per service x remediator x
fault type, from SQLite) x RCA confidence x (1 - 0.3 x blast risk). Below
CONFIDENCE_FLOOR the engine escalates to the fallback if that scores better.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from novasurge import state_db, topology
from novasurge.remediators import REMOVES_CAPACITY

DECISION_MAP: dict[str, list[str]] = {
    "pod_crash":          ["hpa_scaleout", "rolling_restart"],
    "pod_unready":        ["pod_restart", "rolling_restart"],
    "oom_kill":           ["resource_restore", "rolling_restart"],
    "cpu_throttle":       ["resource_restore", "rolling_restart"],
    "network_partition":  ["network_policy_rollback", "rolling_restart"],
    "replica_exhaustion": ["hpa_scaleout", "resource_restore"],
    "high_latency":       ["traffic_reroute", "rolling_restart"],
    "error_spike":        ["rolling_restart", "hpa_scaleout"],
    "cache_miss_spike":   ["cache_flush", "hpa_scaleout"],
    "unknown":            ["rolling_restart", "hpa_scaleout"],
}

PRIOR_SUCCESS = 0.7
PRIOR_WEIGHT = 2.0
CONFIDENCE_FLOOR = 0.4
CASCADE_THRESHOLD = 2
FAILURE_MEMORY_SECONDS = 300


@dataclass
class Guardrail:
    id: str
    outcome: str
    detail: str


@dataclass
class Decision:
    service: str
    anomaly_type: str
    priority: float
    action: str               # remediator name, or BLOCKED / DEFERRED
    fallback: str | None
    confidence: float
    guardrails: list[Guardrail] = field(default_factory=list)
    reasoning: list[str] = field(default_factory=list)

    @property
    def actionable(self) -> bool:
        return self.action not in {"BLOCKED", "DEFERRED"}

    def to_dict(self) -> dict:
        return asdict(self)


def historical_success(service: str, remediator: str, anomaly_type: str) -> tuple[float, int]:
    rate, n = state_db.success_rate(service, remediator, anomaly_type)
    successes = (rate or 0.0) * n
    return (successes + PRIOR_SUCCESS * PRIOR_WEIGHT) / (n + PRIOR_WEIGHT), n


def blast_risk(service: str) -> float:
    return min(len(topology.upstream_closure(service)) / 4.0, 1.0)


def confidence_for(service: str, remediator: str, anomaly_type: str, rca_confidence: float) -> tuple[float, str]:
    hist, n = historical_success(service, remediator, anomaly_type)
    risk = blast_risk(service)
    conf = max(0.0, min(hist * rca_confidence * (1 - 0.3 * risk), 1.0))
    basis = (f"history {hist:.2f} over {n} attempt(s)" if n else f"prior {hist:.2f} (no history yet)")
    return round(conf, 3), f"{basis} x RCA {rca_confidence:.2f} x blast factor {1 - 0.3 * risk:.2f}"


def decide(service: str, anomaly_type: str, severity: float, rca_confidence: float, ready_replicas: int,
           *, owner: str, campaign_id: str | None = None, round_num: int | None = None,
           unready_replicas: int = 0) -> Decision:
    impact = topology.BUSINESS_IMPACT.get(service, 5)
    priority = round(impact * severity, 3)
    plan = list(DECISION_MAP.get(anomaly_type, DECISION_MAP["unknown"]))
    primary, fallback = plan[0], (plan[1] if len(plan) > 1 else None)
    d = Decision(service, anomaly_type, priority, primary, fallback, 0.0)
    d.reasoning.append(f"{service}: {anomaly_type.replace('_', ' ')} at severity {severity:.2f}; business impact "
                       f"{impact}/10 -> priority {priority:.2f}. Playbook: {primary}, fallback {fallback}.")

    def guard(gid: str, outcome: str, detail: str) -> None:
        d.guardrails.append(Guardrail(gid, outcome, detail))
        d.reasoning.append(f"{gid} {outcome}: {detail}")
        state_db.record_guardrail(campaign_id, round_num, gid, service, outcome, detail)

    # G1 — duplicate remediation
    active = state_db.active_remediations()
    if service in active and active[service].get("owner") != owner:
        guard("G1", "BLOCKED", f"{service} is already being remediated with {active[service]['remediator']} "
                               f"by {active[service].get('owner')}")
        d.action = "BLOCKED"
        return d

    # G4 — cascade protection
    others = {s: v for s, v in active.items() if s != service}
    if len(others) >= CASCADE_THRESHOLD:
        top = max(others, key=lambda s: topology.BUSINESS_IMPACT.get(s, 5))
        if topology.BUSINESS_IMPACT.get(top, 5) > impact:
            guard("G4", "DEFERRED", f"{len(others)} remediations in flight ({', '.join(others)}); "
                                    f"{top} outranks {service}, retry in 30s")
            d.action = "DEFERRED"
            return d
        guard("G4", "PROCEED", f"{len(others)} remediations in flight but {service} has the highest priority")

    # G2 — replica safety (replacing a pod that is not serving costs no capacity)
    if primary in REMOVES_CAPACITY and ready_replicas <= 1 and unready_replicas == 0:
        guard("G2", "SWITCHED", f"{primary} would remove the only Ready replica "
                                f"({ready_replicas} Ready); using a surge rollout instead")
        primary, fallback = "rolling_restart", primary if primary != "rolling_restart" else fallback

    # G3 — recent failure memory
    if state_db.recently_failed(service, primary, FAILURE_MEMORY_SECONDS) and fallback:
        guard("G3", "SWITCHED", f"{primary} failed on {service} within the last "
                                f"{FAILURE_MEMORY_SECONDS // 60} minutes; trying {fallback} first")
        primary, fallback = fallback, primary

    conf, basis = confidence_for(service, primary, anomaly_type, rca_confidence)
    d.reasoning.append(f"Confidence in {primary}: {conf:.2f} ({basis}).")
    if conf < CONFIDENCE_FLOOR and fallback:
        alt, alt_basis = confidence_for(service, fallback, anomaly_type, rca_confidence)
        if alt > conf:
            d.reasoning.append(f"{conf:.2f} is below the {CONFIDENCE_FLOOR} floor and {fallback} scores "
                               f"{alt:.2f} ({alt_basis}); escalating to {fallback}.")
            primary, fallback, conf = fallback, primary, alt

    d.action, d.fallback, d.confidence = primary, fallback, conf
    d.reasoning.append(f"Decision: {primary} on {service} (fallback {fallback}, confidence {conf:.2f}).")
    return d
