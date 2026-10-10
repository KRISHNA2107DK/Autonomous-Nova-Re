"""
Chaos injectors.

Contract (every module):
    NAME, DESCRIPTION, EXPECTED_SIGNATURE
    compatible(cluster, service) -> (bool, reason)
    inject(cluster, service) -> Injection
    still_active(cluster, injection) -> bool   is the fault still present?
    reverse(cluster, injection) -> dict        idempotent teardown

`reverse` is *teardown*, not healing: the orchestrator calls it only after the
round's recovery has been measured, to guarantee the next round starts from the
declared baseline even if a remediation only mitigated the fault.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


@dataclass
class Injection:
    injector: str
    service: str
    success: bool
    injected_at: str
    target: str | None = None
    details: dict = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Injection":
        return cls(**d)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


from novasurge.chaos.injectors import (  # noqa: E402  (registry after the shared types)
    cpu_throttle,
    latency_injection,
    network_partition,
    pod_deletion,
    replica_reduction,
)

REGISTRY = {
    mod.NAME: mod
    for mod in (pod_deletion, cpu_throttle, network_partition, latency_injection, replica_reduction)
}
