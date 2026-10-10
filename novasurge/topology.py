"""
ShopFusion topology — the single source of truth used by RCA, blast-radius
preflight, target selection, the decision engine and the dashboard graph.

Edges reflect what the code actually does:
  * api-gateway proxies /products /orders /payments /notifications
  * order-service calls product-service (read + reserve/release) and payment-service
  * order- and payment-service publish events consumed by notification-service
"""

from __future__ import annotations

from collections import deque

SERVICES: list[str] = [
    "api-gateway",
    "product-service",
    "order-service",
    "payment-service",
    "notification-service",
]

# Synchronous request/response calls: caller -> callees
SYNC_CALLS: dict[str, list[str]] = {
    "api-gateway": ["product-service", "order-service", "payment-service", "notification-service"],
    "order-service": ["product-service", "payment-service"],
    "product-service": [],
    "payment-service": [],
    "notification-service": [],
}

# Asynchronous (pub/sub) flows: publisher -> consumers. Failures here do not
# propagate back to the publisher's callers.
ASYNC_FLOWS: dict[str, list[str]] = {
    "order-service": ["notification-service"],
    "payment-service": ["notification-service"],
}

DATASTORES: dict[str, list[str]] = {
    "product-service": ["postgres", "redis"],
    "order-service": ["postgres", "redis"],
    "payment-service": ["postgres", "redis"],
    "notification-service": ["redis"],
    "api-gateway": [],
}

# Revenue / user-impact weight used for prioritisation (10 = most critical).
BUSINESS_IMPACT: dict[str, int] = {
    "payment-service": 10,
    "api-gateway": 9,
    "order-service": 8,
    "product-service": 6,
    "notification-service": 2,
}

# Share of user requests that touch each service, derived from the
# traffic generator mix (40% product reads, 10% catalogue, 25% orders
# [which also hit product + payment], 15% order reads, 10% payment reads).
USER_TRAFFIC_SHARE: dict[str, float] = {
    "api-gateway": 1.00,
    "product-service": 0.75,
    "order-service": 0.40,
    "payment-service": 0.35,
    "notification-service": 0.0,   # async only; users never wait on it
}

# Container port per service (also the Prometheus scrape port).
PORTS: dict[str, int] = {
    "api-gateway": 3000,
    "product-service": 8001,
    "order-service": 8002,
    "payment-service": 8003,
    "notification-service": 3001,
}


def callers_of(service: str) -> list[str]:
    """Services that synchronously call `service` (they suffer when it fails)."""
    return [caller for caller, callees in SYNC_CALLS.items() if service in callees]


def callees_of(service: str) -> list[str]:
    return list(SYNC_CALLS.get(service, []))


def upstream_closure(service: str) -> list[str]:
    """Every service whose requests can be degraded by a failure of `service`."""
    seen: set[str] = set()
    queue = deque(callers_of(service))
    while queue:
        svc = queue.popleft()
        if svc in seen:
            continue
        seen.add(svc)
        queue.extend(callers_of(svc))
    return sorted(seen, key=SERVICES.index)


def downstream_closure(service: str) -> list[str]:
    """Every service `service` depends on, directly or transitively."""
    seen: set[str] = set()
    queue = deque(callees_of(service))
    while queue:
        svc = queue.popleft()
        if svc in seen:
            continue
        seen.add(svc)
        queue.extend(callees_of(svc))
    return sorted(seen, key=SERVICES.index)


def call_path(target: str, entry: str = "api-gateway") -> list[str]:
    """Shortest synchronous call path from the entry point to `target`."""
    if target == entry:
        return [entry]
    queue: deque[list[str]] = deque([[entry]])
    seen = {entry}
    while queue:
        path = queue.popleft()
        for nxt in SYNC_CALLS.get(path[-1], []):
            if nxt == target:
                return path + [nxt]
            if nxt not in seen:
                seen.add(nxt)
                queue.append(path + [nxt])
    return [target]


def edges() -> list[dict]:
    out = [{"source": s, "target": t, "kind": "sync"} for s, ts in SYNC_CALLS.items() for t in ts]
    out += [{"source": s, "target": t, "kind": "async"} for s, ts in ASYNC_FLOWS.items() for t in ts]
    return out
