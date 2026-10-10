"""
order-service — order placement saga across product-service and payment-service.

POST /orders
  1. read product (price)                       product-service
  2. reserve stock (atomic)                     product-service
  3. persist order (pending)                    postgres
  4. charge payment                             payment-service
  5. confirm, or release stock on decline       product-service (compensation)
  6. publish order event                        redis pub/sub -> notification-service

Dependency failures surface as 503 (after compensation); business outcomes
(unknown product, out of stock, card declined) are 4xx / normal responses.
"""

from __future__ import annotations

import json
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime

import httpx
import redis
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Column, DateTime, Float, Integer, String, func, text
from sqlalchemy.orm import Session

from pycommon.db import Base, create_schema, make_engine, ping, session_factory
from pycommon.observability import get_logger, instrument, log, record_client_call, wait_for

SERVICE = "order-service"
logger = get_logger(SERVICE)

engine = make_engine("ordersdb")
SessionLocal = session_factory(engine)

PRODUCT_URL = os.getenv("PRODUCT_SERVICE_URL", "http://product-service:8001")
PAYMENT_URL = os.getenv("PAYMENT_SERVICE_URL", "http://payment-service:8003")

events = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis-service"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    socket_connect_timeout=1,
    socket_timeout=1,
)

# One pooled client per process; tight timeouts so a partitioned or slow
# dependency fails fast instead of piling up worker threads.
http = httpx.Client(
    timeout=httpx.Timeout(connect=1.0, read=4.0, write=2.0, pool=2.0),
    limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
)


class DependencyError(Exception):
    def __init__(self, target: str, detail: str):
        super().__init__(f"{target}: {detail}")
        self.target = target
        self.detail = detail


def call(target: str, method: str, url: str, **kwargs) -> httpx.Response:
    """Outbound call with client-side RED metrics; raises DependencyError on transport/5xx."""
    start = time.perf_counter()
    try:
        resp = http.request(method, url, **kwargs)
    except httpx.HTTPError as exc:
        record_client_call(target, "transport_error", time.perf_counter() - start)
        raise DependencyError(target, f"{type(exc).__name__}: {exc}") from exc
    record_client_call(target, resp.status_code, time.perf_counter() - start)
    if resp.status_code >= 500:
        raise DependencyError(target, f"HTTP {resp.status_code}")
    return resp


# ── Model ────────────────────────────────────────────────────────────────────
class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(100), nullable=False)
    product_id = Column(Integer, nullable=False)
    quantity = Column(Integer, nullable=False)
    amount = Column(Float, nullable=False, default=0.0)
    status = Column(String(32), nullable=False, default="pending")
    payment_id = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class OrderIn(BaseModel):
    user_id: str = Field(min_length=1, max_length=100)
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=100)


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: str
    product_id: int
    quantity: int
    amount: float
    status: str
    payment_id: int | None = None
    created_at: datetime | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    wait_for(lambda: ping(engine), "postgres", logger)
    create_schema(engine)
    log(logger, logging.INFO, "service started")
    yield
    http.close()


app = FastAPI(title=SERVICE, lifespan=lifespan)
instrument(app, logger)


def get_db():
    with SessionLocal() as db:
        yield db


@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE}


@app.get("/ready")
def ready():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"database unavailable: {exc}") from exc
    return {"status": "ready", "service": SERVICE}


def _release(product_id: int, quantity: int) -> None:
    try:
        call("product-service", "POST", f"{PRODUCT_URL}/products/{product_id}/release",
             json={"quantity": quantity})
    except DependencyError as exc:
        # Stock leak is bounded: product-service replenishes periodically.
        log(logger, logging.ERROR, "stock release failed", product_id=product_id, error=str(exc))


def _publish(order: Order) -> None:
    event = {"order_id": order.id, "user_id": order.user_id, "status": order.status,
             "amount": order.amount}
    try:
        events.publish("order-events", json.dumps(event))
    except redis.RedisError as exc:
        log(logger, logging.WARNING, "order event publish failed", error=str(exc))


@app.post("/orders", response_model=OrderOut, status_code=201)
def create_order(payload: OrderIn, db: Session = Depends(get_db)):
    reserved = False
    try:
        product_resp = call("product-service", "GET", f"{PRODUCT_URL}/products/{payload.product_id}")
        if product_resp.status_code == 404:
            raise HTTPException(status_code=404, detail="product not found")
        price = float(product_resp.json()["price"])

        reserve_resp = call("product-service", "POST",
                            f"{PRODUCT_URL}/products/{payload.product_id}/reserve",
                            json={"quantity": payload.quantity})
        if reserve_resp.status_code == 409:
            raise HTTPException(status_code=409, detail="insufficient stock")
        if reserve_resp.status_code >= 400:
            raise HTTPException(status_code=reserve_resp.status_code, detail=reserve_resp.text)
        reserved = True

        order = Order(user_id=payload.user_id, product_id=payload.product_id,
                      quantity=payload.quantity, amount=round(price * payload.quantity, 2),
                      status="pending")
        db.add(order)
        db.commit()
        db.refresh(order)

        pay_resp = call("payment-service", "POST", f"{PAYMENT_URL}/payments",
                        json={"order_id": order.id, "amount": order.amount})
        if pay_resp.status_code >= 400:
            raise DependencyError("payment-service", f"HTTP {pay_resp.status_code}")
        payment = pay_resp.json()
        order.payment_id = payment["id"]
        if payment["status"] == "success":
            order.status = "confirmed"
        else:
            order.status = "payment_declined"
            _release(payload.product_id, payload.quantity)
        reserved = False
        db.commit()
        db.refresh(order)
    except DependencyError as exc:
        db.rollback()
        if reserved:
            _release(payload.product_id, payload.quantity)
        log(logger, logging.ERROR, "dependency failure", target=exc.target, detail=exc.detail)
        raise HTTPException(status_code=503, detail=f"dependency unavailable: {exc.target}") from exc

    _publish(order)
    return order


@app.get("/orders/{order_id}", response_model=OrderOut)
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="order not found")
    return order
