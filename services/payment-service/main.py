"""
payment-service — simulated card processor.

POST /payments      authorise a charge (processor latency 40-160ms, ~3% declines)
GET  /payments/{id} read a payment
Publishes every outcome on the Redis `payment-events` channel.
"""

from __future__ import annotations

import json
import logging
import os
import random
import time
from contextlib import asynccontextmanager
from datetime import datetime

import redis
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Column, DateTime, Float, Integer, String, func, text
from sqlalchemy.orm import Session

from pycommon.db import Base, create_schema, make_engine, ping, session_factory
from pycommon.observability import get_logger, instrument, log, wait_for

SERVICE = "payment-service"
logger = get_logger(SERVICE)

engine = make_engine("paymentsdb")
SessionLocal = session_factory(engine)

events = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis-service"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    socket_connect_timeout=1,
    socket_timeout=1,
)

DECLINE_RATE = float(os.getenv("PAYMENT_DECLINE_RATE", "0.03"))
PROCESSOR_LATENCY_MS = (40, 160)


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, nullable=False, index=True)
    amount = Column(Float, nullable=False)
    status = Column(String(32), nullable=False, default="processing")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PaymentIn(BaseModel):
    order_id: int = Field(gt=0)
    amount: float = Field(gt=0)


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    amount: float
    status: str
    created_at: datetime | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    wait_for(lambda: ping(engine), "postgres", logger)
    create_schema(engine)
    log(logger, logging.INFO, "service started")
    yield


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


@app.post("/payments", response_model=PaymentOut, status_code=201)
def create_payment(payload: PaymentIn, db: Session = Depends(get_db)):
    payment = Payment(order_id=payload.order_id, amount=payload.amount, status="processing")
    db.add(payment)
    db.commit()

    # Sync endpoint -> runs in FastAPI's worker threadpool, so sleeping here
    # models processor latency without blocking the event loop.
    time.sleep(random.uniform(*PROCESSOR_LATENCY_MS) / 1000.0)
    payment.status = "failed" if random.random() < DECLINE_RATE else "success"
    db.commit()
    db.refresh(payment)

    try:
        events.publish("payment-events", json.dumps(
            {"payment_id": payment.id, "order_id": payment.order_id, "status": payment.status}))
    except redis.RedisError as exc:
        log(logger, logging.WARNING, "payment event publish failed", error=str(exc))
    return payment


@app.get("/payments/{payment_id}", response_model=PaymentOut)
def get_payment(payment_id: int, db: Session = Depends(get_db)):
    payment = db.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="payment not found")
    return payment
