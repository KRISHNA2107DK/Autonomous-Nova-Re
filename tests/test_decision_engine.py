"""Guardrails and confidence scoring."""

from novasurge import state_db
from novasurge.decision_engine import DECISION_MAP, decide


def test_every_fault_class_has_a_playbook_with_known_remediators():
    from novasurge.remediators import REGISTRY
    for fault, plan in DECISION_MAP.items():
        assert plan and all(r in REGISTRY for r in plan), fault


def test_playbook_choice_and_confidence(world):
    d = decide("product-service", "network_partition", 0.9, 0.95, 2, owner="t1")
    assert d.action == "network_policy_rollback" and d.fallback == "rolling_restart"
    assert 0 < d.confidence <= 1
    assert d.priority == round(6 * 0.9, 3)


def test_g1_blocks_duplicate_remediation_by_another_owner(world):
    state_db.mark_active("order-service", "pod_restart", owner="someone-else")
    d = decide("order-service", "pod_crash", 0.8, 0.9, 2, owner="t1")
    assert d.action == "BLOCKED"
    assert d.guardrails[0].id == "G1"


def test_g2_never_removes_the_last_serving_replica(world):
    d = decide("order-service", "high_latency", 0.8, 0.9, 1, owner="t1")
    assert d.action == "rolling_restart"
    assert any(g.id == "G2" for g in d.guardrails)
    # ...but replacing a pod that is not serving costs nothing
    d2 = decide("order-service", "pod_unready", 0.8, 0.9, 1, owner="t1", unready_replicas=1)
    assert d2.action == "pod_restart"


def test_g3_recent_failure_switches_to_fallback(world):
    rid = state_db.record_remediation_attempt(None, None, "payment-service", "cpu_throttle", "resource_restore")
    state_db.complete_remediation(rid, False, 3.0, "did not converge")
    d = decide("payment-service", "cpu_throttle", 0.8, 0.9, 2, owner="t1")
    assert d.action == "rolling_restart"
    assert any(g.id == "G3" for g in d.guardrails)


def test_g4_defers_lower_priority_service_during_cascade(world):
    state_db.mark_active("payment-service", "hpa_scaleout", owner="other")
    state_db.mark_active("api-gateway", "rolling_restart", owner="other")
    d = decide("notification-service", "pod_crash", 0.9, 0.9, 1, owner="t1")
    assert d.action == "DEFERRED"
    assert d.guardrails[-1].id == "G4"


def test_confidence_learns_from_history(world):
    first = decide("api-gateway", "error_spike", 0.8, 0.9, 2, owner="t1").confidence
    for _ in range(4):
        rid = state_db.record_remediation_attempt(None, None, "api-gateway", "error_spike", "rolling_restart")
        state_db.complete_remediation(rid, True, 10.0)
    later = decide("api-gateway", "error_spike", 0.8, 0.9, 2, owner="t1").confidence
    assert later > first
