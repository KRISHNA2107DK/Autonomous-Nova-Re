"""End-to-end: a full 5-round campaign on the simulator, plus the HTTP API."""

from fastapi.testclient import TestClient

from novasurge import sim, state_db
from novasurge.sla_tracker import evaluate_round, scorecard
from tests.conftest import run


def test_full_campaign_dry_run(trained_models):
    from novasurge.orchestrator import DEFAULT_PLAN
    state_db.reset_runtime(history=True)
    report = run(sim.run_campaign(DEFAULT_PLAN, echo=False, isolate=False))
    rounds = state_db.get_rounds(report["campaign_id"])
    assert len(rounds) == 5
    assert all(r["status"] == "RECOVERED" for r in rounds), [(r["round"], r["status"]) for r in rounds]
    assert report["rca_origin_accuracy"] == 1.0
    assert report["classification_accuracy"] == 1.0
    assert report["resilience_score"] >= 90
    # the strategy spreads the campaign across services
    assert len(report["services_tested"]) >= 4


def test_sla_math():
    rec = {"injector": "cpu_throttle", "injected_at": "2026-01-01T00:00:00+00:00",
           "detected_at": "2026-01-01T00:00:12+00:00", "mitigated_at": "2026-01-01T00:00:20+00:00",
           "recovered_at": "2026-01-01T00:00:50+00:00"}
    sla = evaluate_round(rec)
    assert sla["ttd_seconds"] == 12 and sla["ttm_seconds"] == 8 and sla["ttr_seconds"] == 38
    assert sla["detection_met"] and sla["recovery_met"]


def test_scorecard_penalises_masked_and_wrong_diagnoses():
    good = {"status": "RECOVERED", "target": "a", "expected_signature": "x", "healed_by": "primary",
            "fault_cleared": True, "rca": {"origin": "a", "anomaly_type": "x"},
            "sla": {"recovery_met": True, "detection_met": True, "ttd_seconds": 5, "ttr_seconds": 30},
            "user_impact": {"failure_ratio": 0.0}}
    masked = good | {"status": "MASKED", "fault_cleared": False, "rca": {"origin": "b", "anomaly_type": "y"}}
    assert scorecard([good])["resilience_score"] == 100.0
    worse = scorecard([good, masked])
    assert worse["resilience_score"] < 90
    assert worse["rca_origin_accuracy"] == 0.5


def test_api_endpoints(trained_models):
    from novasurge.api.server import create_app
    with TestClient(create_app(autopilot=False, start_monitor=False)) as client:
        assert client.get("/api/health").json()["status"] == "ok"
        assert client.get("/health").status_code == 200           # legacy alias
        assert isinstance(client.get("/api/events").json(), list)
        assert isinstance(client.get("/api/campaigns").json(), list)
        topo = client.get("/api/topology").json()
        assert len(topo["nodes"]) == 5 and topo["edges"]
        r = client.post("/api/chaos/inject", json={"injector": "nope", "service": "x"})
        assert r.status_code == 400
        assert client.post("/api/autopilot", json={"enabled": True}).json() == {"autopilot": True}
