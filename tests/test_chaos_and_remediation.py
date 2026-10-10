"""Each injector really changes cluster state, and each playbook remediator really repairs it."""

import pytest

from novasurge.chaos.injectors import REGISTRY as INJECTORS
from novasurge.remediators import REGISTRY as REMEDIATORS, RemediationContext
from tests.conftest import run

CASES = [
    ("pod_deletion", "order-service", "hpa_scaleout"),
    ("cpu_throttle", "payment-service", "resource_restore"),
    ("network_partition", "product-service", "network_policy_rollback"),
    ("latency_injection", "order-service", "traffic_reroute"),
    ("replica_reduction", "payment-service", "hpa_scaleout"),
]


@pytest.mark.parametrize("injector, service, remediator", CASES)
def test_inject_then_remediate(world, injector, service, remediator):
    cluster, telemetry = world
    mod = INJECTORS[injector]
    ok, why = mod.compatible(cluster, service)
    assert ok, why
    inj = mod.inject(cluster, service)
    assert inj.success, inj.error
    if injector != "pod_deletion":       # pod deletion is healed by the ReplicaSet itself
        assert mod.still_active(cluster, inj)

    ctx = RemediationContext(cluster, telemetry, timeout_s=15, poll_s=0.1)
    result = run(REMEDIATORS[remediator](service, ctx))
    assert result.success, result.summary
    assert not mod.still_active(cluster, inj), f"{remediator} did not clear {injector}"
    assert telemetry.probe(service)["ok"]


def test_reverse_is_idempotent(world):
    cluster, _ = world
    mod = INJECTORS["network_partition"]
    inj = mod.inject(cluster, "payment-service")
    assert mod.reverse(cluster, inj)["deleted"] is True
    assert mod.reverse(cluster, inj)["deleted"] is False


def test_replica_reduction_refuses_single_replica_services(world):
    cluster, _ = world
    ok, why = INJECTORS["replica_reduction"].compatible(cluster, "notification-service")
    assert not ok and "minimum" in why


def test_quarantine_refuses_to_remove_the_only_serving_replica(world):
    cluster, telemetry = world
    cluster.patch_hpa("payment-service-hpa", {"spec": {"minReplicas": 1, "maxReplicas": 1}})
    ctx = RemediationContext(cluster, telemetry, timeout_s=5, poll_s=0.1)
    import time
    deadline = time.time() + 5
    while len([p for p in cluster.list_pods("payment-service") if not p.deleting]) > 1 and time.time() < deadline:
        time.sleep(0.1)
    result = run(REMEDIATORS["traffic_reroute"]("payment-service", ctx))
    assert not result.success and "refused" in result.summary
