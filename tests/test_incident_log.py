"""Durable incident log: live event files and the rendered per-campaign log."""

from __future__ import annotations

import json

from novasurge import config, incident_log
from novasurge.reasoning import Narrator


def test_events_are_appended_live_and_rendered(sim_home):
    cid = "c-test-incident-log"
    n = Narrator(cid, echo=False)
    n.round = 1
    n.say("INJECT", "Injected pod_deletion into payment-service", service="payment-service")
    n.say("REMEDIATE", "hpa_scaleout succeeded in 3.0s", service="payment-service")

    events_file = config.REPORTS_DIR / cid / incident_log.EVENTS_FILE
    lines = [json.loads(x) for x in events_file.read_text(encoding="utf-8").splitlines()]
    assert [e["phase"] for e in lines] == ["INJECT", "REMEDIATE"]
    assert all(e["campaign_id"] == cid and e["round"] == 1 for e in lines)

    rounds = [{"round": 1, "injector": "pod_deletion", "target": "payment-service", "status": "RECOVERED",
               "planner": {"decided_by": "rules", "reason": "never tried"},
               "decision": {"action": "hpa_scaleout", "reasoning": ["pod crash -> scale out"]},
               "remediations": [{"remediator": "hpa_scaleout", "service": "payment-service", "success": True,
                                 "verified": True, "duration_s": 3.0, "summary": "min 2 -> 3"}],
               "sla": {"ttd_seconds": 5, "ttr_seconds": 20}, "user_impact": {"failure_ratio": 0.0}}]
    path = incident_log.write(cid, rounds, {"resilience_score": 100.0, "verdict": "EXCELLENT"})
    text = path.read_text(encoding="utf-8")
    assert "Round 1 — pod_deletion → payment-service" in text
    assert "pod crash -> scale out" in text
    assert "| hpa_scaleout | payment-service | success | yes |" in text
    assert "Injected pod_deletion into payment-service" in text


def test_events_outside_a_campaign_go_to_the_autopilot_log(sim_home):
    ev = Narrator(None, echo=False).say("AUTOPILOT", "autopilot healed order-service")
    day_file = config.REPORTS_DIR / "autopilot" / f"{ev['at'][:10]}.jsonl"
    assert "autopilot healed order-service" in day_file.read_text(encoding="utf-8")
