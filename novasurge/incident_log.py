"""
Durable incident log: every injected failure, detection, diagnosis, decision and
remediation, with the reasoning behind each step, written as plain files.

Two artefacts per campaign in <repo>/reports/<campaign>/:
  events.jsonl      every narration event, appended live as it happens (one JSON object per line)
  INCIDENT-LOG.md   a readable per-round log rendered from rounds.json + events when the campaign ends

Events outside a campaign (autopilot healing, manual injections) are appended to
reports/autopilot/<UTC date>.jsonl. The files survive a reset or a moved runtime
directory; SQLite stays the live store for the dashboard.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from novasurge import config

log = logging.getLogger(__name__)

EVENTS_FILE = "events.jsonl"
LOG_FILE = "INCIDENT-LOG.md"


def _events_path(campaign_id: str | None, at: str | None = None) -> Path:
    if campaign_id:
        return config.REPORTS_DIR / campaign_id / EVENTS_FILE
    day = (at or datetime.now(timezone.utc).isoformat())[:10]
    return config.REPORTS_DIR / "autopilot" / f"{day}.jsonl"


def append_event(ev: dict) -> None:
    """Append one narration event to its durable log file (never raises)."""
    try:
        path = _events_path(ev.get("campaign_id"), ev.get("at"))
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(ev, default=str, ensure_ascii=False) + "\n")
    except OSError as exc:
        log.warning("could not append incident event: %s", exc)


def load_events(campaign_id: str) -> list[dict]:
    """Events of one campaign: the live file if present, else whatever SQLite still holds."""
    path = _events_path(campaign_id)
    if path.exists():
        out = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return out
    try:
        from novasurge import state_db
        with state_db.connect() as c:
            rows = c.execute("SELECT * FROM events WHERE campaign_id = ? ORDER BY id", (campaign_id,)).fetchall()
    except Exception as exc:  # noqa: BLE001 - a missing/locked DB just means no narration
        log.warning("could not read events for %s: %s", campaign_id, exc)
        return []
    out = []
    for r in rows:
        d = dict(r)
        d["round"] = d.pop("round_num")
        d["data"] = json.loads(d["data"]) if d.get("data") else None
        out.append(d)
    if out:
        # Make DB-only narration durable so a later DB loss can never take it away.
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("".join(json.dumps(e, default=str, ensure_ascii=False) + "\n" for e in out),
                            encoding="utf-8")
        except OSError as exc:
            log.warning("could not back up events for %s: %s", campaign_id, exc)
    return out


# --------------------------------------------------------------------------- rendering

def _t(ts: str | None) -> str:
    return ts[11:19] if ts and len(ts) >= 19 else (ts or "—")


def _pct(v) -> str:
    return f"{v:.1%}" if isinstance(v, (int, float)) else "—"


def _sec(v) -> str:
    return f"{v}s" if v is not None else "—"


def _bullets(items, limit: int | None = None) -> list[str]:
    items = list(items or [])
    shown = items[:limit] if limit else items
    out = [f"- {i}" for i in shown]
    if limit and len(items) > limit:
        out.append(f"- … {len(items) - limit} more")
    return out


def _round_section(r: dict, events: list[dict]) -> list[str]:
    n = r.get("round")
    sla = r.get("sla") or {}
    L = [f"## Round {n} — {r.get('injector') or '—'} → {r.get('target') or '—'}  ·  **{r.get('status')}**", ""]
    L.append(f"TTD {_sec(sla.get('ttd_seconds'))} (target {_sec(sla.get('detection_target_seconds'))}, "
             f"{'met' if sla.get('detection_met') else 'missed'}) · TTM {_sec(sla.get('ttm_seconds'))} · "
             f"TTR {_sec(sla.get('ttr_seconds'))} (target {_sec(sla.get('recovery_target_seconds'))}, "
             f"{'met' if sla.get('recovery_met') else 'missed'}) · healed by {r.get('healed_by') or '—'} · "
             f"diagnosis {'correct' if r.get('diagnosis_correct') else 'wrong'}, "
             f"classification {'correct' if r.get('classification_correct') else 'wrong'}")
    L.append("")

    p = r.get("planner") or {}
    if p:
        L += ["### 1. Why this experiment", ""]
        who = f"LLM agent ({p.get('model')})" if p.get("decided_by") == "llm" else (p.get("decided_by") or "rules")
        L.append(f"Chosen by **{who}**: {p.get('reason') or '—'}")
        if p.get("fallback_reason"):
            L.append(f"\nRule fallback because: {p['fallback_reason']}")
        cands = p.get("candidates") or []
        if cands:
            L += ["", "| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |",
                  "|---|---|---|---|---|---|"]
            for c in cands:
                mins = c.get("minutes_since_last_tried")
                L.append(f"| {c.get('id')} | {c.get('fault')} | {c.get('service')} | {c.get('rule_score')} | "
                         f"{'never' if mins is None else mins} | {c.get('last_outcome') or '—'} |")
        L.append("")

    pf = r.get("preflight") or {}
    if pf:
        L += ["### 2. Safety check before injecting", ""]
        L.append(f"Decision **{pf.get('go_nogo')}** · risk {pf.get('injection_risk')} · system health "
                 f"{pf.get('system_health_pct')}% · target ready {pf.get('target_ready')} · load "
                 f"{pf.get('load_ratio')}× baseline · dependents {', '.join(pf.get('dependents') or []) or 'none'} · "
                 f"users possibly affected {pf.get('estimated_affected_users_pct')}%")
        if pf.get("nogo_reasons"):
            L += [""] + _bullets(pf["nogo_reasons"])
        L.append("")

    inj = r.get("injection") or {}
    if inj:
        L += ["### 3. Failure injected", ""]
        L.append(f"`{inj.get('injector')}` on **{inj.get('service')}** at {_t(inj.get('injected_at'))} UTC — "
                 f"{'succeeded' if inj.get('success') else 'FAILED: ' + str(inj.get('error'))}")
        if inj.get("details"):
            L.append(f"\nDetails: `{json.dumps(inj['details'], default=str)}`")
        L.append("")

    det = r.get("detection") or {}
    L += ["### 4. Detection", ""]
    if det:
        L.append(f"Confirmed at {_t(det.get('detected_at'))} UTC on **{det.get('affected_service')}** as "
                 f"`{det.get('anomaly_type')}` · severity {det.get('severity_score')} · Isolation Forest score "
                 f"{det.get('iforest_score')} (threshold {det.get('threshold')}) · flags: "
                 f"{', '.join(det.get('flags') or []) or '—'}")
        L += ["", "Evidence:"] + _bullets(det.get("evidence"))
        lstm = det.get("lstm") or {}
        if lstm.get("predicted_score_60s") is not None:
            L.append(f"\nLSTM 60 s forecast: score {lstm['predicted_score_60s']} "
                     f"({'still anomalous' if lstm.get('predicted_anomaly') else 'returning to normal'})")
    else:
        L.append("Not detected within the detection window.")
    L.append("")

    rca = r.get("rca") or {}
    if rca:
        L += ["### 5. Root-cause analysis", ""]
        L.append(f"Origin **{rca.get('origin')}** · type `{rca.get('anomaly_type')}` · confidence "
                 f"{rca.get('confidence')} · call path {' → '.join(rca.get('call_path') or []) or '—'} · affected "
                 f"{', '.join(rca.get('affected') or []) or '—'}")
        if rca.get("narrative"):
            L += ["", f"> {rca['narrative']}"]
        L += ["", "Evidence:"] + _bullets(rca.get("evidence"), limit=10)
        cands = rca.get("candidates") or []
        if cands and isinstance(cands[0], dict):
            L += ["", "| Candidate | Score | Why |", "|---|---|---|"]
            for c in cands[:5]:
                reasons = c.get("reasons") or []
                why = "; ".join(map(str, reasons)) if isinstance(reasons, list) else str(reasons)
                why = why if len(why) <= 400 else why[:400] + "…"
                L.append(f"| {c.get('service')} | {c.get('score')} | {why.replace('|', '/')} |")
        L.append("")

    dec = r.get("decision") or {}
    if dec:
        L += ["### 6. Decision", ""]
        L.append(f"Action **{dec.get('action')}** (fallback {dec.get('fallback')}) · confidence "
                 f"{dec.get('confidence')} · priority {dec.get('priority')}")
        L += [""] + _bullets(dec.get("reasoning"))
        L.append("")

    if r.get("guardrails"):
        L += ["### Guardrails triggered", ""] + _bullets(
            g.get("message") or json.dumps(g, default=str) if isinstance(g, dict) else str(g) for g in r["guardrails"])
        L.append("")

    rems = r.get("remediations") or []
    L += ["### 7. Remediation", ""]
    if rems:
        L += ["| Remediator | Service | Result | Verified | Duration | Summary |", "|---|---|---|---|---|---|"]
        for a in rems:
            L.append(f"| {a.get('remediator')} | {a.get('service')} | {'success' if a.get('success') else 'failed'} | "
                     f"{'yes' if a.get('verified') else 'no'} | {round(a.get('duration_s') or 0, 1)}s | "
                     f"{str(a.get('summary') or '').replace('|', '/')} |")
    else:
        L.append("No remediation was needed or attempted.")
    L.append("")

    td = r.get("teardown") or {}
    ui = r.get("user_impact") or {}
    L += ["### 8. Teardown and user impact", ""]
    if td:
        L.append(f"Fault still present at teardown: **{'yes' if td.get('fault_still_present') else 'no'}** · "
                 f"reverse `{json.dumps(td.get('reverse'), default=str)}` · autoscaler "
                 f"`{json.dumps(td.get('autoscaler'), default=str)}`")
    if ui:
        L.append(f"\nUsers: {ui.get('failed_requests', 0):.0f} failed of {ui.get('total_requests', 0):.0f} requests "
                 f"({_pct(ui.get('failure_ratio'))}) · user p99 {ui.get('p99_ms')} ms over {ui.get('window_seconds')} s")
    L.append("")

    mine = [e for e in events if e.get("round") == n]
    L += ["### 9. Full narration", ""]
    if mine:
        L += ["| Time (UTC) | Phase | Service | Message |", "|---|---|---|---|"]
        for e in mine:
            msg = str(e.get("message") or "").replace("|", "/").replace("\n", " ")
            L.append(f"| {_t(e.get('at'))} | {e.get('phase')} | {e.get('service') or ''} | {msg} |")
    else:
        L.append("_Narration for this run is no longer available (recorded before durable event logs existed); "
                 "the structured sections above are complete._")
    L.append("")
    return L


def render(campaign_id: str, rounds: list[dict], report: dict, events: list[dict]) -> str:
    L = [f"# Incident log — campaign `{campaign_id}`", "",
         f"**Resilience score {report.get('resilience_score')}/100** — {report.get('verdict')}", ""]
    comps = report.get("components") or {}
    if comps:
        L += ["| Component | Points |", "|---|---|"] + [f"| {k.replace('_', ' ')} | {v} |" for k, v in comps.items()]
        L.append("")
    L += ["| # | Fault | Target | Status | TTD | TTR | Users failed |", "|---|---|---|---|---|---|---|"]
    for r in rounds:
        sla = r.get("sla") or {}
        L.append(f"| {r.get('round')} | {r.get('injector')} | {r.get('target')} | {r.get('status')} | "
                 f"{_sec(sla.get('ttd_seconds'))} | {_sec(sla.get('ttr_seconds'))} | "
                 f"{_pct((r.get('user_impact') or {}).get('failure_ratio'))} |")
    L.append("")
    for r in rounds:
        L += _round_section(r, events)
    rest = [e for e in events if e.get("round") is None]
    if rest:
        L += ["## Campaign-level events", "", "| Time (UTC) | Phase | Message |", "|---|---|---|"]
        for e in rest:
            msg = str(e.get("message") or "").replace("|", "/").replace("\n", " ")
            L.append(f"| {_t(e.get('at'))} | {e.get('phase')} | {msg} |")
        L.append("")
    return "\n".join(L)


def write(campaign_id: str, rounds: list[dict] | None = None, report: dict | None = None) -> Path | None:
    """Render INCIDENT-LOG.md for one campaign (from files on disk when not given)."""
    out = config.REPORTS_DIR / campaign_id
    try:
        if rounds is None:
            rounds = json.loads((out / "rounds.json").read_text(encoding="utf-8"))
        if report is None:
            sc = out / "scorecard.json"
            report = json.loads(sc.read_text(encoding="utf-8")) if sc.exists() else {}
        events = load_events(campaign_id)
        out.mkdir(parents=True, exist_ok=True)
        path = out / LOG_FILE
        if not events and path.exists() and "\n### 9. Full narration\n\n| Time (UTC)" in path.read_text(encoding="utf-8"):
            # Never replace a log that still holds narration with one that has lost it.
            log.warning("kept existing %s for %s: its narration is no longer available elsewhere",
                        LOG_FILE, campaign_id)
            return path
        path.write_text(render(campaign_id, rounds, report, events), encoding="utf-8")
        return path
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("could not write incident log for %s: %s", campaign_id, exc)
        return None


def rebuild_all() -> list[Path]:
    """Regenerate the incident log of every campaign that has a rounds.json."""
    if not config.REPORTS_DIR.exists():
        return []
    written = []
    for d in sorted(config.REPORTS_DIR.iterdir()):
        if d.is_dir() and (d / "rounds.json").exists():
            p = write(d.name)
            if p:
                written.append(p)
    return written
