"""
product-service — product catalogue with Redis cache-aside and stock reservation.

Endpoints
  GET  /products                      list catalogue
  GET  /products/{id}                 read product (Redis cache-aside, 60s TTL)
  POST /products                      create product
  POST /products/{id}/reserve         atomically decrement stock (409 if insufficient)
  POST /products/{id}/release         compensating stock increment
  GET  /health  /ready  /metrics
"""

from __future__ import annotations

import json
import logging
import os
import threading
from contextlib import asynccontextmanager

import redis
from fastapi import Depends, FastAPI, HTTPException
from prometheus_client import Counter
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Column, Float, Integer, String, select, text, update
from sqlalchemy.orm import Session

from pycommon.db import Base, create_schema, make_engine, ping, session_factory
from pycommon.observability import REGISTRY, get_logger, instrument, log, wait_for

SERVICE = "product-service"
logger = get_logger(SERVICE)

engine = make_engine("productsdb")
SessionLocal = session_factory(engine)

cache = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis-service"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    decode_responses=True,
    socket_connect_timeout=1,
    socket_timeout=1,
)
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "60"))
REPLENISH_INTERVAL_SECONDS = float(os.getenv("REPLENISH_INTERVAL_SECONDS", "15"))
REPLENISH_THRESHOLD = int(os.getenv("REPLENISH_THRESHOLD", "100"))

CACHE_LOOKUPS = Counter(
    "cache_lookups_total", "Product cache lookups", ["result"], registry=REGISTRY,
)


# ── Model ────────────────────────────────────────────────────────────────────
class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    price = Column(Float, nullable=False)
    stock = Column(Integer, nullable=False, default=0)
    restock_level = Column(Integer, nullable=False, default=0)
    category = Column(String(100), nullable=False)


class ProductIn(BaseModel):
    name: str
    price: float = Field(gt=0)
    stock: int = Field(ge=0)
    category: str


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    price: float
    stock: int
    category: str


class StockChange(BaseModel):
    quantity: int = Field(gt=0, le=1000)


SEED = [
    ("Laptop Pro 15", 1299.99, 500, "Electronics"),
    ("Wireless Mouse", 29.99, 2000, "Electronics"),
    ("USB-C Hub", 49.99, 1500, "Electronics"),
    ("Mechanical Keyboard", 89.99, 1000, "Electronics"),
    ("4K Monitor", 399.99, 400, "Electronics"),
    ("Standing Desk", 499.99, 300, "Furniture"),
    ("Ergonomic Chair", 349.99, 250, "Furniture"),
    ("Desk Lamp", 39.99, 1200, "Furniture"),
    ("Notebook Set", 14.99, 3000, "Stationery"),
    ("Ballpoint Pens 10pk", 7.99, 5000, "Stationery"),
    ("Sticky Notes", 5.99, 4000, "Stationery"),
    ("Whiteboard", 79.99, 600, "Office"),
    ("Dry Erase Markers", 9.99, 2500, "Office"),
    ("File Organizer", 24.99, 800, "Office"),
    ("Webcam HD", 69.99, 900, "Electronics"),
    ("Headphones Pro", 149.99, 700, "Electronics"),
    ("Microphone USB", 99.99, 550, "Electronics"),
    ("Phone Stand", 19.99, 1800, "Accessories"),
    ("Cable Management Kit", 15.99, 2000, "Accessories"),
    ("Laptop Sleeve", 34.99, 1100, "Accessories"),
]


def _seed(conn) -> None:
    """Runs inside create_schema's locked transaction, so it can never double-seed."""
    with Session(bind=conn) as db:
        if db.scalar(select(Product.id).limit(1)) is not None:
            return
        for name, price, stock, category in SEED:
            db.add(Product(name=name, price=price, stock=stock, restock_level=stock, category=category))
        db.flush()
        log(logger, logging.INFO, "catalogue seeded", products=len(SEED))


def _replenisher(stop: threading.Event) -> None:
    """Supplier replenishment: top products back up to their restock level."""
    while not stop.wait(REPLENISH_INTERVAL_SECONDS):
        try:
            with SessionLocal() as db:
                result = db.execute(
                    update(Product)
                    .where(Product.stock < REPLENISH_THRESHOLD)
                    .values(stock=Product.restock_level)
                    .returning(Product.id)
                )
                ids = [row[0] for row in result]
                db.commit()
            for pid in ids:
                _invalidate(pid)
            if ids:
                log(logger, logging.INFO, "stock replenished", product_ids=ids)
        except Exception as exc:  # noqa: BLE001 - keep the background job alive
            log(logger, logging.WARNING, "replenishment failed", error=str(exc))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    wait_for(lambda: ping(engine), "postgres", logger)
    create_schema(engine, seed=_seed)
    stop = threading.Event()
    threading.Thread(target=_replenisher, args=(stop,), daemon=True).start()
    log(logger, logging.INFO, "service started")
    yield
    stop.set()


app = FastAPI(title=SERVICE, lifespan=lifespan)
instrument(app, logger)


def get_db():
    with SessionLocal() as db:
        yield db


def _cache_key(product_id: int) -> str:
    return f"products:{product_id}"


def _invalidate(product_id: int) -> None:
    try:
        cache.delete(_cache_key(product_id))
    except redis.RedisError as exc:
        log(logger, logging.WARNING, "cache invalidation failed", product_id=product_id, error=str(exc))


# ── Probes ───────────────────────────────────────────────────────────────────
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


# ── API ──────────────────────────────────────────────────────────────────────
@app.get("/products", response_model=list[ProductOut])
def list_products(db: Session = Depends(get_db)):
    return db.scalars(select(Product).order_by(Product.id)).all()


@app.get("/products/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    key = _cache_key(product_id)
    try:
        cached = cache.get(key)
        if cached:
            CACHE_LOOKUPS.labels("hit").inc()
            return json.loads(cached)
        CACHE_LOOKUPS.labels("miss").inc()
    except redis.RedisError as exc:
        CACHE_LOOKUPS.labels("error").inc()
        log(logger, logging.WARNING, "cache read failed", error=str(exc))

    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="product not found")
    data = ProductOut.model_validate(product).model_dump()
    try:
        cache.setex(key, CACHE_TTL_SECONDS, json.dumps(data))
    except redis.RedisError as exc:
        log(logger, logging.WARNING, "cache write failed", error=str(exc))
    return data


@app.post("/products", response_model=ProductOut, status_code=201)
def create_product(payload: ProductIn, db: Session = Depends(get_db)):
    product = Product(**payload.model_dump(), restock_level=payload.stock)
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@app.post("/products/{product_id}/reserve", response_model=ProductOut)
def reserve_stock(product_id: int, change: StockChange, db: Session = Depends(get_db)):
    # Single conditional UPDATE: concurrent reservations can never oversell.
    row = db.execute(
        update(Product)
        .where(Product.id == product_id, Product.stock >= change.quantity)
        .values(stock=Product.stock - change.quantity)
        .returning(Product)
    ).scalar_one_or_none()
    if row is None:
        db.rollback()
        exists = db.get(Product, product_id) is not None
        raise HTTPException(status_code=409 if exists else 404,
                            detail="insufficient stock" if exists else "product not found")
    db.commit()
    _invalidate(product_id)
    return row


@app.post("/products/{product_id}/release", response_model=ProductOut)
def release_stock(product_id: int, change: StockChange, db: Session = Depends(get_db)):
    row = db.execute(
        update(Product)
        .where(Product.id == product_id)
        .values(stock=Product.stock + change.quantity)
        .returning(Product)
    ).scalar_one_or_none()
    if row is None:
        db.rollback()
        raise HTTPException(status_code=404, detail="product not found")
    db.commit()
    _invalidate(product_id)
    return row
