"""Chaos Planner agent: candidate facts, recency, LLM choice validation and fallback (no real API calls)."""

from datetime import datetime, timedelta, timezone

from novasurge import llm, state_db
from novasurge.chaos import planner
from novasurge.chaos.planner import ChaosPlanner, build_candidates


def _record(injector, target, minutes_ago, status="RECOVERED"):
    at = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()
    state_db.save_round("hist", {"round": abs(hash((injector, target, minutes_ago))) % 10**6, "injector": injector,
                                 "target": target, "status": status, "injected_at": at, "detected_at": at,
                                 "sla": {"recovery_met": True}, "diagnosis_correct": True})


def test_candidates_cover_applicable_pairs_and_skip_used_ones(world):
    cluster, _ = world
    cands = build_candidates(cluster, [("cpu_throttle", "payment-service")])
    pairs = {(c.injector, c.service) for c in cands}
    assert ("cpu_throttle", "payment-service") not in pairs
    assert ("replica_reduction", "notification-service") not in pairs      # not applicable (min 1 replica)
    assert ("network_partition", "api-gateway") in pairs
    assert [c.id for c in cands] == list(range(1, len(cands) + 1))


def test_recently_tried_pair_ranks_below_never_tried(world):
    cluster, _ = world
    _record("network_partition", "product-service", minutes_ago=2)
    cands = {(c.injector, c.service): c for c in build_candidates(cluster, [])}
    recent = cands[("network_partition", "product-service")]
    assert 1.9 < recent.minutes_since_last_tried < 3
    assert recent.times_tried == 1
    assert recent.score_parts["staleness"] < cands[("network_partition", "payment-service")].score_parts["staleness"]


def test_failed_last_attempt_raises_priority(world):
    cluster, _ = world
    _record("latency_injection", "order-service", minutes_ago=5, status="FAILED")
    c = {(c.injector, c.service): c for c in build_candidates(cluster, [])}[("latency_injection", "order-service")]
    assert c.last_outcome == "failed" and c.score_parts["weakness"] > 0


def test_llm_choice_is_used_when_valid(world, monkeypatch):
    cluster, _ = world
    monkeypatch.setattr(llm, "chat_json", lambda system, user, **kw: ({"candidate_id": 3, "reason": "test"}, "fake/m"))
    d = ChaosPlanner().decide(cluster, [], 1, 5)
    cands = build_candidates(cluster, [])
    assert d.decided_by == "llm" and d.model == "fake/m"
    assert (d.injector, d.target) == (cands[2].injector, cands[2].service)


def test_invalid_or_failed_llm_falls_back_to_rules(world, monkeypatch):
    cluster, _ = world
    top = build_candidates(cluster, [])[0]
    monkeypatch.setattr(llm, "chat_json", lambda *a, **kw: ({"candidate_id": 999}, "fake/m"))
    d = ChaosPlanner().decide(cluster, [], 1, 5)
    assert d.decided_by == "rules" and "outside the candidate list" in d.fallback_reason
    assert (d.injector, d.target) == (top.injector, top.service)

    def boom(*a, **kw):
        raise llm.LLMUnavailable("groq rate limit reached (HTTP 429)")
    monkeypatch.setattr(llm, "chat_json", boom)
    d = ChaosPlanner().decide(cluster, [], 1, 5)
    assert d.decided_by == "rules" and "429" in d.fallback_reason


def test_no_key_means_no_call(world, monkeypatch):
    monkeypatch.setenv("NOVASURGE_LLM_PROVIDER", "none")
    assert llm.load_config() is None
    assert planner.ChaosPlanner().decide(world[0], [], 1, 5).decided_by == "rules"
