"""
NovaSurge API + dashboard server.

    python -m novasurge serve            -> http://127.0.0.1:8000

One process owns the Monitor (the single detection loop). Everything else —
WebSocket stream, REST, campaigns started from the dashboard, and autopilot —
consumes its ticks, so all views agree.

REST (all under /api; legacy aliases kept for /health, /anomaly/current,
/metrics/current, /rounds)
  GET  /api/health                 liveness
  GET  /api/status                 platform status (prometheus, models, campaign, autopilot)
  GET  /api/anomaly/current        detector verdict (primary anomaly + all anomalous services)
  GET  /api/detection              full per-service detection
  GET  /api/metrics/current        latest telemetry snapshot
  GET  /api/topology               live dependency graph (health + call rates)
  GET  /api/events?after=&limit=   narrated reasoning feed
  GET  /api/model                  model card
  GET  /api/campaigns              campaign history
  GET  /api/campaigns/{id}         one campaign with rounds
  GET  /api/rounds                 rounds of the latest campaign
  POST /api/campaign/start         {"rounds": N} or {"plan": [...]}
  POST /api/campaign/stop
  POST /api/autopilot              {"enabled": bool}
  POST /api/chaos/inject           {"injector": ..., "service": ...}   manual fault (autopilot heals it)
WS   /ws/stream                    one frame per detector tick
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from novasurge import __version__, config, state_db, topology
from novasurge.chaos.injectors import REGISTRY as INJECTORS
from novasurge.cluster import get_cluster
from novasurge.healer import Healer
from novasurge.ml.detector import DetectionResult
from novasurge.monitor import Monitor
from novasurge.orchestrator import Campaign, CampaignOptions, load_plan
from novasurge.reasoning import Narrator, detection_text
from novasurge.telemetry import Snapshot

log = logging.getLogger("novasurge.api")


# Request bodies live at module level: with postponed annotations FastAPI
# resolves type names against module globals.
class CampaignRequest(BaseModel):
    rounds: int | None = None
    plan: list[dict] | None = None


class AutopilotRequest(BaseModel):
    enabled: bool


class InjectRequest(BaseModel):
    injector: str
    service: str


class Hub:
    """Shared runtime: monitor, websocket clients, campaign task, autopilot."""

    def __init__(self, autopilot: bool):
        self.monitor: Monitor | None = None
        self.clients: set[WebSocket] = set()
        self.campaign: Campaign | None = None
        self.campaign_task: asyncio.Task | None = None
        self.autopilot = autopilot
        self.autopilot_task: asyncio.Task | None = None
        self.autopilot_cooldown_until = 0.0
        self.last_event_id = 0
        self.started_at = datetime.now(timezone.utc).isoformat()

    @property
    def campaign_running(self) -> bool:
        return self.campaign_task is not None and not self.campaign_task.done()

    # ── per-tick fan-out ─────────────────────────────────────────────────────
    async def on_tick(self, snap: Snapshot, det: DetectionResult | None) -> None:
        events = state_db.recent_events(limit=50, after_id=self.last_event_id)
        if events:
            self.last_event_id = events[-1]["id"]
        frame = build_frame(snap, det, events, self)
        if self.clients:
            payload = json.dumps(frame, default=str)
            dead = []
            for ws in list(self.clients):
                try:
                    await ws.send_text(payload)
                except Exception:  # noqa: BLE001
                    dead.append(ws)
            for ws in dead:
                self.clients.discard(ws)
        await self._autopilot(det)

    async def _autopilot(self, det: DetectionResult | None) -> None:
        if not (self.autopilot and det and det.primary) or self.campaign_running:
            return
        if self.autopilot_task and not self.autopilot_task.done():
            return
        if time.monotonic() < self.autopilot_cooldown_until:
            return
        self.autopilot_task = asyncio.create_task(self._autopilot_heal(det))

    async def _autopilot_heal(self, det: DetectionResult) -> None:
        narrator = Narrator(None, echo=False)
        payload = det.anomaly_payload()
        narrator.say("AUTOPILOT", "Autopilot engaged — " + detection_text(payload, None),
                     payload["affected_service"], payload)
        healer = Healer(self.monitor, get_cluster(), narrator, owner="autopilot")
        try:
            outcome = await healer.heal(det)
            narrator.say("AUTOPILOT", f"Autopilot finished: {outcome.status} "
                                      f"(healed by {outcome.healed_by or 'nothing'}).",
                         (outcome.rca or {}).get("origin"), outcome.to_dict())
        except Exception as exc:  # noqa: BLE001
            log.exception("autopilot failed")
            narrator.say("FAILED", f"Autopilot error: {exc}")
        finally:
            self.autopilot_cooldown_until = time.monotonic() + 30


def build_frame(snap: Snapshot, det: DetectionResult | None, events: list[dict], hub: Hub) -> dict:
    services = {}
    for svc in topology.SERVICES:
        st = snap.services[svc]
        d = det.services[svc] if det else None
        services[svc] = {
            "status": d.status if d else "unknown",
            "score": round(d.score, 4) if d else None,
            "severity": d.severity if d else 0.0,
            "anomaly_type": d.anomaly_type if d else None,
            "flags": d.flags if d else [],
            "top_deviations": [[f, round(z, 2)] for f, z in d.top_deviations(3)] if d else [],
            "metrics": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in st.features.items()},
            "replicas": {"ready": st.ready_replicas, "desired": st.desired_replicas,
                         "baseline_min": st.baseline_min_replicas, "hpa_min": st.hpa_min, "hpa_max": st.hpa_max},
            "lstm": (d.lstm.__dict__ if d else None),
        }
    return {
        "type": "tick",
        "timestamp": snap.timestamp.isoformat(),
        "threshold": det.threshold if det else None,
        "services": services,
        "anomaly": det.anomaly_payload() if det else None,
        "user_sli": snap.user_sli,
        "call_rates": snap.call_rates,
        "prometheus_ok": snap.prometheus_ok,
        "campaign": state_db.kv_get("campaign"),
        "autopilot": {"enabled": hub.autopilot,
                      "healing": bool(hub.autopilot_task and not hub.autopilot_task.done())},
        "events": events,
    }


def create_app(autopilot: bool = True, start_monitor: bool = True) -> FastAPI:
    hub = Hub(autopilot)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        state_db.clear_all_active()
        latest = state_db.recent_events(limit=1)
        hub.last_event_id = latest[-1]["id"] if latest else 0
        if start_monitor:
            hub.monitor = Monitor()
            hub.monitor.add_listener(hub.on_tick)
            await hub.monitor.start()
        app.state.hub = hub
        yield
        if hub.campaign_task and not hub.campaign_task.done():
            hub.campaign.stop_requested = True
            hub.campaign_task.cancel()
        if hub.monitor:
            await hub.monitor.stop()

    app = FastAPI(title="NovaSurge", version=__version__, lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                       allow_methods=["*"], allow_headers=["*"])

    def monitor() -> Monitor:
        if hub.monitor is None:
            raise HTTPException(503, "monitor not running")
        return hub.monitor

    # ── read API ─────────────────────────────────────────────────────────────
    @app.get("/api/health")
    @app.get("/health", include_in_schema=False)
    def health():
        return {"status": "ok", "service": "novasurge", "version": __version__}

    @app.get("/api/status")
    def status():
        m = hub.monitor
        card = m.detector.card if m and m.detector else None
        return {
            "version": __version__,
            "started_at": hub.started_at,
            "prometheus_ok": bool(m and m.snapshot and m.snapshot.prometheus_ok),
            "monitor_tick": m.tick if m else 0,
            "models": {"loaded": bool(m and m.detector), "error": m.model_error if m else None,
                       "trained_at": card["created_at"] if card else None,
                       "threshold": card["iforest"]["threshold"] if card else None},
            "campaign": state_db.kv_get("campaign"),
            "campaign_running": hub.campaign_running,
            "autopilot": hub.autopilot,
        }

    @app.get("/api/anomaly/current")
    @app.get("/anomaly/current", include_in_schema=False)
    def anomaly_current():
        m = monitor()
        if m.detection is None:
            return {"anomaly_detected": False, "status": "warming_up" if m.detector else "models_missing"}
        return m.detection.anomaly_payload()

    @app.get("/api/detection")
    def detection():
        m = monitor()
        return m.detection.to_dict() if m.detection else {}

    @app.get("/api/metrics/current")
    @app.get("/metrics/current", include_in_schema=False)
    def metrics_current():
        m = monitor()
        return m.snapshot.to_dict() if m.snapshot else {}

    @app.get("/api/topology")
    def topo():
        m = hub.monitor
        det, snap = (m.detection, m.snapshot) if m else (None, None)
        nodes = [{"id": s, "impact": topology.BUSINESS_IMPACT[s],
                  "status": det.services[s].status if det else "unknown",
                  "request_rate": snap.services[s].features.get("request_rate") if snap else None}
                 for s in topology.SERVICES]
        rates = snap.call_rates if snap else {}
        edges = [e | {"rate": rates.get(f"{e['source']}->{e['target']}")} for e in topology.edges()]
        return {"nodes": nodes, "edges": edges}

    @app.get("/api/events")
    def events(after: int = 0, limit: int = 100):
        return state_db.recent_events(limit=min(limit, 500), after_id=after)

    @app.get("/api/model")
    def model():
        m = hub.monitor
        if not (m and m.detector):
            raise HTTPException(404, m.model_error if m else "monitor not running")
        return m.detector.card

    @app.get("/api/campaigns")
    def campaigns(limit: int = 20):
        return state_db.list_campaigns(limit)

    @app.get("/api/campaigns/{campaign_id}")
    def campaign(campaign_id: str):
        c = state_db.get_campaign(campaign_id)
        if not c:
            raise HTTPException(404, "unknown campaign")
        return c | {"rounds": state_db.get_rounds(campaign_id)}

    @app.get("/api/rounds")
    @app.get("/rounds", include_in_schema=False)
    def rounds():
        c = state_db.latest_campaign()
        return state_db.get_rounds(c["id"]) if c else []

    # ── control API ──────────────────────────────────────────────────────────
    @app.post("/api/campaign/start")
    async def campaign_start(req: CampaignRequest | None = None):
        m = monitor()
        if hub.campaign_running:
            raise HTTPException(409, "a campaign is already running")
        if m.detector is None:
            raise HTTPException(409, m.model_error or "models not trained")
        plan = (req.plan if req and req.plan else load_plan())
        if req and req.rounds:
            plan = plan[: req.rounds]
        for spec in plan:
            if spec.get("injector") not in INJECTORS:
                raise HTTPException(400, f"unknown injector {spec.get('injector')}")
        hub.campaign = Campaign(m, get_cluster(), plan=plan, options=CampaignOptions(), mode="live", echo=False)
        hub.campaign_task = asyncio.create_task(hub.campaign.run())
        return {"campaign_id": hub.campaign.id, "rounds": len(plan)}

    @app.post("/api/campaign/stop")
    async def campaign_stop():
        if not hub.campaign_running:
            raise HTTPException(409, "no campaign running")
        hub.campaign.stop_requested = True
        return {"stopping": hub.campaign.id, "note": "stops after the current round completes its teardown"}

    @app.post("/api/autopilot")
    def autopilot(req: AutopilotRequest):
        hub.autopilot = req.enabled
        return {"autopilot": hub.autopilot}

    @app.post("/api/chaos/inject")
    async def chaos_inject(req: InjectRequest):
        if req.injector not in INJECTORS or req.service not in topology.SERVICES:
            raise HTTPException(400, "unknown injector or service")
        if hub.campaign_running:
            raise HTTPException(409, "a campaign is running")
        mod = INJECTORS[req.injector]
        ok, why = await asyncio.to_thread(mod.compatible, get_cluster(), req.service)
        if not ok:
            raise HTTPException(409, f"{req.injector} not applicable to {req.service}: {why}")
        inj = await asyncio.to_thread(mod.inject, get_cluster(), req.service)
        Narrator(None, echo=False).say("INJECT", f"Manual fault injected: {req.injector} into {req.service}"
                                                 f" — autopilot {'will heal it' if hub.autopilot else 'is OFF'}.",
                                       req.service, inj.to_dict())
        return inj.to_dict()

    # ── WebSocket ────────────────────────────────────────────────────────────
    @app.websocket("/ws/stream")
    async def stream(ws: WebSocket):
        await ws.accept()
        hub.clients.add(ws)
        try:
            hello = {"type": "hello", "version": __version__, "services": topology.SERVICES,
                     "edges": topology.edges(), "impact": topology.BUSINESS_IMPACT,
                     "events": state_db.recent_events(limit=40),
                     "model": hub.monitor.detector.card["iforest"] if hub.monitor and hub.monitor.detector else None}
            await ws.send_text(json.dumps(hello, default=str))
            if hub.monitor and hub.monitor.snapshot:
                await ws.send_text(json.dumps(build_frame(hub.monitor.snapshot, hub.monitor.detection, [], hub),
                                              default=str))
            while True:
                await ws.receive_text()      # keep-alive; client messages are ignored
        except WebSocketDisconnect:
            pass
        finally:
            hub.clients.discard(ws)

    # ── dashboard ────────────────────────────────────────────────────────────
    dist = config.DASHBOARD_DIST
    if (dist / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/", include_in_schema=False)
        def index():
            return FileResponse(dist / "index.html")

        @app.get("/favicon.svg", include_in_schema=False)
        def favicon():
            return FileResponse(dist / "favicon.svg")
    else:
        @app.get("/", include_in_schema=False)
        def index_missing():
            return HTMLResponse("<h2>NovaSurge API is running.</h2><p>The dashboard has not been built yet: "
                                "run <code>python -m novasurge dashboard-build</code>.</p><p>API docs: "
                                "<a href='/docs'>/docs</a></p>")

    @app.exception_handler(Exception)
    async def unhandled(_req, exc: Exception):
        log.exception("unhandled API error")
        return JSONResponse({"error": str(exc)}, status_code=500)

    return app
