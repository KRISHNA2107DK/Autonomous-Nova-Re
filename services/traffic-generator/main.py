"""
traffic-generator — steady, realistic shopper traffic through the real user path
(nginx -> api-gateway -> services), running inside the cluster.

Request mix (per request):
    40%  GET  /products/{id}
    10%  GET  /products
    25%  POST /orders
    15%  GET  /orders/{id}       (ids harvested from successful orders)
    10%  GET  /payments/{id}

It doubles as the *user-facing SLI probe*: every outcome is exported on :9100
    loadgen_requests_total{endpoint, outcome}     outcome = ok | client_error |
                                                  server_error | timeout | connection_error
    loadgen_request_duration_seconds{endpoint}
AutoHeal's SLA tracker uses these to measure what users actually experienced
during each chaos round.

Configuration (env): TARGET_URL, RPS, MAX_CONCURRENCY, REQUEST_TIMEOUT_SECONDS
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import signal
import time
from collections import Counter as TallyCounter
from collections import deque
from datetime import datetime, timezone

import httpx
from prometheus_client import Counter, Gauge, Histogram, start_http_server

TARGET_URL = os.getenv("TARGET_URL", "http://nginx-gateway.shopfusion.svc.cluster.local")
RPS = float(os.getenv("RPS", "20"))
MAX_CONCURRENCY = int(os.getenv("MAX_CONCURRENCY", "100"))
TIMEOUT = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "8"))
METRICS_PORT = int(os.getenv("METRICS_PORT", "9100"))

REQUESTS = Counter("loadgen_requests_total", "Synthetic user requests", ["endpoint", "outcome"])
LATENCY = Histogram(
    "loadgen_request_duration_seconds", "Synthetic user request latency", ["endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
IN_FLIGHT = Gauge("loadgen_in_flight", "Synthetic requests in flight")
DROPPED = Counter("loadgen_dropped_total", "Requests skipped because the concurrency cap was reached")
TARGET_RPS = Gauge("loadgen_target_rps", "Configured request rate")

order_ids: deque[int] = deque(maxlen=500)
payment_ids: deque[int] = deque(maxlen=500)
window: TallyCounter = TallyCounter()


def log(message: str, **fields) -> None:
    print(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                      "service": "traffic-generator", "level": "INFO", "message": message, **fields}),
          flush=True)


def pick_request() -> tuple[str, str, str, dict]:
    roll = random.random()
    if roll < 0.40:
        return "GET /products/{id}", "GET", f"/products/{random.randint(1, 20)}", {}
    if roll < 0.50:
        return "GET /products", "GET", "/products", {}
    if roll < 0.75:
        body = {"user_id": f"user-{random.randint(1, 500)}", "product_id": random.randint(1, 20),
                "quantity": random.randint(1, 3)}
        return "POST /orders", "POST", "/orders", {"json": body}
    if roll < 0.90:
        oid = random.choice(order_ids) if order_ids else random.randint(1, 50)
        return "GET /orders/{id}", "GET", f"/orders/{oid}", {}
    pid = random.choice(payment_ids) if payment_ids else random.randint(1, 50)
    return "GET /payments/{id}", "GET", f"/payments/{pid}", {}


def classify(status: int) -> str:
    if status < 400:
        return "ok"
    # 404 on reads of ids we never created and 409 (out of stock) are
    # legitimate business answers, not failures of the system.
    if status < 500:
        return "client_error"
    return "server_error"


async def one_request(client: httpx.AsyncClient, sem: asyncio.Semaphore) -> None:
    endpoint, method, path, kwargs = pick_request()
    start = time.perf_counter()
    IN_FLIGHT.inc()
    try:
        resp = await client.request(method, path, **kwargs)
        outcome = classify(resp.status_code)
        if endpoint == "POST /orders" and resp.status_code == 201:
            try:
                body = resp.json()
                order_ids.append(int(body["id"]))
                if body.get("payment_id"):
                    payment_ids.append(int(body["payment_id"]))
            except (ValueError, KeyError, TypeError):
                pass
    except httpx.TimeoutException:
        outcome = "timeout"
    except httpx.HTTPError:
        outcome = "connection_error"
    finally:
        IN_FLIGHT.dec()
        sem.release()
    elapsed = time.perf_counter() - start
    REQUESTS.labels(endpoint, outcome).inc()
    LATENCY.labels(endpoint).observe(elapsed)
    window[outcome] += 1


async def reporter() -> None:
    while True:
        await asyncio.sleep(10)
        total = sum(window.values())
        failed = window["server_error"] + window["timeout"] + window["connection_error"]
        log("traffic stats", rps=round(total / 10, 1), requests=total,
            failure_ratio=round(failed / total, 4) if total else 0.0, outcomes=dict(window))
        window.clear()


async def main() -> None:
    start_http_server(METRICS_PORT)
    TARGET_RPS.set(RPS)
    log("traffic generator starting", target=TARGET_URL, rps=RPS, max_concurrency=MAX_CONCURRENCY)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    sem = asyncio.Semaphore(MAX_CONCURRENCY)
    limits = httpx.Limits(max_connections=MAX_CONCURRENCY, max_keepalive_connections=50)
    async with httpx.AsyncClient(base_url=TARGET_URL, timeout=TIMEOUT, limits=limits) as client:
        asyncio.create_task(reporter())
        interval = 1.0 / RPS
        next_at = time.perf_counter()
        tasks: set[asyncio.Task] = set()
        while not stop.is_set():
            # Open-loop arrivals: schedule on a fixed clock so a slow backend
            # does not silently reduce offered load (no coordinated omission).
            next_at += interval
            if sem.locked():
                DROPPED.inc()
            else:
                await sem.acquire()
                task = asyncio.create_task(one_request(client, sem))
                tasks.add(task)
                task.add_done_callback(tasks.discard)
            delay = next_at - time.perf_counter()
            if delay > 0:
                try:
                    await asyncio.wait_for(stop.wait(), timeout=delay)
                except asyncio.TimeoutError:
                    pass
            elif delay < -1.0:
                next_at = time.perf_counter()  # fell far behind; resynchronise
        log("traffic generator stopping")


if __name__ == "__main__":
    asyncio.run(main())
