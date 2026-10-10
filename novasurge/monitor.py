"""
Monitor — the platform's single detection loop.

Every STEP_SECONDS: telemetry snapshot -> detector.step -> publish.
Consumers (API WebSocket broadcaster, orchestrator, autopilot) await ticks
instead of polling files. Each tick is also appended to telemetry.jsonl so
models can later be retrained on what the system actually experienced.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Awaitable, Callable

from novasurge import config, state_db
from novasurge.ml.detector import DetectionResult, Detector, ModelsMissing
from novasurge.telemetry import Snapshot, TelemetrySource, get_telemetry

log = logging.getLogger("novasurge.monitor")

Listener = Callable[[Snapshot, DetectionResult | None], Awaitable[None]]
TELEMETRY_LOG_MAX_BYTES = 50 * 1024 * 1024


class Monitor:
    def __init__(self, telemetry: TelemetrySource | None = None, detector: Detector | None = None,
                 interval: float = config.STEP_SECONDS, record: bool = True):
        self.telemetry = telemetry or get_telemetry()
        self.interval = interval
        self.record = record
        self.detector = detector
        self.model_error: str | None = None
        if self.detector is None:
            try:
                self.detector = Detector()
            except ModelsMissing as exc:
                self.model_error = str(exc)
                log.warning("%s — running in telemetry-only mode", exc)
        self.snapshot: Snapshot | None = None
        self.detection: DetectionResult | None = None
        self.tick = 0
        self._listeners: list[Listener] = []
        self._cond = asyncio.Condition()
        self._task: asyncio.Task | None = None
        self.context: dict = {}          # round/campaign context stamped onto recorded telemetry

    def add_listener(self, fn: Listener) -> None:
        self._listeners.append(fn)

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop(), name="novasurge-monitor")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def next_tick(self, timeout: float | None = None) -> tuple[Snapshot, DetectionResult | None]:
        async with self._cond:
            current = self.tick
            await asyncio.wait_for(self._cond.wait_for(lambda: self.tick > current), timeout)
            return self.snapshot, self.detection

    async def _loop(self) -> None:
        next_at = time.monotonic()
        while True:
            try:
                snap = await asyncio.to_thread(self.telemetry.snapshot)
                det = self.detector.step(snap) if self.detector else None
                self.snapshot, self.detection = snap, det
                if self.record:
                    await asyncio.to_thread(self._record, snap, det)
                if det:
                    state_db.kv_set("detector", {"at": snap.timestamp.isoformat(),
                                                 "anomalous": det.anomalous, "primary": det.primary})
                async with self._cond:
                    self.tick += 1
                    self._cond.notify_all()
                for fn in list(self._listeners):
                    try:
                        await fn(snap, det)
                    except Exception as exc:  # noqa: BLE001 - one bad listener must not stop detection
                        log.warning("monitor listener failed: %s", exc)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                log.exception("monitor tick failed: %s", exc)
            next_at += self.interval
            await asyncio.sleep(max(0.0, next_at - time.monotonic()))
            if time.monotonic() - next_at > self.interval * 3:
                next_at = time.monotonic()

    def _record(self, snap: Snapshot, det: DetectionResult | None) -> None:
        if not snap.prometheus_ok:
            return
        log_path = config.DATA_DIR / "telemetry.jsonl"
        try:
            if log_path.exists() and log_path.stat().st_size > TELEMETRY_LOG_MAX_BYTES:
                log_path.replace(log_path.with_suffix(".jsonl.1"))
            rec = {
                "t": snap.timestamp.timestamp(),
                "features": {s: st.features for s, st in snap.services.items()},
                "anomalous": det.anomalous if det else [],
                "context": self.context,
            }
            with log_path.open("a") as fh:
                fh.write(json.dumps(rec) + "\n")
        except OSError as exc:
            log.debug("telemetry record failed: %s", exc)
