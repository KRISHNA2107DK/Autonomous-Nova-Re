"""
Chaos Planner agent — decides WHICH fault to inject into WHICH service.

1. Candidates: every (fault, service) pair whose injector is applicable right now.
2. Facts per candidate, all measured or derived from the real topology:
     dependents (who breaks if it breaks), dependencies, business impact,
     share of user traffic, minutes since this exact pair was last injected
     (SQLite history across all campaigns), times tried, last outcome.
3. Rule-based score (always computed, the fallback):
     0.30 staleness   never tried = 1.0, else log-scaled up to 24 h
   + 0.20 blast       dependents / 4
   + 0.15 weakness    last attempt undetected / failed / missed SLA / wrong diagnosis
   + 0.15 impact      business impact / 10
   + 0.10 users       user traffic share
   + 0.10 deps        dependencies / 4
   - 0.40 same fault already used this campaign, - 0.25 same service already hit
   (a pair already used in this campaign is never offered again)
4. The LLM agent receives the top candidates with those facts and returns
   {"candidate_id", "reason"}. Its answer is validated against the offered list;
   no key, an API error, a rate limit or an invalid answer -> the top rule-based pick.
One LLM call per round.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from novasurge import llm, state_db, topology
from novasurge.chaos.injectors import REGISTRY as INJECTORS

log = logging.getLogger("novasurge.planner")

TOP_K = 10
STALE_FULL_HOURS = 24.0

SYSTEM_PROMPT = """You are the Chaos Planner of NovaSurge, an autonomous chaos-engineering platform for a
Kubernetes e-commerce application. Each round you choose ONE fault to inject into ONE service.
Choose to maximise what the experiment teaches about the system's resilience:
- prefer (fault, service) pairs never tried or not tried for a long time;
- prefer services that many others depend on, or that carry high business impact / user traffic;
- prefer pairs whose last attempt went badly (undetected, failed recovery, SLA missed, wrong diagnosis);
- keep variety inside a campaign: avoid repeating a fault type or a service already used this campaign;
- you may only choose from the candidate list; ids not in the list are invalid.
Reply with a JSON object only: {"candidate_id": <int>, "reason": "<one sentence, at most 40 words>"}"""


@dataclass
class Candidate:
    id: int
    injector: str
    service: str
    fault: str
    dependents: list[str]
    depends_on: list[str]
    business_impact: int
    user_traffic_share: float
    minutes_since_last_tried: float | None
    times_tried: int
    last_outcome: str | None
    rule_score: float
    score_parts: dict = field(default_factory=dict)

    def for_llm(self) -> dict:
        return {
            "id": self.id, "fault": self.injector, "service": self.service, "what_it_does": self.fault,
            "dependents": self.dependents, "depends_on": self.depends_on,
            "business_impact_1_to_10": self.business_impact, "user_traffic_share": self.user_traffic_share,
            "minutes_since_last_tried": None if self.minutes_since_last_tried is None
            else round(self.minutes_since_last_tried, 1),
            "times_tried": self.times_tried, "last_outcome": self.last_outcome,
            "rule_score": round(self.rule_score, 3),
        }


@dataclass
class PlanDecision:
    injector: str
    target: str
    decided_by: str            # "llm" | "rules"
    model: str | None
    reason: str
    fallback_reason: str | None
    candidates: list[dict]

    def to_dict(self) -> dict:
        return asdict(self)


def _outcome(h: dict | None) -> str | None:
    if not h:
        return None
    if not h.get("last_detected"):
        return "undetected"
    if h.get("last_status") not in ("RECOVERED",):
        return (h.get("last_status") or "unknown").lower()
    if h.get("last_recovery_met") is False:
        return "recovered_but_missed_sla"
    if h.get("last_diagnosis_correct") is False:
        return "recovered_but_misdiagnosed"
    return "recovered_within_sla"


def _weakness(outcome: str | None) -> float:
    return {None: 0.0, "recovered_within_sla": 0.0, "recovered_but_missed_sla": 0.6,
            "recovered_but_misdiagnosed": 0.7, "masked": 0.8}.get(outcome, 1.0)


def build_candidates(cluster, chosen: list[tuple[str, str]], now: datetime | None = None) -> list[Candidate]:
    now = now or datetime.now(timezone.utc)
    history = state_db.fault_history()
    used_faults = {f for f, _ in chosen}
    used_services = {s for _, s in chosen}
    out: list[Candidate] = []
    for name, mod in INJECTORS.items():
        for svc in topology.SERVICES:
            if (name, svc) in chosen:
                continue
            try:
                ok, _why = mod.compatible(cluster, svc)
            except Exception as exc:  # noqa: BLE001 - an unreachable pod makes the pair ineligible
                log.debug("compatible(%s, %s) failed: %s", name, svc, exc)
                ok = False
            if not ok:
                continue
            h = history.get((name, svc))
            minutes = None
            if h and h.get("last_at"):
                minutes = (now - datetime.fromisoformat(h["last_at"])).total_seconds() / 60.0
            staleness = 1.0 if minutes is None else min(
                1.0, math.log1p(minutes / 60.0) / math.log1p(STALE_FULL_HOURS))
            dependents = topology.upstream_closure(svc)
            deps = topology.downstream_closure(svc)
            outcome = _outcome(h)
            parts = {
                "staleness": 0.30 * staleness,
                "blast": 0.20 * len(dependents) / 4.0,
                "weakness": 0.15 * _weakness(outcome),
                "impact": 0.15 * topology.BUSINESS_IMPACT.get(svc, 5) / 10.0,
                "users": 0.10 * topology.USER_TRAFFIC_SHARE.get(svc, 0.0),
                "deps": 0.10 * len(deps) / 4.0,
                "variety": -(0.40 if name in used_faults else 0.0) - (0.25 if svc in used_services else 0.0),
            }
            out.append(Candidate(
                id=0, injector=name, service=svc, fault=mod.DESCRIPTION, dependents=dependents, depends_on=deps,
                business_impact=topology.BUSINESS_IMPACT.get(svc, 5),
                user_traffic_share=topology.USER_TRAFFIC_SHARE.get(svc, 0.0),
                minutes_since_last_tried=minutes, times_tried=h["count"] if h else 0, last_outcome=outcome,
                rule_score=sum(parts.values()), score_parts={k: round(v, 3) for k, v in parts.items()}))
    out.sort(key=lambda c: (-c.rule_score, c.injector, c.service))
    for i, c in enumerate(out, start=1):
        c.id = i
    return out


class ChaosPlanner:
    def __init__(self, use_llm: bool = True):
        self.use_llm = use_llm

    def decide(self, cluster, chosen: list[tuple[str, str]], round_num: int, total_rounds: int,
               system_health: dict | None = None) -> PlanDecision | None:
        candidates = build_candidates(cluster, chosen)
        if not candidates:
            return None
        top = candidates[:TOP_K]
        best = top[0]
        offered = [c.for_llm() for c in top]
        fallback_reason = None
        if self.use_llm:
            try:
                answer, model = llm.chat_json(SYSTEM_PROMPT, json.dumps({
                    "round": round_num, "rounds_in_campaign": total_rounds,
                    "already_chosen_this_campaign": [{"fault": f, "service": s} for f, s in chosen],
                    "system_health": system_health or {},
                    "candidates": offered,
                }))
                pick = next((c for c in top if c.id == int(answer.get("candidate_id", -1))), None)
                if pick is None:
                    raise llm.LLMUnavailable(f"model chose an id outside the candidate list: {answer!r}"[:200])
                reason = str(answer.get("reason") or "").strip()[:300] or "no reason given"
                return PlanDecision(pick.injector, pick.service, "llm", model, reason, None, offered)
            except (llm.LLMUnavailable, ValueError, TypeError) as exc:
                fallback_reason = str(exc)
                log.info("planner falling back to rules: %s", exc)
        when = ("never tried before" if best.minutes_since_last_tried is None
                else f"last tried {best.minutes_since_last_tried:.0f} min ago")
        reason = (f"highest rule score {best.rule_score:.3f}: {when}, {len(best.dependents)} dependent service(s), "
                  f"impact {best.business_impact}/10, last outcome {best.last_outcome or 'n/a'}")
        return PlanDecision(best.injector, best.service, "rules", None, reason, fallback_reason, offered)
