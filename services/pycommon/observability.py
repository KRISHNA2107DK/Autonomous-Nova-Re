"""
Shared observability helpers for the ShopFusion Python services.

Every service exposes the same metric names so AutoHeal can query them
uniformly (the `service` label is attached by Prometheus from the pod's
`app` label, so it is not set here):

    http_requests_total{method, route, status_code}
    http_request_duration_seconds{method, route}          (histogram)
    http_requests_in_flight                                (gauge)
    http_client_requests_total{target, status_code}       (outbound calls)
    http_client_request_duration_seconds{target}          (histogram)

`route` is the matched route *template* (e.g. /products/{product_id}),
never the raw path, so label cardinality stays bounded.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone

from fastapi import FastAPI, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.routing import Match

LATENCY_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

REGISTRY = CollectorRegistry()

HTTP_REQUESTS = Counter(
    "http_requests_total", "HTTP requests handled",
    ["method", "route", "status_code"], registry=REGISTRY,
)
HTTP_DURATION = Histogram(
    "http_request_duration_seconds", "HTTP request latency",
    ["method", "route"], buckets=LATENCY_BUCKETS, registry=REGISTRY,
)
HTTP_IN_FLIGHT = Gauge(
    "http_requests_in_flight", "HTTP requests currently being served",
    registry=REGISTRY,
)
CLIENT_REQUESTS = Counter(
    "http_client_requests_total", "Outbound HTTP calls to other services",
    ["target", "status_code"], registry=REGISTRY,
)
CLIENT_DURATION = Histogram(
    "http_client_request_duration_seconds", "Outbound HTTP call latency",
    ["target"], buckets=LATENCY_BUCKETS, registry=REGISTRY,
)

# Probe/metrics endpoints are excluded from the RED metrics so health
# checks and scrapes do not dilute request-rate and latency signals.
_UNINSTRUMENTED = {"/health", "/ready", "/metrics"}


# ── Logging ──────────────────────────────────────────────────────────────────
class _JsonFormatter(logging.Formatter):
    def __init__(self, service: str):
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "service": self.service,
            "level": record.levelname,
            "message": record.getMessage(),
        }
        entry.update(getattr(record, "fields", {}))
        return json.dumps(entry, default=str)


def get_logger(service: str) -> logging.Logger:
    logger = logging.getLogger(service)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(_JsonFormatter(service))
        logger.addHandler(handler)
        logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))
        logger.propagate = False
    return logger


def log(logger: logging.Logger, level: int, message: str, **fields) -> None:
    logger.log(level, message, extra={"fields": fields})


# ── HTTP instrumentation ─────────────────────────────────────────────────────
def _route_template(app: FastAPI, request: Request) -> str:
    for route in app.router.routes:
        match, _ = route.matches(request.scope)
        if match == Match.FULL:
            return getattr(route, "path", request.url.path)
    return "unmatched"


def instrument(app: FastAPI, logger: logging.Logger) -> None:
    """Attach RED-metrics middleware and the /metrics endpoint."""

    @app.middleware("http")
    async def _metrics_middleware(request: Request, call_next):
        path = request.url.path
        if path in _UNINSTRUMENTED:
            return await call_next(request)

        route = _route_template(app, request)
        HTTP_IN_FLIGHT.inc()
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            elapsed = time.perf_counter() - start
            HTTP_IN_FLIGHT.dec()
            HTTP_REQUESTS.labels(request.method, route, str(status)).inc()
            HTTP_DURATION.labels(request.method, route).observe(elapsed)
            if status >= 500:
                log(logger, logging.ERROR, "request failed", method=request.method,
                    path=path, status_code=status, duration_ms=round(elapsed * 1000, 1))
            elif status >= 400:
                log(logger, logging.WARNING, "request rejected", method=request.method,
                    path=path, status_code=status, duration_ms=round(elapsed * 1000, 1))

    @app.get("/metrics", include_in_schema=False)
    def _metrics() -> Response:
        return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)


def record_client_call(target: str, status_code: int | str, seconds: float) -> None:
    CLIENT_REQUESTS.labels(target, str(status_code)).inc()
    CLIENT_DURATION.labels(target).observe(seconds)


# ── Startup helpers ──────────────────────────────────────────────────────────
def wait_for(check, what: str, logger: logging.Logger, timeout: float = 90.0) -> None:
    """Retry `check()` until it stops raising, so pods tolerate dependency start order."""
    deadline = time.monotonic() + timeout
    attempt = 0
    while True:
        attempt += 1
        try:
            check()
            log(logger, logging.INFO, f"{what} reachable", attempts=attempt)
            return
        except Exception as exc:  # noqa: BLE001 - any failure means "not ready yet"
            if time.monotonic() >= deadline:
                raise RuntimeError(f"{what} not reachable after {timeout:.0f}s: {exc}") from exc
            log(logger, logging.WARNING, f"waiting for {what}", attempt=attempt, error=str(exc))
            time.sleep(2)
