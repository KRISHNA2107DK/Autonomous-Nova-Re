"""
Test fixtures. Every test runs against the stateful simulator with all
writable state (SQLite, models, reports) redirected into a temp directory,
so the suite never touches a real cluster or real artefacts.
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
import time
from pathlib import Path

import pytest

from novasurge import config


@pytest.fixture(scope="session", autouse=True)
def no_llm_calls():
    """Tests never spend real API calls; the planner's LLM path is tested with a fake client."""
    import os
    os.environ["NOVASURGE_LLM_PROVIDER"] = "none"


@pytest.fixture(scope="session")
def sim_home():
    base = config.NOVASURGE_HOME / "test-runs"
    base.mkdir(parents=True, exist_ok=True)
    home = Path(tempfile.mkdtemp(prefix="run-", dir=base))
    config.SIMULATION = True
    config.MODELS_DIR = home / "models"
    config.DB_PATH = home / "state.db"
    config.DATA_DIR = home / "data"
    config.REPORTS_DIR = home / "reports"
    for d in (config.MODELS_DIR, config.DATA_DIR):
        d.mkdir(parents=True, exist_ok=True)
    yield home
    shutil.rmtree(home, ignore_errors=True)


@pytest.fixture(scope="session")
def trained_models(sim_home):
    """Train once per session on simulated baseline telemetry."""
    from novasurge import sim
    from novasurge.cluster import set_cluster
    from novasurge.ml.train import train
    from novasurge.telemetry import set_telemetry

    sim.reset()
    set_cluster(sim.get_simulated_cluster())
    set_telemetry(sim.get_simulated_telemetry())
    end = time.time()
    card = train(start=end - 600, end=end, epochs=60, quiet=True)
    return card


@pytest.fixture()
def world(trained_models):
    """A fresh simulated cluster + telemetry, installed as the active backends."""
    from novasurge import sim, state_db
    from novasurge.cluster import set_cluster
    from novasurge.telemetry import set_telemetry

    sim.reset()
    cluster, telemetry = sim.get_simulated_cluster(), sim.get_simulated_telemetry()
    set_cluster(cluster)
    set_telemetry(telemetry)
    state_db.reset_runtime(history=True)
    return cluster, telemetry


def run(coro):
    return asyncio.run(coro)
