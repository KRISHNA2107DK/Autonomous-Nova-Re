"""
Online anomaly detector (one `step()` per 5-second telemetry snapshot).

Per service, three independent detectors vote on every window:
  1. Isolation Forest on the normalised feature vector (multivariate novelty)
  2. Robust z-score rule — any feature >= Z_ALERT sigmas in its *harmful*
     direction (interpretable, catches single-feature explosions)
  3. Structural invariants from Kubernetes/Prometheus — pods not ready,
     capacity below the declared baseline, metrics endpoint unreachable

A window is anomalous if any detector fires; a service becomes *confirmed*
anomalous after 2 of the last 3 windows (debounces one-off blips) and clears
after 3 consecutive clean windows. The LSTM forecaster adds a 60-second-ahead
prediction and a one-step "surprise" residual.
"""

from __future__ import annotations

import json
import logging
import math
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime

import joblib
import numpy as np
import torch

from novasurge import config
from novasurge.ml import train as artefacts
from novasurge.ml.features import Normalizer, harmful_z
from novasurge.ml.forecaster import TelemetryForecaster
from novasurge.telemetry import FEATURES, ServiceState, Snapshot
from novasurge import topology
from novasurge.topology import SERVICES

log = logging.getLogger("novasurge.detector")

Z_ALERT = 6.0          # single-feature rule
Z_SUPPORT = 3.0        # IF flags only count if some feature is >= this harmful
CONFIRM_WINDOWS = 2    # out of the last 3
CLEAR_WINDOWS = 3      # consecutive clean windows to clear

# Deterministic facts from the Kubernetes API (already debounced by readiness
# probes) confirm on first sight; statistical signals need CONFIRM_WINDOWS.
STRONG_FLAGS = {"all_replicas_down", "replicas_lost", "container_restarted", "capacity_below_baseline"}


class ModelsMissing(RuntimeError):
    pass


@dataclass
class LstmView:
    predicted_score_60s: float | None = None
    predicted_anomaly: bool = False
    forecast_scores: list[float] = field(default_factory=list)
    residual_z: float | None = None
    ready: bool = False


@dataclass
class ServiceDetection:
    service: str
    score: float
    z: dict[str, float]
    raw: dict[str, float | None]
    missing: list[str]
    flags: list[str]
    window_anomalous: bool
    confirmed: bool
    severity: float
    status: str
    anomaly_type: str | None
    evidence: list[str]
    first_flagged_at: str | None
    confirmed_at: str | None
    episode_flags: list[str]
    ready_replicas: int
    desired_replicas: int
    lstm: LstmView

    def top_deviations(self, n: int = 3) -> list[tuple[str, float]]:
        return sorted(self.z.items(), key=lambda kv: -abs(kv[1]))[:n]


@dataclass
class DetectionResult:
    timestamp: datetime
    threshold: float
    services: dict[str, ServiceDetection]
    anomalous: list[str]
    primary: str | None
    prometheus_ok: bool = True

    def anomaly_payload(self) -> dict:
        """Shape served at /api/anomaly/current and consumed by the orchestrator."""
        if not self.primary:
            return {"anomaly_detected": False, "timestamp": self.timestamp.isoformat(),
                    "anomalous_services": [], "threshold": self.threshold}
        d = self.services[self.primary]
        return {
            "anomaly_detected": True,
            "timestamp": self.timestamp.isoformat(),
            "affected_service": d.service,
            "anomaly_type": d.anomaly_type,
            "severity_score": round(d.severity, 4),
            "iforest_score": round(d.score, 4),
            "threshold": round(self.threshold, 4),
            "feature_deltas": {k: round(v, 2) for k, v in d.z.items()},
            "evidence": d.evidence,
            "flags": d.flags,
            "detected_at": d.confirmed_at,
            "first_flagged_at": d.first_flagged_at,
            "lstm": asdict(d.lstm),
            "anomalous_services": [
                {"service": s, "severity": round(self.services[s].severity, 4),
                 "anomaly_type": self.services[s].anomaly_type,
                 "first_flagged_at": self.services[s].first_flagged_at}
                for s in self.anomalous
            ],
        }

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "threshold": self.threshold,
            "anomalous": self.anomalous,
            "primary": self.primary,
            "prometheus_ok": self.prometheus_ok,
            "services": {k: asdict(v) for k, v in self.services.items()},
        }


class Detector:
    def __init__(self) -> None:
        if not artefacts.models_present():
            raise ModelsMissing("trained models not found — run `python -m novasurge train`")
        self.normalizer = Normalizer.load(artefacts.normalizer_path())
        self.iforest = joblib.load(artefacts.iforest_path())
        ckpt = torch.load(artefacts.forecaster_path(), map_location="cpu", weights_only=True)
        self.forecaster = TelemetryForecaster(**ckpt["config"])
        self.forecaster.load_state_dict(ckpt["state_dict"])
        self.forecaster.eval()
        card = json.loads(artefacts.model_card_path().read_text())
        self.card = card
        self.threshold = float(card["iforest"]["threshold"])
        self.residual_mean = float(card["forecaster"]["residual_mean"])
        self.residual_std = max(float(card["forecaster"]["residual_std"]), 1e-3)

        self._windows = {s: deque(maxlen=3) for s in SERVICES}
        self._z_hist = {s: deque(maxlen=config.LSTM_HISTORY) for s in SERVICES}
        self._prev_forecast: dict[str, np.ndarray | None] = {s: None for s in SERVICES}
        self._confirmed = {s: False for s in SERVICES}
        self._clear_streak = {s: 0 for s in SERVICES}
        self._first_flag: dict[str, str | None] = {s: None for s in SERVICES}
        self._confirmed_at: dict[str, str | None] = {s: None for s in SERVICES}
        self._healthy_restarts: dict[str, int | None] = {s: None for s in SERVICES}
        self._stable_ready: dict[str, int | None] = {s: None for s in SERVICES}
        self._prev_state: dict[str, ServiceState | None] = {s: None for s in SERVICES}
        self._lost: dict[str, dict] = {s: {} for s in SERVICES}
        # What was observed during the current anomaly episode (kept until it clears),
        # so a diagnosis made a tick later still sees the incident, not a quiet window.
        self._episode: dict[str, dict] = {s: {} for s in SERVICES}
        self.last: DetectionResult | None = None

    # ── public ───────────────────────────────────────────────────────────────
    def step(self, snap: Snapshot) -> DetectionResult:
        zs, missing = {}, {}
        for svc in SERVICES:
            zs[svc], missing[svc] = self.normalizer.transform(svc, snap.services[svc].features)

        # one batched IF call: current vectors + every forecast step
        forecasts = self._forecast(zs)
        batch = [zs[s] for s in SERVICES]
        for svc in SERVICES:
            if forecasts.get(svc) is not None:
                batch.extend(forecasts[svc])
        scores = self.iforest.decision_function(np.asarray(batch, np.float32))
        current = dict(zip(SERVICES, scores[:len(SERVICES)]))
        offset = len(SERVICES)
        forecast_scores: dict[str, list[float]] = {}
        for svc in SERVICES:
            if forecasts.get(svc) is not None:
                forecast_scores[svc] = [float(x) for x in scores[offset:offset + config.LSTM_HORIZON]]
                offset += config.LSTM_HORIZON

        results = {}
        for svc in SERVICES:
            results[svc] = self._evaluate(svc, snap, snap.services[svc], zs[svc], missing[svc],
                                          float(current[svc]), forecasts.get(svc),
                                          forecast_scores.get(svc, []))
        anomalous = [s for s in SERVICES if results[s].confirmed]
        primary = min(anomalous, key=lambda s: (results[s].first_flagged_at or "~", -results[s].severity,
                                                 -len(topology.call_path(s)))) if anomalous else None
        self.last = DetectionResult(snap.timestamp, self.threshold, results, anomalous, primary,
                                    snap.prometheus_ok)
        return self.last

    # ── internals ────────────────────────────────────────────────────────────
    def _forecast(self, zs: dict[str, np.ndarray]) -> dict[str, np.ndarray | None]:
        ready = []
        for svc in SERVICES:
            self._z_hist[svc].append(zs[svc])
            if len(self._z_hist[svc]) == config.LSTM_HISTORY:
                ready.append(svc)
        out: dict[str, np.ndarray | None] = {s: None for s in SERVICES}
        if not ready:
            return out
        x = torch.from_numpy(np.stack([np.stack(self._z_hist[s]) for s in ready]).astype(np.float32))
        with torch.no_grad():
            pred = self.forecaster(x).numpy()
        for i, svc in enumerate(ready):
            out[svc] = pred[i]
        return out

    def _evaluate(self, svc: str, snap: Snapshot, st: ServiceState, z: np.ndarray, missing: list[str],
                  score: float, forecast: np.ndarray | None, f_scores: list[float]) -> ServiceDetection:
        hz = harmful_z(z)
        harmful_max = float(hz.max())
        z_map = {f: float(z[i]) for i, f in enumerate(FEATURES)}
        flags: list[str] = []

        if score < self.threshold and harmful_max >= Z_SUPPORT:
            flags.append("iforest")
        for i, feat in enumerate(FEATURES):
            if hz[i] >= Z_ALERT:
                flags.append(f"zscore:{feat}")

        structural = self._structural_flags(svc, st)
        flags += structural
        strong = any(f in STRONG_FLAGS for f in structural)

        window_anomalous = bool(flags)
        win = self._windows[svc]
        win.append(window_anomalous)
        ts = snap.timestamp.isoformat()
        if window_anomalous and self._first_flag[svc] is None:
            self._first_flag[svc] = ts

        if not self._confirmed[svc]:
            if strong or sum(win) >= CONFIRM_WINDOWS:
                self._confirmed[svc] = True
                self._confirmed_at[svc] = ts
                self._clear_streak[svc] = 0
            elif not window_anomalous and not any(win):
                self._first_flag[svc] = None
        else:
            self._clear_streak[svc] = 0 if window_anomalous else self._clear_streak[svc] + 1
            if self._clear_streak[svc] >= CLEAR_WINDOWS:
                self._confirmed[svc] = False
                self._first_flag[svc] = None
                self._confirmed_at[svc] = None

        if not self._confirmed[svc] and not window_anomalous and st.desired_replicas and \
                st.ready_replicas >= st.desired_replicas:
            self._healthy_restarts[svc] = st.restarts

        severity = self._severity(score, harmful_max, st, structural)
        confirmed = self._confirmed[svc]
        episode = self._episode[svc]
        if not confirmed and not window_anomalous:
            episode.clear()
        anomaly_type, evidence = None, []
        if window_anomalous:
            anomaly_type, evidence = self._classify(svc, st, z_map, structural)
            episode.setdefault("flags", set()).update(flags)
            episode["peak_severity"] = max(episode.get("peak_severity", 0.0), severity)
            if anomaly_type != "unknown" and "type" not in episode:
                episode["type"], episode["evidence"] = anomaly_type, evidence
        if confirmed and episode.get("type"):
            anomaly_type, evidence = episode["type"], episode["evidence"]
            severity = max(severity, round(0.6 * episode["peak_severity"], 4))
        elif confirmed and anomaly_type is None:
            anomaly_type, evidence = "unknown", []
        status = "anomaly" if confirmed else ("degraded" if window_anomalous or score < self.threshold
                                              else "healthy")

        lstm = self._lstm_view(svc, z, forecast, f_scores)
        return ServiceDetection(
            service=svc, score=score, z=z_map, raw=dict(st.features), missing=missing, flags=flags,
            window_anomalous=window_anomalous, confirmed=confirmed, severity=severity, status=status,
            anomaly_type=anomaly_type, evidence=evidence, first_flagged_at=self._first_flag[svc],
            confirmed_at=self._confirmed_at[svc], episode_flags=sorted(episode.get("flags", [])),
            ready_replicas=st.ready_replicas,
            desired_replicas=st.desired_replicas, lstm=lstm,
        )

    def _structural_flags(self, svc: str, st: ServiceState) -> list[str]:
        """
        replicas_lost: Ready count fell below its last stable level (a replica
        died) — unlike a scale-up, where new pods are simply still starting.
        """
        flags = []
        stable = self._stable_ready[svc]
        prev = self._prev_state[svc]
        self._prev_state[svc] = st
        lost = False
        if prev is not None and prev.ready_pods:
            # A pod that was serving last tick and no longer is — unless the
            # deployment was scaled down / rolled out, or NovaSurge quarantined it.
            vanished = set(prev.ready_pods) - set(st.ready_pods) - set(st.quarantined_pods)
            expected = st.desired_replicas < prev.desired_replicas or st.generation != prev.generation
            lost = bool(vanished) and not expected
            if lost:
                self._lost[svc] = {"gone": sorted(vanished - set(st.pod_names)),
                                   "unready": sorted(vanished & set(st.pod_names))}
        if st.desired_replicas and st.ready_replicas >= st.desired_replicas and not lost:
            self._lost[svc] = {}
        if st.desired_replicas > 0:
            if st.ready_replicas == 0:
                flags.append("all_replicas_down")
            elif lost or (stable is not None and st.ready_replicas < min(st.desired_replicas, stable)):
                flags.append("replicas_lost")
        healthy_restarts = self._healthy_restarts[svc]
        if healthy_restarts is not None and st.restarts > healthy_restarts:
            flags.append("container_restarted")
        if st.desired_replicas and st.desired_replicas < st.baseline_min_replicas:
            flags.append("capacity_below_baseline")
        elif st.hpa_max and st.hpa_max < st.baseline_min_replicas:
            flags.append("capacity_below_baseline")
        if st.scrape_up is not None and st.scrape_up <= 0.5:
            flags.append("metrics_unreachable")
        return flags

    def _severity(self, score: float, harmful_max: float, st: ServiceState, structural: list[str]) -> float:
        """0..1, saturating smoothly so the most affected service still ranks first."""
        parts = [
            0.9 * min(max((self.threshold - score) / 0.3, 0.0), 1.0),
            0.95 * (1.0 - math.exp(-max(harmful_max - Z_SUPPORT, 0.0) / 8.0)),
        ]
        if "all_replicas_down" in structural:
            parts.append(0.95)
        elif "replicas_lost" in structural and st.desired_replicas:
            parts.append(0.4 + 0.4 * (1 - st.ready_ratio))
        if "container_restarted" in structural:
            parts.append(0.5)
        if "capacity_below_baseline" in structural:
            parts.append(0.5)
        if "metrics_unreachable" in structural:
            parts.append(0.6)
        combined = 1.0 - math.prod(1.0 - p for p in parts)
        return round(min(combined, 0.9999), 4)

    def _classify(self, svc: str, st: ServiceState, z: dict[str, float], structural: list[str]
                  ) -> tuple[str, list[str]]:
        ev: list[str] = []
        raw = st.features
        base = self.normalizer.baseline(svc)
        restarted = (self._healthy_restarts[svc] is not None and st.restarts > self._healthy_restarts[svc])
        if structural:
            ev.append(f"replicas ready {st.ready_replicas}/{st.desired_replicas}"
                      f" (declared minimum {st.baseline_min_replicas})")
        if "metrics_unreachable" in structural:
            ev.append(f"metrics endpoint unreachable on {(1 - (st.scrape_up or 0)):.0%} of pods")

        def say(feat: str, unit: str = "") -> str:
            val = raw.get(feat)
            shown = "n/a" if val is None else (f"{val:.1%}" if "rate" in feat and "request" not in feat
                                                else f"{val:.2f}{unit}")
            ref = base.get(feat, 0.0)
            ref_s = f"{ref:.1%}" if "rate" in feat and "request" not in feat else f"{ref:.2f}{unit}"
            return f"{feat}={shown} vs baseline {ref_s} (z={z[feat]:+.1f})"

        if "capacity_below_baseline" in structural:
            ev.append(f"autoscaler bounds min={st.hpa_min} max={st.hpa_max} below declared "
                      f"minimum {st.baseline_min_replicas}")
            return "replica_exhaustion", ev
        if "metrics_unreachable" in structural and not restarted and st.pods > 0:
            ev.append(say("caller_error_rate"))
            ev.append(say("request_rate", " req/s"))
            ev.append("pods are running (no container restarts) but cannot be reached over the pod network")
            return "network_partition", ev
        if any(f in structural for f in ("all_replicas_down", "replicas_lost", "container_restarted")):
            lost = self._lost[svc]
            unready_now = sorted(set(st.pod_names) - set(st.ready_pods))
            if restarted:
                ev.append(f"container restarts increased to {st.restarts}")
            if lost.get("gone"):
                ev.append(f"Ready pod(s) {', '.join(lost['gone'])} disappeared without a scale-down or rollout")
            elif unready_now and not restarted and "all_replicas_down" not in structural:
                ev.append(f"pod(s) {', '.join(unready_now)} still running but failing readiness")
                ev.append(say("p99_latency_ms", "ms"))
                return "pod_unready", ev
            ev.append(say("caller_error_rate"))
            return "pod_crash", ev
        if z["cpu_throttle_ratio"] >= 4.0 or (raw.get("cpu_throttle_ratio") or 0) >= 0.25:
            ev.append(say("cpu_throttle_ratio"))
            ev.append(say("p99_latency_ms", "ms"))
            return "cpu_throttle", ev
        # Traffic vanished while callers fail and the service itself is not slow:
        # requests are not reaching it at all.
        baseline_rps = base.get("request_rate") or 0.0
        if (z["caller_error_rate"] >= Z_ALERT and z["request_rate"] <= -Z_ALERT
                and (raw.get("request_rate") or 0.0) < 0.15 * baseline_rps
                and z["p99_latency_ms"] < 4.0 and not restarted):
            ev.append(say("caller_error_rate"))
            ev.append(say("request_rate", " req/s"))
            return "network_partition", ev
        if z["memory_mb"] >= Z_ALERT:
            ev.append(say("memory_mb", "MB"))
            return "oom_kill", ev
        if max(z["p99_latency_ms"], z["caller_p99_ms"]) >= 4.0 and z["error_rate"] < Z_ALERT:
            ev.append(say("p99_latency_ms", "ms"))
            ev.append(say("caller_p99_ms", "ms"))
            return "high_latency", ev
        if max(z["error_rate"], z["caller_error_rate"]) >= 4.0:
            ev.append(say("error_rate"))
            ev.append(say("caller_error_rate"))
            return "error_spike", ev
        top = sorted(z.items(), key=lambda kv: -abs(kv[1]))[:2]
        ev += [say(f) for f, _ in top]
        return "unknown", ev

    def _lstm_view(self, svc: str, z: np.ndarray, forecast: np.ndarray | None,
                   f_scores: list[float]) -> LstmView:
        view = LstmView()
        prev = self._prev_forecast[svc]
        if prev is not None:
            r = float(np.linalg.norm(z - prev[0]) / math.sqrt(len(FEATURES)))
            view.residual_z = round((r - self.residual_mean) / self.residual_std, 3)
        self._prev_forecast[svc] = forecast
        if forecast is None:
            return view
        view.ready = True
        view.forecast_scores = [round(x, 4) for x in f_scores]
        view.predicted_score_60s = round(f_scores[-1], 4) if f_scores else None
        end_harm = float(harmful_z(forecast[-1].astype(np.float32)).max())
        view.predicted_anomaly = bool(f_scores and f_scores[-1] < self.threshold and end_harm >= Z_SUPPORT)
        return view
