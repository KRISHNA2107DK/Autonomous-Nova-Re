"""
Central configuration. Every path is absolute (derived from this file), so the
platform behaves identically no matter which directory it is launched from.

Runtime state (SQLite, live JSON state, telemetry) lives in NOVASURGE_HOME,
outside the repository: the repo may sit in a synced folder (OneDrive, Dropbox)
where SQLite locking and constant churn are a problem. Finished campaign
reports are written once into <repo>/reports/.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parent


def _default_home() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "AutoHeal"
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "novasurge"


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


NOVASURGE_HOME = Path(_env("NOVASURGE_HOME", str(_default_home())))
RUNTIME_DIR = NOVASURGE_HOME / "runtime"
STATE_DIR = RUNTIME_DIR / "state"
DATA_DIR = RUNTIME_DIR / "data"
LOGS_DIR = RUNTIME_DIR / "logs"
DB_PATH = STATE_DIR / "novasurge.db"
TOOLS_DIR = NOVASURGE_HOME / "bin"

MODELS_DIR = PACKAGE_DIR / "models"
REPORTS_DIR = REPO_ROOT / "reports"
K8S_DIR = REPO_ROOT / "k8s"
DASHBOARD_DIST = REPO_ROOT / "dashboard" / "dist"
CAMPAIGN_FILE = REPO_ROOT / "config" / "campaign.json"

for _d in (STATE_DIR, DATA_DIR, LOGS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ── Cluster ──────────────────────────────────────────────────────────────────
CLUSTER_NAME = _env("NOVASURGE_CLUSTER", "novasurge")
KUBE_CONTEXT = _env("NOVASURGE_KUBE_CONTEXT", f"kind-{CLUSTER_NAME}")
NAMESPACE = _env("NOVASURGE_NAMESPACE", "shopfusion")
SYSTEM_NAMESPACE = "novasurge-system"

# ── Endpoints (host side) ────────────────────────────────────────────────────
PROMETHEUS_URL = _env("PROMETHEUS_URL", "http://127.0.0.1:30090")
GATEWAY_URL = _env("GATEWAY_URL", "http://127.0.0.1:30080")
API_HOST = _env("NOVASURGE_API_HOST", "127.0.0.1")
API_PORT = int(_env("NOVASURGE_API_PORT", "8000"))
API_URL = _env("NOVASURGE_API_URL", f"http://{API_HOST}:{API_PORT}")

# ── Telemetry / detection cadence ────────────────────────────────────────────
STEP_SECONDS = 5            # detector tick == Prometheus scrape interval
RATE_WINDOW = "30s"         # PromQL rate() window
LSTM_HISTORY = 12           # 12 x 5s = 60s of history
LSTM_HORIZON = 12           # forecast 60s ahead

# ── Simulation (dry-run / tests) ─────────────────────────────────────────────
SIMULATION = _env("NOVASURGE_SIMULATION", "false").lower() in {"1", "true", "yes"}
