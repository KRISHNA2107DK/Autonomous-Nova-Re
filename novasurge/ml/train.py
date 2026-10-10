"""
Train NovaSurge's detection models on *real* baseline telemetry.

    python -m novasurge train [--minutes 8] [--include-recorded]

Pipeline
  1. Pull the baseline window from Prometheus with exactly the PromQL used for
     live inference (telemetry.PrometheusTelemetry.history).
  2. Fit per-service robust normalisation (ml.features.Normalizer).
  3. Isolation Forest on normalised vectors, with Gaussian jitter augmentation
     so every feature has spread (an IF cannot split on a constant feature, so
     without it an error-rate explosion on a zero-error baseline is invisible).
  4. Calibrate the anomaly threshold on the training scores and measure the
     false-positive rate on a held-out (later-in-time) slice.
  5. Probe detection sensitivity with synthetic single-feature faults.
  6. Train the LSTM forecaster on the same series (+ optionally the telemetry
     NovaSurge recorded during past chaos campaigns, which teaches it what
     degradation and recovery dynamics look like) and compare it against a
     naive persistence forecast.
  7. Persist artefacts + model_card.json.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import torch
from sklearn.ensemble import IsolationForest
from torch import nn

from novasurge import config
from novasurge.ml.features import HARMFUL_DIRECTION, Normalizer
from novasurge.ml.forecaster import TelemetryForecaster
from novasurge.telemetry import FEATURES, get_telemetry
from novasurge.topology import SERVICES

log = logging.getLogger("novasurge.train")

# Artefact locations are resolved at call time so a dry-run can redirect
# config.MODELS_DIR without touching the real models.
def normalizer_path(): return config.MODELS_DIR / "normalizer.json"          # noqa: E704
def iforest_path(): return config.MODELS_DIR / "iforest.joblib"              # noqa: E704
def forecaster_path(): return config.MODELS_DIR / "lstm_forecaster.pt"       # noqa: E704
def model_card_path(): return config.MODELS_DIR / "model_card.json"          # noqa: E704
def recorded_telemetry_path(): return config.DATA_DIR / "telemetry.jsonl"    # noqa: E704

AUGMENT_COPIES = 4
AUGMENT_SIGMA = 0.75
HOLDOUT_FRACTION = 0.2
PROBE_Z = 8.0
CALIBRATION_Z = 4.0


_QUIET = False


def _say(msg: str) -> None:
    if not _QUIET:
        print(f"[train] {msg}", flush=True)


def models_present() -> bool:
    return all(p.exists() for p in (normalizer_path(), iforest_path(), forecaster_path(), model_card_path()))


# ── data ─────────────────────────────────────────────────────────────────────
def _split_contiguous(series: list[tuple[float, dict]], step: int) -> list[list[tuple[float, dict]]]:
    runs, cur, prev = [], [], None
    for t, row in series:
        if prev is not None and t - prev > step * 1.5:
            runs.append(cur)
            cur = []
        cur.append((t, row))
        prev = t
    if cur:
        runs.append(cur)
    return runs


def load_recorded(normalizer: Normalizer) -> list[np.ndarray]:
    """Per-service z-series recorded by the live detector (includes chaos rounds)."""
    recorded = recorded_telemetry_path()
    if not recorded.exists():
        return []
    by_svc: dict[str, list[tuple[float, dict]]] = {s: [] for s in SERVICES}
    with recorded.open() as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            for svc, feats in rec.get("features", {}).items():
                if svc in by_svc:
                    by_svc[svc].append((rec["t"], feats))
    out = []
    for svc, series in by_svc.items():
        for run in _split_contiguous(sorted(series, key=lambda x: x[0]), config.STEP_SECONDS):
            if len(run) >= config.LSTM_HISTORY + config.LSTM_HORIZON:
                out.append(np.stack([normalizer.transform(svc, row)[0] for _, row in run]))
    return out


def _windows(series: list[np.ndarray], history: int, horizon: int, holdout: float
             ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Sliding windows; the last `holdout` fraction (in time) of *each* series validates."""
    xt, yt, xv, yv = [], [], [], []
    for z in series:
        n = len(z) - history - horizon + 1
        if n <= 0:
            continue
        n_val = max(1, int(n * holdout))
        for i in range(n):
            xs, ys = (xv, yv) if i >= n - n_val else (xt, yt)
            xs.append(z[i:i + history])
            ys.append(z[i + history:i + history + horizon])
    as_arr = lambda a, steps: (np.asarray(a, np.float32) if a
                               else np.zeros((0, steps, len(FEATURES)), np.float32))
    return as_arr(xt, history), as_arr(yt, horizon), as_arr(xv, history), as_arr(yv, horizon)


# ── Isolation Forest ─────────────────────────────────────────────────────────
def _fit_iforest(z_train: np.ndarray, seed: int) -> IsolationForest:
    rng = np.random.default_rng(seed)
    jitter = [z_train + rng.normal(0.0, AUGMENT_SIGMA, z_train.shape) for _ in range(AUGMENT_COPIES)]
    x_aug = np.vstack([z_train, *jitter]).astype(np.float32)
    model = IsolationForest(n_estimators=200, max_samples=256, contamination="auto",
                            random_state=seed, n_jobs=-1)
    model.fit(x_aug)
    return model


def _calibrate_threshold(model: IsolationForest, train_scores: np.ndarray, z_ref: np.ndarray
                         ) -> tuple[float, dict]:
    """
    Place the threshold between the two populations it must separate:
      clean_floor   — 0.1% quantile of scores on healthy training data
      weakest_probe — the highest (least anomalous) median score among
                      single-feature faults of CALIBRATION_Z sigmas
    Isolation-Forest scores saturate outside the training range (every value
    beyond the max lands in the same leaf), so a fixed numeric cut-off would
    either miss moderate faults or fire on healthy noise; the midpoint is the
    max-margin choice given the data.
    """
    clean_floor = float(np.quantile(train_scores, 0.001))
    probe_medians = []
    for i, feat in enumerate(FEATURES):
        probe = z_ref.copy()
        probe[:, i] = (HARMFUL_DIRECTION[feat] or 1) * CALIBRATION_Z
        probe_medians.append(float(np.median(model.decision_function(probe))))
    weakest = max(probe_medians)
    threshold = (clean_floor + weakest) / 2 if weakest < clean_floor else clean_floor - 0.01
    return float(threshold), {"clean_floor": clean_floor, "weakest_probe": weakest,
                              "probe_medians": dict(zip(FEATURES, probe_medians))}


def _probe_detection(model: IsolationForest, z_ref: np.ndarray, threshold: float) -> dict[str, float]:
    """Detection rate when a single feature deviates PROBE_Z robust sigmas in its harmful direction."""
    rates = {}
    for i, feat in enumerate(FEATURES):
        probe = z_ref.copy()
        direction = HARMFUL_DIRECTION[feat] or 1
        probe[:, i] = direction * PROBE_Z
        rates[feat] = round(float(np.mean(model.decision_function(probe) < threshold)), 3)
    return rates


# ── LSTM ─────────────────────────────────────────────────────────────────────
def _fit_forecaster(x: np.ndarray, y: np.ndarray, x_val: np.ndarray, y_val: np.ndarray,
                    epochs: int, seed: int) -> tuple[TelemetryForecaster, dict]:
    torch.manual_seed(seed)
    xt, yt = torch.from_numpy(x), torch.from_numpy(y)
    xv, yv = torch.from_numpy(x_val), torch.from_numpy(y_val)

    model = TelemetryForecaster(len(FEATURES), hidden=48, horizon=config.LSTM_HORIZON)
    opt = torch.optim.Adam(model.parameters(), lr=3e-3, weight_decay=1e-5)
    loss_fn = nn.MSELoss()
    best_state, best_val, patience, bad = None, float("inf"), 20, 0
    gen = torch.Generator().manual_seed(seed)
    for epoch in range(epochs):
        model.train()
        perm = torch.randperm(len(xt), generator=gen)
        for b in range(0, len(xt), 64):
            sel = perm[b:b + 64]
            opt.zero_grad()
            loss = loss_fn(model(xt[sel]), yt[sel])
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
        model.eval()
        with torch.no_grad():
            val = loss_fn(model(xv), yv).item()
        if val < best_val - 1e-5:
            best_val, bad = val, 0
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        else:
            bad += 1
            if bad >= patience:
                break
    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        pred = model(xv)
        persistence = xv[:, -1:, :].expand_as(yv)
        val_mse = loss_fn(pred, yv).item()
        naive_mse = loss_fn(persistence, yv).item()
        step1 = torch.linalg.norm(pred[:, 0, :] - yv[:, 0, :], dim=1) / np.sqrt(len(FEATURES))
    stats = {
        "epochs_run": epoch + 1,
        "train_windows": int(len(xt)),
        "val_windows": int(len(xv)),
        "val_mse": round(val_mse, 5),
        "persistence_val_mse": round(naive_mse, 5),
        "skill_vs_persistence": round(1.0 - val_mse / naive_mse, 4) if naive_mse > 0 else 0.0,
        "residual_mean": float(step1.mean()),
        "residual_std": float(step1.std()) if len(step1) > 1 else 0.1,
    }
    return model, stats


# ── entry point ──────────────────────────────────────────────────────────────
def train(minutes: float = 8.0, start: float | None = None, end: float | None = None,
          include_recorded: bool = False, epochs: int = 300, seed: int = 42, quiet: bool = False) -> dict:
    global _QUIET
    _QUIET = quiet
    end = end or time.time()
    start = start or end - minutes * 60
    source = get_telemetry()
    _say(f"pulling baseline telemetry {datetime.fromtimestamp(start, timezone.utc):%H:%M:%S}"
         f" -> {datetime.fromtimestamp(end, timezone.utc):%H:%M:%S} UTC ({(end - start) / 60:.1f} min)")
    history = source.history(start, end, config.STEP_SECONDS)

    rows_by_service = {svc: [row for _, row in history.get(svc, [])] for svc in SERVICES}
    min_rows = min(len(r) for r in rows_by_service.values())
    needed = config.LSTM_HISTORY + config.LSTM_HORIZON + 10
    if min_rows < needed:
        raise RuntimeError(f"baseline too short: {min_rows} samples per service, need >= {needed} "
                           f"({needed * config.STEP_SECONDS / 60:.1f} min of steady traffic)")
    _say(f"samples per service: {', '.join(f'{s}={len(r)}' for s, r in rows_by_service.items())}")

    normalizer = Normalizer.fit(rows_by_service)

    z_series: dict[str, np.ndarray] = {}
    for svc in SERVICES:
        z_series[svc] = np.stack([normalizer.transform(svc, row)[0] for row in rows_by_service[svc]])

    # time-ordered holdout per service
    train_parts, hold_parts = [], []
    for z in z_series.values():
        cut = int(len(z) * (1 - HOLDOUT_FRACTION))
        train_parts.append(z[:cut])
        hold_parts.append(z[cut:])
    z_train, z_hold = np.vstack(train_parts), np.vstack(hold_parts)

    _say(f"training Isolation Forest on {len(z_train)} vectors (+{AUGMENT_COPIES}x jitter augmentation)")
    iforest = _fit_iforest(z_train, seed)
    train_scores = iforest.decision_function(z_train)
    threshold, calib = _calibrate_threshold(iforest, train_scores, z_hold)
    _say(f"calibration: clean-data floor {calib['clean_floor']:.4f}, weakest 4-sigma fault probe "
         f"{calib['weakest_probe']:.4f} -> threshold at the midpoint")
    hold_scores = iforest.decision_function(z_hold)
    fp_rate = float(np.mean(hold_scores < threshold))
    probes = _probe_detection(iforest, z_hold, threshold)
    _say(f"threshold={threshold:.4f}  holdout false-positive rate={fp_rate:.4f}")
    _say("single-feature fault probe detection: " + ", ".join(f"{k}={v:.0%}" for k, v in probes.items()))

    series = list(z_series.values())
    recorded = load_recorded(normalizer) if include_recorded else []
    if recorded:
        _say(f"adding {len(recorded)} recorded telemetry runs (incl. chaos rounds) to forecaster training")
    x, y, x_val, y_val = _windows(series + recorded, config.LSTM_HISTORY, config.LSTM_HORIZON,
                                  HOLDOUT_FRACTION)
    _say(f"training LSTM forecaster on {len(x)} windows, validating on {len(x_val)} "
         f"({config.LSTM_HISTORY} steps in -> {config.LSTM_HORIZON} steps out)")
    forecaster, lstm_stats = _fit_forecaster(x, y, x_val, y_val, epochs, seed)
    _say(f"forecaster val MSE={lstm_stats['val_mse']}  persistence MSE={lstm_stats['persistence_val_mse']}"
         f"  skill={lstm_stats['skill_vs_persistence']:+.1%}")

    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    normalizer.save(normalizer_path())
    joblib.dump(iforest, iforest_path())
    torch.save({"state_dict": forecaster.state_dict(), "config": forecaster.config()}, forecaster_path())

    card = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "data": {
            "source": "prometheus" if not config.SIMULATION else "simulation",
            "window_start": datetime.fromtimestamp(start, timezone.utc).isoformat(),
            "window_end": datetime.fromtimestamp(end, timezone.utc).isoformat(),
            "step_seconds": config.STEP_SECONDS,
            "samples_per_service": {s: len(r) for s, r in rows_by_service.items()},
            "recorded_runs_used": len(recorded),
        },
        "features": FEATURES,
        "iforest": {
            "n_estimators": 200,
            "augmentation": {"copies": AUGMENT_COPIES, "sigma": AUGMENT_SIGMA},
            "threshold": threshold,
            "calibration": calib,
            "train_score_quantiles": {q: float(np.quantile(train_scores, q)) for q in (0.001, 0.01, 0.5)},
            "holdout_false_positive_rate": fp_rate,
            "fault_probe_z": PROBE_Z,
            "fault_probe_detection_rate": probes,
        },
        "forecaster": {
            "history_steps": config.LSTM_HISTORY,
            "horizon_steps": config.LSTM_HORIZON,
            **forecaster.config(),
            **lstm_stats,
        },
        "baseline_medians": {svc: normalizer.baseline(svc) for svc in SERVICES},
    }
    model_card_path().write_text(json.dumps(card, indent=2))
    _say(f"artefacts written to {config.MODELS_DIR}")
    return card
