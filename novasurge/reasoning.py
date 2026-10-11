"""
Narration: turns structured decisions into plain-English reasoning events.

Deterministic templates (no LLM, fully offline) — but every number in the text
comes from live data; nothing is a canned placeholder.
Events are persisted in SQLite, streamed to the dashboard's reasoning feed and
appended to a durable per-campaign file (see incident_log).
"""

from __future__ import annotations

import logging
import sqlite3

from novasurge import incident_log, state_db

log = logging.getLogger(__name__)

PHASES = ("CAMPAIGN", "PREFLIGHT", "STRATEGY", "INJECT", "DETECT", "RCA", "DECIDE", "GUARDRAIL",
          "REMEDIATE", "VERIFY", "RECOVERED", "FAILED", "TEARDOWN", "SUMMARY", "AUTOPILOT")


class Narrator:
    def __init__(self, campaign_id: str | None = None, echo: bool = True):
        self.campaign_id = campaign_id
        self.echo = echo
        self.round: int | None = None

    def say(self, phase: str, message: str, service: str | None = None, data: dict | None = None) -> dict:
        try:
            ev = state_db.add_event(phase, message, campaign_id=self.campaign_id, round_num=self.round,
                                    service=service, data=data)
        except sqlite3.Error as exc:
            # The durable event file below still records it; a damaged or locked DB must never stop a run.
            log.warning("could not store event in SQLite (%s); kept in the event file", exc)
            ev = {"id": None, "at": state_db.iso(), "campaign_id": self.campaign_id, "round": self.round,
                  "phase": phase, "service": service, "message": message, "data": data}
        incident_log.append_event(ev)
        if self.echo:
            tag = f"R{self.round}" if self.round else "--"
            print(f"  [{tag} {phase:<9}] {message}", flush=True)
        return ev


def detection_text(payload: dict, injected_ago: float | None) -> str:
    svc = payload["affected_service"]
    kind = (payload.get("anomaly_type") or "unknown").replace("_", " ")
    lead = (f"Anomaly confirmed on {svc} {injected_ago:.0f}s after injection"
            if injected_ago is not None else f"Anomaly confirmed on {svc}")
    ev = "; ".join(payload.get("evidence", [])[:3])
    others = [s["service"] for s in payload.get("anomalous_services", []) if s["service"] != svc]
    text = (f"{lead}: pattern matches {kind}. Isolation Forest score {payload['iforest_score']:+.3f} "
            f"(threshold {payload['threshold']:+.3f}), severity {payload['severity_score']:.2f}.")
    if ev:
        text += f" Evidence: {ev}."
    if others:
        text += f" Also deviating: {', '.join(others)}."
    lstm = payload.get("lstm") or {}
    if lstm.get("predicted_score_60s") is not None:
        text += (f" LSTM forecast for the next 60s: score {lstm['predicted_score_60s']:+.3f}"
                 f" ({'still anomalous' if lstm.get('predicted_anomaly') else 'returning to normal'}).")
    return text


def remediation_text(result: dict) -> str:
    verdict = "succeeded" if result["success"] else "did not complete"
    return f"{result['remediator']} {verdict} in {result['duration_s']:.1f}s — {result['summary']}."


def recovery_text(service: str, sla: dict, impact: dict | None) -> str:
    text = (f"{service} recovered: detected in {sla['ttd_seconds']}s, mitigated in {sla['ttm_seconds']}s, "
            f"fully back to its normal operating band in {sla['ttr_seconds']}s "
            f"(target {sla['recovery_target_seconds']}s — {'MET' if sla['recovery_met'] else 'MISSED'}).")
    if impact and impact.get("failure_ratio") is not None:
        text += (f" Users saw {impact['failed_requests']:.0f} failed requests out of {impact['total_requests']:.0f} "
                 f"({impact['failure_ratio']:.1%}) during the incident.")
    return text
