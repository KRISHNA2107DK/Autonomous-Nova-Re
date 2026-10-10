"""
Per-service robust normalisation.

Each service has its own healthy operating point (payment p99 ~250ms is normal,
product p99 ~10ms is normal), so a single pooled scaler — what the original
code used — makes a slow-but-healthy service look anomalous and hides real
regressions on fast services. Every feature is instead expressed as a robust
z-score against *that service's own* baseline:

    z = (x - median_s) / scale_s,     scale_s = max(1.4826 * MAD, floor)

The floor encodes measurement resolution (e.g. Prometheus histogram buckets,
scheduler jitter) so near-constant baselines (error_rate == 0) do not turn
every 1-in-1000 blip into an infinite z-score.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from novasurge.telemetry import FEATURES
from novasurge.topology import SERVICES

Z_CLIP = 25.0

# feature -> (absolute floor, floor relative to |median|)
SCALE_FLOORS: dict[str, tuple[float, float]] = {
    "request_rate": (0.5, 0.10),
    "error_rate": (0.02, 0.0),
    "p99_latency_ms": (15.0, 0.15),
    "inflight": (1.0, 0.25),
    "cpu_cores": (0.01, 0.20),
    "cpu_throttle_ratio": (0.05, 0.0),
    "memory_mb": (10.0, 0.10),
    "caller_error_rate": (0.02, 0.0),
    "caller_p99_ms": (15.0, 0.15),
}

# Direction in which a deviation hurts users / indicates a fault.
#   +1: only increases are harmful, -1: only decreases, 0: both directions.
HARMFUL_DIRECTION: dict[str, int] = {
    "request_rate": -1,
    "error_rate": +1,
    "p99_latency_ms": +1,
    "inflight": +1,
    "cpu_cores": +1,
    "cpu_throttle_ratio": +1,
    "memory_mb": +1,
    "caller_error_rate": +1,
    "caller_p99_ms": +1,
}


@dataclass
class FeatureStats:
    median: float
    scale: float


class Normalizer:
    def __init__(self, stats: dict[str, dict[str, FeatureStats]]):
        self.stats = stats

    # ── fitting ──────────────────────────────────────────────────────────────
    @classmethod
    def fit(cls, rows_by_service: dict[str, list[dict]]) -> "Normalizer":
        stats: dict[str, dict[str, FeatureStats]] = {}
        for svc in SERVICES:
            rows = rows_by_service.get(svc, [])
            stats[svc] = {}
            for feat in FEATURES:
                vals = np.array([r[feat] for r in rows if r.get(feat) is not None], dtype=float)
                abs_floor, rel_floor = SCALE_FLOORS[feat]
                if vals.size == 0:
                    stats[svc][feat] = FeatureStats(median=0.0, scale=abs_floor)
                    continue
                med = float(np.median(vals))
                mad = float(np.median(np.abs(vals - med)))
                scale = max(1.4826 * mad, abs_floor, rel_floor * abs(med))
                stats[svc][feat] = FeatureStats(median=med, scale=scale)
        return cls(stats)

    # ── transform ────────────────────────────────────────────────────────────
    def transform(self, service: str, features: dict[str, float | None]) -> tuple[np.ndarray, list[str]]:
        """Return (z-vector, missing-feature names). Missing values map to 0 (neutral)."""
        z = np.zeros(len(FEATURES), dtype=np.float32)
        missing = []
        svc_stats = self.stats[service]
        for i, feat in enumerate(FEATURES):
            val = features.get(feat)
            if val is None or not math.isfinite(val):
                missing.append(feat)
                continue
            st = svc_stats[feat]
            z[i] = float(np.clip((val - st.median) / st.scale, -Z_CLIP, Z_CLIP))
        return z, missing

    def baseline(self, service: str) -> dict[str, float]:
        return {f: s.median for f, s in self.stats[service].items()}

    # ── persistence ──────────────────────────────────────────────────────────
    def to_dict(self) -> dict:
        return {svc: {f: {"median": s.median, "scale": s.scale} for f, s in feats.items()}
                for svc, feats in self.stats.items()}

    @classmethod
    def from_dict(cls, data: dict) -> "Normalizer":
        return cls({svc: {f: FeatureStats(**v) for f, v in feats.items()} for svc, feats in data.items()})

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, path: Path) -> "Normalizer":
        return cls.from_dict(json.loads(path.read_text()))


def harmful_z(z: np.ndarray) -> np.ndarray:
    """Project z onto the harmful direction of each feature (>= 0 means harmful)."""
    out = np.empty_like(z)
    for i, feat in enumerate(FEATURES):
        d = HARMFUL_DIRECTION[feat]
        out[i] = abs(z[i]) if d == 0 else d * z[i]
    return out
