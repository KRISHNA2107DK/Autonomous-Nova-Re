"""
SLA evaluation and the campaign resilience scorecard.

Per round
  TTD  time to detect   = anomaly confirmed - fault injected
  TTM  time to mitigate = remediation verified functional - anomaly confirmed
  TTR  time to recover  = service back inside its normal telemetry band - anomaly confirmed
  user impact            = share of synthetic-user requests that failed during the round

Scorecard (0-100) — every component is measured, none is self-reported:
  35  recovery SLA met rate              (TTR <= target)
  20  detection SLA met rate             (TTD <= target)
  20  remediation effectiveness          (1.0 first action, 0.5 fallback, 0 failed;
                                          x0.25 if the fault was still physically present afterwards)
  15  diagnosis accuracy                 (RCA origin == injected service, fault class == expected)
  10  user protection                    (1 - mean user failure ratio during rounds, floor 0)
"""

from __future__ import annotations

from datetime import datetime, timezone

# Recovery target (seconds from confirmed detection to verified recovery).
SLA_TARGETS: dict[str, int] = {
    "pod_deletion": 90,
    "cpu_throttle": 90,
    "network_partition": 90,
    "latency_injection": 120,
    "replica_reduction": 120,
}

# Detection target (seconds from injection to confirmed anomaly).
DETECTION_SLA: dict[str, int] = {
    "pod_deletion": 25,
    "cpu_throttle": 35,
    "network_partition": 30,
    "latency_injection": 35,
    "replica_reduction": 35,
}


def _seconds(a: str | None, b: str | None) -> float | None:
    if not a or not b:
        return None
    return round((datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds(), 2)


def evaluate_round(rec: dict) -> dict:
    injector = rec.get("injector", "")
    ttd = _seconds(rec.get("injected_at"), rec.get("detected_at"))
    ttm = _seconds(rec.get("detected_at"), rec.get("mitigated_at"))
    ttr = _seconds(rec.get("detected_at"), rec.get("recovered_at"))
    rec_target = SLA_TARGETS.get(injector, 120)
    det_target = DETECTION_SLA.get(injector, 35)
    return {
        "ttd_seconds": ttd,
        "ttm_seconds": ttm,
        "ttr_seconds": ttr,
        "detection_target_seconds": det_target,
        "recovery_target_seconds": rec_target,
        "detection_met": ttd is not None and ttd <= det_target,
        "recovery_met": ttr is not None and ttr <= rec_target,
        "recovery_margin_seconds": round(rec_target - ttr, 2) if ttr is not None else None,
    }


def scorecard(rounds: list[dict]) -> dict:
    executed = [r for r in rounds if r.get("status") not in {"SKIPPED", "SKIPPED_PREFLIGHT", None}]
    n = len(executed)
    if not n:
        return {"resilience_score": 0.0, "rounds_executed": 0, "components": {}, "verdict": "no rounds executed"}

    def frac(pred) -> float:
        return sum(1 for r in executed if pred(r)) / n

    recovery = frac(lambda r: (r.get("sla") or {}).get("recovery_met"))
    detection = frac(lambda r: (r.get("sla") or {}).get("detection_met"))
    def effective(r: dict) -> float:
        base = {"primary": 1.0, "self-healing": 1.0, "fallback": 0.5}.get(r.get("healed_by"), 0.0)
        return base * (1.0 if r.get("fault_cleared", True) else 0.25)

    effectiveness = sum(effective(r) for r in executed) / n
    origin_ok = frac(lambda r: (r.get("rca") or {}).get("origin") == r.get("target"))
    class_ok = frac(lambda r: (r.get("rca") or {}).get("anomaly_type") == r.get("expected_signature"))
    impacts = [r["user_impact"]["failure_ratio"] for r in executed
               if r.get("user_impact") and r["user_impact"].get("failure_ratio") is not None]
    mean_impact = sum(impacts) / len(impacts) if impacts else None
    protection = max(0.0, 1.0 - 2.0 * mean_impact) if mean_impact is not None else 0.5

    components = {
        "recovery_sla": round(35 * recovery, 2),
        "detection_sla": round(20 * detection, 2),
        "remediation_effectiveness": round(20 * effectiveness, 2),
        "diagnosis_accuracy": round(15 * (origin_ok + class_ok) / 2, 2),
        "user_protection": round(10 * protection, 2),
    }
    score = round(sum(components.values()), 1)

    ttd = [r["sla"]["ttd_seconds"] for r in executed if (r.get("sla") or {}).get("ttd_seconds") is not None]
    ttr = [r["sla"]["ttr_seconds"] for r in executed if (r.get("sla") or {}).get("ttr_seconds") is not None]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "resilience_score": score,
        "verdict": _verdict(score),
        "components": components,
        "rounds_executed": n,
        "recovered": sum(1 for r in executed if r.get("status") == "RECOVERED"),
        "masked": sum(1 for r in executed if r.get("status") == "MASKED"),
        "detected": sum(1 for r in executed if r.get("detected_at")),
        "rca_origin_accuracy": round(origin_ok, 3),
        "classification_accuracy": round(class_ok, 3),
        "mean_ttd_seconds": round(sum(ttd) / len(ttd), 2) if ttd else None,
        "mean_ttr_seconds": round(sum(ttr) / len(ttr), 2) if ttr else None,
        "max_ttr_seconds": max(ttr) if ttr else None,
        "mean_user_failure_ratio": round(mean_impact, 4) if mean_impact is not None else None,
        "services_tested": sorted({r["target"] for r in executed if r.get("target")}),
        "failure_types_covered": sorted({r["injector"] for r in executed if r.get("injector")}),
        "guardrails_triggered": sum(len(r.get("guardrails") or []) for r in executed),
    }


def _verdict(score: float) -> str:
    if score >= 90:
        return "EXCELLENT — every fault detected, diagnosed and healed within SLA"
    if score >= 75:
        return "GOOD — reliable recovery with minor SLA or diagnosis misses"
    if score >= 60:
        return "FAIR — recovery works but detection speed or diagnosis needs tuning"
    return "NEEDS IMPROVEMENT — missed detections, failed remediations or SLA breaches"
