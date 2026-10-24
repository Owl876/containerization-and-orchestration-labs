"""HTTP API and two competing workers; PostgreSQL is the single queue."""
import asyncio
from contextlib import asynccontextmanager
import logging
import os
import threading
import time

import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel, Field
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST

ROLE = os.getenv("ROLE", "api")
VERSION = os.getenv("APP_VERSION", "dev")
POLL = float(os.getenv("WORKER_POLL_SECONDS", "1"))
STOP = threading.Event()
LOG = logging.getLogger("uvicorn.error")
REQUESTS = Counter("shop_http_requests_total", "HTTP requests", ["component", "path", "status"])
LATENCY = Histogram("shop_http_request_duration_seconds", "HTTP latency", ["component", "path"])
PROCESSED = Counter("shop_orders_processed_total", "Orders committed by this worker")
PENDING = Gauge("shop_orders_pending", "Pending orders observed by a worker")
DB_ERRORS = Counter("shop_db_errors_total", "Database operation failures", ["component"])
LAST_POLL = Gauge("shop_worker_last_success_timestamp_seconds", "Last successful worker poll")
SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    item text NOT NULL,
    quantity integer NOT NULL CHECK (quantity > 0),
    status text NOT NULL DEFAULT 'pending',
    created_at timestamptz NOT NULL DEFAULT now(),
    processed_at timestamptz,
    processed_by text
);
"""


def connect():
    return psycopg.connect(host=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPORT", "5432"), dbname=os.getenv("PGDATABASE", "shop"),
        user=os.getenv("PGUSER", "shop"), password=os.getenv("PGPASSWORD", ""),
        connect_timeout=3, options="-c statement_timeout=5000", row_factory=dict_row)


def work():
    while not STOP.is_set():
        try:
            with connect() as conn:
                # Locks prevent two workers processing the same order. The update
                # and status change commit atomically; a crash rolls them back.
                rows = conn.execute("""
                    WITH batch AS (
                        SELECT id FROM orders WHERE status = 'pending'
                        ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 10
                    )
                    UPDATE orders SET status = 'processed', processed_at = now(),
                        processed_by = %s
                    FROM batch WHERE orders.id = batch.id RETURNING orders.id
                """, (os.getenv("HOSTNAME", "worker"),)).fetchall()
                pending = conn.execute("SELECT count(*) AS n FROM orders WHERE status = 'pending'").fetchone()["n"]
            PROCESSED.inc(len(rows))
            PENDING.set(pending)
            LAST_POLL.set(time.time())
            if rows:
                LOG.info("processed=%s worker=%s", len(rows), os.getenv("HOSTNAME"))
        except psycopg.Error as exc:
            DB_ERRORS.labels(ROLE).inc()
            LOG.warning("worker database unavailable: %s", type(exc).__name__)
        STOP.wait(POLL)


@asynccontextmanager
async def lifespan(app):
    # Serialize initial schema creation: concurrent CREATE TABLE IF NOT EXISTS
    # can still race on PostgreSQL system catalogs without an advisory lock.
    while True:
        try:
            with connect() as conn:
                conn.execute("SELECT pg_advisory_xact_lock(31003)")
                conn.execute(SCHEMA)
            break
        except psycopg.Error as exc:
            LOG.warning("waiting for postgres: %s", type(exc).__name__)
            await asyncio.sleep(2)
    thread = None
    if ROLE == "worker":
        thread = threading.Thread(target=work, daemon=True)
        thread.start()
    yield
    STOP.set()
    if thread:
        thread.join(timeout=10)


app = FastAPI(title=f"shop-{ROLE}", lifespan=lifespan)


@app.middleware("http")
async def metrics(request: Request, call_next):
    started = time.monotonic()
    response = await call_next(request)
    path = request.url.path if request.url.path in {"/health", "/orders", "/order"} else "other"
    if request.url.path != "/metrics":
        REQUESTS.labels(ROLE, path, str(response.status_code)).inc()
        LATENCY.labels(ROLE, path).observe(time.monotonic() - started)
    return response


@app.get("/health", response_class=PlainTextResponse)
def health():
    if os.getenv("HEALTH_FAIL", "false").lower() == "true":
        return PlainTextResponse("simulated unhealthy version", status_code=503)
    return "ok"


@app.get("/version")
def version():
    return {"version": VERSION, "role": ROLE, "pod": os.getenv("HOSTNAME", "local")}


class Order(BaseModel):
    item: str = Field(min_length=1, max_length=200)
    quantity: int = Field(default=1, ge=1, le=10000)


@app.post("/order", status_code=201)
def order(order: Order):
    if ROLE != "api":
        raise HTTPException(404)
    try:
        with connect() as conn:
            return conn.execute("INSERT INTO orders(item, quantity) VALUES (%s, %s) RETURNING *",
                                (order.item, order.quantity)).fetchone()
    except psycopg.Error:
        DB_ERRORS.labels(ROLE).inc()
        raise HTTPException(503, "database unavailable")


@app.get("/orders")
def orders():
    if ROLE != "api":
        raise HTTPException(404)
    try:
        with connect() as conn:
            return conn.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 100").fetchall()
    except psycopg.Error:
        DB_ERRORS.labels(ROLE).inc()
        raise HTTPException(503, "database unavailable")


@app.get("/metrics")
def prometheus_metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
