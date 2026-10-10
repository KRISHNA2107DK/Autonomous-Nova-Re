"""
SQLite persistence shared by the orchestrator, the API and the dashboard.

WAL mode allows the API process to read while an orchestrator process writes.
All timestamps are timezone-aware UTC ISO-8601 strings, so lexical comparison
in SQL is chronological comparison.

Tables
  campaigns          one row per chaos campaign
  rounds             one row per round (full record kept as JSON)
  remediations       every remediation attempt (feeds confidence scoring)
  guardrail_events   every guardrail decision
  active_remediations  services currently being remediated (Guardrail 1)
  events             the narrated reasoning feed
  kv                 small live state (round status, detector heartbeat)
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator

from novasurge import config

_init_lock = threading.Lock()
_initialised: set[str] = set()

SCHEMA = """
CREATE TABLE IF NOT EXISTS campaigns (
    id           TEXT PRIMARY KEY,
    started_at   TEXT NOT NULL,
    finished_at  TEXT,
    status       TEXT NOT NULL,
    mode         TEXT NOT NULL,
    plan         TEXT,
    report       TEXT
);
CREATE TABLE IF NOT EXISTS rounds (
    campaign_id  TEXT NOT NULL,
    round_num    INTEGER NOT NULL,
    injector     TEXT,
    target       TEXT,
    status       TEXT,
    updated_at   TEXT NOT NULL,
    data         TEXT NOT NULL,
    PRIMARY KEY (campaign_id, round_num)
);
CREATE TABLE IF NOT EXISTS remediations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id   TEXT,
    round_num     INTEGER,
    service       TEXT NOT NULL,
    anomaly_type  TEXT,
    remediator    TEXT NOT NULL,
    attempted_at  TEXT NOT NULL,
    completed_at  TEXT,
    success       INTEGER,
    duration_s    REAL,
    error         TEXT
);
CREATE INDEX IF NOT EXISTS ix_rem_svc ON remediations(service, remediator, attempted_at);
CREATE TABLE IF NOT EXISTS guardrail_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id   TEXT,
    round_num     INTEGER,
    guardrail     TEXT NOT NULL,
    service       TEXT NOT NULL,
    outcome       TEXT NOT NULL,
    detail        TEXT,
    at            TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS active_remediations (
    service     TEXT PRIMARY KEY,
    remediator  TEXT NOT NULL,
    owner       TEXT,
    started_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    at           TEXT NOT NULL,
    campaign_id  TEXT,
    round_num    INTEGER,
    phase        TEXT NOT NULL,
    service      TEXT,
    message      TEXT NOT NULL,
    data         TEXT
);
CREATE TABLE IF NOT EXISTS kv (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
"""


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    return (dt or utcnow()).isoformat()


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    path = str(config.DB_PATH)
    if path not in _initialised:
        with _init_lock:
            if path not in _initialised:
                config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
                conn = sqlite3.connect(path, timeout=15)
                conn.execute("PRAGMA journal_mode=WAL")
                conn.executescript(SCHEMA)
                conn.commit()
                conn.close()
                _initialised.add(path)
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=15000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _dumps(obj: Any) -> str:
    return json.dumps(obj, default=str)


# ── campaigns / rounds ───────────────────────────────────────────────────────
def create_campaign(campaign_id: str, mode: str, plan: list[dict]) -> None:
    with connect() as c:
        c.execute("INSERT INTO campaigns (id, started_at, status, mode, plan) VALUES (?, ?, ?, ?, ?)",
                  (campaign_id, iso(), "RUNNING", mode, _dumps(plan)))


def finish_campaign(campaign_id: str, status: str, report: dict | None) -> None:
    with connect() as c:
        c.execute("UPDATE campaigns SET finished_at=?, status=?, report=? WHERE id=?",
                  (iso(), status, _dumps(report) if report is not None else None, campaign_id))


def get_campaign(campaign_id: str) -> dict | None:
    with connect() as c:
        row = c.execute("SELECT * FROM campaigns WHERE id=?", (campaign_id,)).fetchone()
    return _campaign(row) if row else None


def latest_campaign() -> dict | None:
    with connect() as c:
        row = c.execute("SELECT * FROM campaigns ORDER BY started_at DESC LIMIT 1").fetchone()
    return _campaign(row) if row else None


def list_campaigns(limit: int = 20) -> list[dict]:
    with connect() as c:
        rows = c.execute("SELECT * FROM campaigns ORDER BY started_at DESC LIMIT ?", (limit,)).fetchall()
    return [_campaign(r) for r in rows]


def _campaign(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["plan"] = json.loads(d["plan"]) if d.get("plan") else []
    d["report"] = json.loads(d["report"]) if d.get("report") else None
    return d


def save_round(campaign_id: str, record: dict) -> None:
    with connect() as c:
        c.execute(
            """INSERT INTO rounds (campaign_id, round_num, injector, target, status, updated_at, data)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(campaign_id, round_num) DO UPDATE SET
                 injector=excluded.injector, target=excluded.target, status=excluded.status,
                 updated_at=excluded.updated_at, data=excluded.data""",
            (campaign_id, record["round"], record.get("injector"), record.get("target"),
             record.get("status"), iso(), _dumps(record)),
        )


def get_rounds(campaign_id: str) -> list[dict]:
    with connect() as c:
        rows = c.execute("SELECT data FROM rounds WHERE campaign_id=? ORDER BY round_num",
                         (campaign_id,)).fetchall()
    return [json.loads(r["data"]) for r in rows]


# ── remediation history (confidence + Guardrail 3) ───────────────────────────
def record_remediation_attempt(campaign_id: str | None, round_num: int | None, service: str,
                               anomaly_type: str | None, remediator: str) -> int:
    with connect() as c:
        cur = c.execute(
            """INSERT INTO remediations (campaign_id, round_num, service, anomaly_type, remediator, attempted_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (campaign_id, round_num, service, anomaly_type, remediator, iso()))
        return int(cur.lastrowid)


def complete_remediation(rem_id: int, success: bool, duration_s: float, error: str | None = None) -> None:
    with connect() as c:
        c.execute("UPDATE remediations SET completed_at=?, success=?, duration_s=?, error=? WHERE id=?",
                  (iso(), int(success), round(duration_s, 3), error, rem_id))


def success_rate(service: str, remediator: str, anomaly_type: str | None = None,
                 lookback: int = 10) -> tuple[float | None, int]:
    """(success rate over the last `lookback` completed attempts, sample size)."""
    q = ("SELECT success FROM remediations WHERE service=? AND remediator=? AND success IS NOT NULL"
         + (" AND anomaly_type=?" if anomaly_type else "") + " ORDER BY id DESC LIMIT ?")
    args: tuple = (service, remediator, anomaly_type, lookback) if anomaly_type else (service, remediator, lookback)
    with connect() as c:
        rows = c.execute(q, args).fetchall()
    if not rows:
        return None, 0
    return sum(r["success"] for r in rows) / len(rows), len(rows)


def recently_failed(service: str, remediator: str, within_seconds: int = 300) -> bool:
    cutoff = iso(utcnow() - timedelta(seconds=within_seconds))
    with connect() as c:
        row = c.execute(
            """SELECT COUNT(*) AS n FROM remediations
               WHERE service=? AND remediator=? AND success=0 AND attempted_at > ?""",
            (service, remediator, cutoff)).fetchone()
    return row["n"] > 0


# ── active remediations (Guardrail 1) ────────────────────────────────────────
ACTIVE_TTL_SECONDS = 600


def mark_active(service: str, remediator: str, owner: str) -> None:
    with connect() as c:
        c.execute("INSERT OR REPLACE INTO active_remediations (service, remediator, owner, started_at)"
                  " VALUES (?, ?, ?, ?)", (service, remediator, owner, iso()))


def clear_active(service: str) -> None:
    with connect() as c:
        c.execute("DELETE FROM active_remediations WHERE service=?", (service,))


def active_remediations() -> dict[str, dict]:
    """Active entries; stale ones (crashed owner) older than the TTL are purged."""
    cutoff = iso(utcnow() - timedelta(seconds=ACTIVE_TTL_SECONDS))
    with connect() as c:
        c.execute("DELETE FROM active_remediations WHERE started_at < ?", (cutoff,))
        rows = c.execute("SELECT * FROM active_remediations").fetchall()
    return {r["service"]: dict(r) for r in rows}


def clear_all_active(owner: str | None = None) -> None:
    with connect() as c:
        if owner:
            c.execute("DELETE FROM active_remediations WHERE owner=?", (owner,))
        else:
            c.execute("DELETE FROM active_remediations")


# ── guardrails ───────────────────────────────────────────────────────────────
def record_guardrail(campaign_id: str | None, round_num: int | None, guardrail: str, service: str,
                     outcome: str, detail: str) -> None:
    with connect() as c:
        c.execute(
            """INSERT INTO guardrail_events (campaign_id, round_num, guardrail, service, outcome, detail, at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (campaign_id, round_num, guardrail, service, outcome, detail, iso()))


# ── reasoning feed ───────────────────────────────────────────────────────────
def add_event(phase: str, message: str, *, campaign_id: str | None = None, round_num: int | None = None,
              service: str | None = None, data: dict | None = None) -> dict:
    at = iso()
    with connect() as c:
        cur = c.execute(
            "INSERT INTO events (at, campaign_id, round_num, phase, service, message, data) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (at, campaign_id, round_num, phase, service, message, _dumps(data) if data else None))
        eid = int(cur.lastrowid)
    return {"id": eid, "at": at, "campaign_id": campaign_id, "round": round_num, "phase": phase,
            "service": service, "message": message, "data": data}


def recent_events(limit: int = 50, after_id: int = 0) -> list[dict]:
    with connect() as c:
        rows = c.execute("SELECT * FROM events WHERE id > ? ORDER BY id DESC LIMIT ?",
                         (after_id, limit)).fetchall()
    out = []
    for r in reversed(rows):
        d = dict(r)
        d["round"] = d.pop("round_num")
        d["data"] = json.loads(d["data"]) if d.get("data") else None
        out.append(d)
    return out


def fault_history() -> dict[tuple[str, str], dict]:
    """Per (injector, target): when it was last injected, how often, and how the last attempt went."""
    with connect() as c:
        rows = c.execute("SELECT data FROM rounds WHERE injector IS NOT NULL AND target IS NOT NULL").fetchall()
    out: dict[tuple[str, str], dict] = {}
    for r in rows:
        rec = json.loads(r["data"])
        at = rec.get("injected_at")
        if not at:
            continue
        key = (rec["injector"], rec["target"])
        h = out.setdefault(key, {"count": 0, "last_at": None})
        h["count"] += 1
        if h["last_at"] is None or at > h["last_at"]:
            sla = rec.get("sla") or {}
            h.update(last_at=at, last_status=rec.get("status"),
                     last_detected=bool(rec.get("detected_at")),
                     last_recovery_met=sla.get("recovery_met"),
                     last_diagnosis_correct=rec.get("diagnosis_correct"),
                     last_ttr_seconds=sla.get("ttr_seconds"))
    return out


CHAOS_PHASES = ("INJECT", "REMEDIATE", "TEARDOWN", "AUTOPILOT", "RECOVERED", "FAILED")


def last_chaos_activity() -> datetime | None:
    """When NovaSurge last injected or remediated anything (training must not see it)."""
    marks = ",".join("?" * len(CHAOS_PHASES))
    with connect() as c:
        row = c.execute(f"SELECT MAX(at) AS at FROM events WHERE phase IN ({marks})", CHAOS_PHASES).fetchone()  # noqa: S608
    return datetime.fromisoformat(row["at"]) if row and row["at"] else None


# ── kv ───────────────────────────────────────────────────────────────────────
def kv_set(key: str, value: Any) -> None:
    with connect() as c:
        c.execute("INSERT OR REPLACE INTO kv (key, value, updated_at) VALUES (?, ?, ?)",
                  (key, _dumps(value), iso()))


def kv_get(key: str, default: Any = None) -> Any:
    with connect() as c:
        row = c.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
    return json.loads(row["value"]) if row else default


def reset_runtime(history: bool = False) -> None:
    """Forget live state; with history=True also every recorded campaign/remediation (tests)."""
    with connect() as c:
        c.execute("DELETE FROM active_remediations")
        c.execute("DELETE FROM kv")
        if history:
            for table in ("remediations", "guardrail_events", "events", "rounds", "campaigns"):
                c.execute(f"DELETE FROM {table}")  # noqa: S608 - fixed table names
