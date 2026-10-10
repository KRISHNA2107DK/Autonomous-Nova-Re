"""
Simulation backend for `--dry-run` and the test-suite.

A dry run executes the *same* orchestrator, detector, RCA, decision engine,
injectors and remediators as a live run — only the Cluster and TelemetrySource
are swapped for stateful simulations. Runtime state, models and reports are
redirected to separate locations so a dry run never touches live artefacts.
"""

from __future__ import annotations

import time

from novasurge import config

_cluster = None
_telemetry = None


def configure() -> None:
    """Redirect all writable state to simulation-only locations."""
    sim_home = config.NOVASURGE_HOME / "sim"
    config.SIMULATION = True
    config.MODELS_DIR = sim_home / "models"
    config.DB_PATH = sim_home / "state.db"
    config.DATA_DIR = sim_home / "data"
    config.REPORTS_DIR = config.REPO_ROOT / "reports" / "dry-run"
    for d in (config.MODELS_DIR, config.DATA_DIR, config.DB_PATH.parent):
        d.mkdir(parents=True, exist_ok=True)


def get_simulated_cluster():
    global _cluster
    if _cluster is None:
        from novasurge.sim.cluster import SimulatedCluster
        _cluster = SimulatedCluster()
    return _cluster


def get_simulated_telemetry():
    global _telemetry
    if _telemetry is None:
        from novasurge.sim.telemetry import SimulatedTelemetry
        _telemetry = SimulatedTelemetry(get_simulated_cluster())
    return _telemetry


def reset() -> None:
    global _cluster, _telemetry
    _cluster = None
    _telemetry = None
    from novasurge.cluster import set_cluster
    from novasurge.telemetry import set_telemetry
    set_cluster(None)
    set_telemetry(None)


def ensure_models() -> None:
    from novasurge.ml.train import models_present, train
    if not models_present():
        end = time.time()
        train(start=end - 600, end=end, epochs=80, quiet=True)


def fast_options():
    from novasurge.healer import HealOptions
    from novasurge.orchestrator import CampaignOptions
    return CampaignOptions(
        steady_state_timeout_s=30, detect_timeout_s=20, teardown_settle_s=0.5,
        heal=HealOptions(verify_timeout_s=20, probe_successes=3, probe_interval_s=0.2,
                         recovery_timeout_s=40, remediation_timeout_s=20, poll_s=0.2),
    )


async def run_campaign(plan: list[dict], echo: bool = True, isolate: bool = True) -> dict:
    from novasurge.cluster import set_cluster
    from novasurge.ml.detector import Detector
    from novasurge.monitor import Monitor
    from novasurge.orchestrator import Campaign
    from novasurge.telemetry import set_telemetry

    if isolate:
        configure()
    reset()
    cluster, telemetry = get_simulated_cluster(), get_simulated_telemetry()
    set_cluster(cluster)
    set_telemetry(telemetry)
    ensure_models()
    monitor = Monitor(telemetry=telemetry, detector=Detector(), interval=1.0)
    await monitor.start()
    try:
        for _ in range(3):
            await monitor.next_tick(timeout=10)
        return await Campaign(monitor, cluster, plan=plan, options=fast_options(), mode="dry-run",
                              echo=echo).run()
    finally:
        await monitor.stop()
