import numpy as np

from novasurge import topology
from novasurge.ml.features import Normalizer, harmful_z
from novasurge.telemetry import FEATURES


def test_dependency_closures_follow_real_call_graph():
    assert set(topology.callers_of("product-service")) == {"api-gateway", "order-service"}
    assert topology.upstream_closure("payment-service") == ["api-gateway", "order-service"]
    assert topology.downstream_closure("api-gateway") == [
        "product-service", "order-service", "payment-service", "notification-service"]
    assert topology.call_path("payment-service") == ["api-gateway", "payment-service"]
    assert topology.upstream_closure("api-gateway") == []


def test_every_service_has_impact_port_and_traffic_share():
    for svc in topology.SERVICES:
        assert svc in topology.BUSINESS_IMPACT
        assert svc in topology.PORTS
        assert svc in topology.USER_TRAFFIC_SHARE


def _rows(n=100, **overrides):
    rng = np.random.default_rng(0)
    rows = []
    for _ in range(n):
        row = {"request_rate": 20 + rng.normal(0, 0.5), "error_rate": 0.0, "p99_latency_ms": 240 + rng.normal(0, 3),
               "inflight": 1.0, "cpu_cores": 0.02, "cpu_throttle_ratio": 0.0, "memory_mb": 80.0,
               "caller_error_rate": 0.0, "caller_p99_ms": 241.0}
        row.update(overrides)
        rows.append(row)
    return rows


def test_normalizer_is_per_service_and_respects_floors():
    norm = Normalizer.fit({svc: _rows() for svc in topology.SERVICES})
    st = norm.stats["payment-service"]
    # constant error_rate baseline -> the absolute floor, never a zero scale
    assert st["error_rate"].scale == 0.02
    assert st["p99_latency_ms"].scale >= 15.0
    z, missing = norm.transform("payment-service", {**_rows(1)[0], "error_rate": 0.10, "p99_latency_ms": None})
    assert z[FEATURES.index("error_rate")] == np.float32(5.0)
    assert z[FEATURES.index("p99_latency_ms")] == 0.0 and "p99_latency_ms" in missing


def test_harmful_direction():
    z = np.zeros(len(FEATURES), dtype=np.float32)
    z[FEATURES.index("request_rate")] = -6       # traffic drop is harmful
    z[FEATURES.index("p99_latency_ms")] = -6     # getting faster is not
    hz = harmful_z(z)
    assert hz[FEATURES.index("request_rate")] == 6
    assert hz[FEATURES.index("p99_latency_ms")] == -6
