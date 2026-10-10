"""Detector + RCA against faults injected into the simulated cluster."""

import time

import pytest

from novasurge.chaos.injectors import REGISTRY
from novasurge.ml.detector import Detector
from novasurge.rca import analyze


def _ticks(detector, telemetry, n, sleep=0.0):
    det = None
    for _ in range(n):
        det = detector.step(telemetry.snapshot())
        if sleep:
            time.sleep(sleep)
    return det


def test_healthy_system_raises_no_anomaly(world):
    _, telemetry = world
    detector = Detector()
    det = _ticks(detector, telemetry, 15)
    assert det.anomalous == []
    assert det.primary is None


@pytest.mark.parametrize("injector, target, expected_type", [
    ("cpu_throttle", "payment-service", "cpu_throttle"),
    ("network_partition", "product-service", "network_partition"),
    ("replica_reduction", "order-service", "replica_exhaustion"),
    ("latency_injection", "order-service", "high_latency"),
])
def test_fault_is_detected_and_root_caused(world, injector, target, expected_type):
    cluster, telemetry = world
    detector = Detector()
    _ticks(detector, telemetry, 4)
    REGISTRY[injector].inject(cluster, target)
    det = None
    for _ in range(12):
        det = detector.step(telemetry.snapshot())
        if det.primary:
            break
        time.sleep(0.2)
    assert det.primary, f"{injector} on {target} was not detected"
    rca = analyze(det, cluster, telemetry)
    assert rca.origin == target
    assert rca.anomaly_type == expected_type
    assert rca.confidence >= 0.5


def test_pod_deletion_is_seen_even_if_kubernetes_heals_within_a_tick(world):
    cluster, telemetry = world
    detector = Detector()
    _ticks(detector, telemetry, 3)
    REGISTRY["pod_deletion"].inject(cluster, "order-service")
    det = detector.step(telemetry.snapshot())
    assert "order-service" in det.anomalous
    assert "replicas_lost" in det.services["order-service"].flags
    assert det.services["order-service"].anomaly_type == "pod_crash"


def test_scale_up_is_not_mistaken_for_lost_replicas(world):
    cluster, telemetry = world
    detector = Detector()
    _ticks(detector, telemetry, 3)
    cluster.patch_hpa("payment-service-hpa", {"spec": {"minReplicas": 3, "maxReplicas": 4}})
    det = _ticks(detector, telemetry, 2)
    assert "replicas_lost" not in det.services["payment-service"].flags
