import asyncio
import os
import random
import time
from collections import Counter as TallyCounter

import asyncpg
import httpx
from fastapi import FastAPI, Query, Request, Response
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.trace import Status, StatusCode
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from pydantic import BaseModel, Field

from logging_conf import configure_logging
from panda_state import PandaState
from telemetry import setup_tracing

SERVICE_NAME = "api"
PORT = os.getenv("PORT", "8000")
SELF_URL = os.getenv("SELF_URL", f"http://127.0.0.1:{PORT}")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://shop:shop@shop-postgresql:5432/shop")

CATALOG = ["bamboo-snack-pack", "panda-sticker-sheet", "plush-panda", "kuberpandas-mug"]

CREATE_ORDERS_TABLE = """
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    item TEXT NOT NULL,
    quantity INT NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'new',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""

CREATE_STATUS_INDEX = "CREATE INDEX IF NOT EXISTS orders_status_created_idx ON orders (status, created_at)"

setup_tracing(SERVICE_NAME)
log = configure_logging()
tracer = trace.get_tracer(__name__)
panda = PandaState()

app = FastAPI(title=SERVICE_NAME)
HTTPXClientInstrumentor().instrument()

db_pool: asyncpg.Pool | None = None

REQUESTS_TOTAL = Counter("http_requests_total", "Total HTTP requests", ["method", "path", "status"])
ERRORS_TOTAL = Counter("http_errors_total", "Total HTTP 5xx responses", ["method", "path"])
REQUEST_DURATION = Histogram("http_request_duration_seconds", "Request duration in seconds", ["method", "path"])
PANDA_ENERGY = Gauge("panda_energy_level", "Текущий запас энергии панды (0-100)")
PANDA_NAPS_TOTAL = Counter("panda_naps_total", "Сколько раз панда вздремнула через /slow")
ORDERS_CREATED_TOTAL = Counter("shop_orders_created_total", "Заказы, оформленные через /orders")


class OrderRequest(BaseModel):
    item: str | None = Field(default=None, description="Что заказываем из лавки панд")
    quantity: int = Field(default=1, ge=1, le=20)


@app.middleware("http")
async def red_metrics(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start
    path = request.url.path

    REQUEST_DURATION.labels(request.method, path).observe(duration)
    REQUESTS_TOTAL.labels(request.method, path, response.status_code).inc()
    if response.status_code >= 500:
        ERRORS_TOTAL.labels(request.method, path).inc()

    log.info(
        "request completed",
        extra={
            "http_method": request.method,
            "http_path": path,
            "http_status": response.status_code,
            "duration_ms": round(duration * 1000, 2),
        },
    )
    return response


FastAPIInstrumentor.instrument_app(app)


@app.on_event("startup")
async def startup() -> None:
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    async with db_pool.acquire() as conn:
        await conn.execute(CREATE_ORDERS_TABLE)
        await conn.execute(CREATE_STATUS_INDEX)


@app.on_event("shutdown")
async def shutdown() -> None:
    if db_pool is not None:
        await db_pool.close()


@app.get("/health")
async def health() -> Response:
    return Response(content="ok", media_type="text/plain")


@app.get("/fail")
async def fail() -> Response:
    span = trace.get_current_span()
    span.set_status(Status(StatusCode.ERROR, "панда уронила бамбук"))
    span.record_exception(RuntimeError("panda dropped the bamboo"))
    log.error("simulated failure", extra={"endpoint": "/fail"})
    return Response(content="simulated failure", status_code=500)


@app.get("/slow")
async def slow() -> dict:
    delay = random.uniform(1, 3)
    with tracer.start_as_current_span("nap-time"):
        await asyncio.sleep(delay)
    energy = await panda.spend(delay * 10)
    PANDA_ENERGY.set(energy)
    PANDA_NAPS_TOTAL.inc()
    return {"slept_seconds": round(delay, 2), "panda_energy_level": round(energy, 1)}


@app.get("/load")
async def load(
    n: int = Query(50, ge=1, le=500, description="Сколько запросов сделать"),
    concurrency: int = Query(20, ge=1, le=100, description="Максимум одновременных запросов"),
    target: str = Query("/health", description="Какой путь дёргать"),
) -> dict:
    semaphore = asyncio.Semaphore(concurrency)

    async def one(client: httpx.AsyncClient) -> int:
        async with semaphore:
            resp = await client.get(f"{SELF_URL}{target}")
            return resp.status_code

    async with httpx.AsyncClient(timeout=10) as client:
        statuses = await asyncio.gather(*(one(client) for _ in range(n)))

    energy = await panda.spend(n * 0.05)
    PANDA_ENERGY.set(energy)
    log.info("load generated", extra={"requests": n, "target": target})
    return {"requests": n, "target": target, "statuses": dict(TallyCounter(statuses))}


@app.post("/orders")
async def create_order(order: OrderRequest) -> dict:
    item = order.item or random.choice(CATALOG)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO orders (item, quantity) VALUES ($1, $2) RETURNING id, status, created_at",
            item,
            order.quantity,
        )
    ORDERS_CREATED_TOTAL.inc()
    log.info("order created", extra={"order_id": row["id"], "item": item, "quantity": order.quantity})
    return {"id": row["id"], "item": item, "quantity": order.quantity, "status": row["status"]}


@app.get("/orders/{order_id}")
async def get_order(order_id: int) -> Response:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, item, quantity, status, created_at, updated_at FROM orders WHERE id = $1",
            order_id,
        )
    if row is None:
        return Response(content="order not found", status_code=404)
    return {
        "id": row["id"],
        "item": row["item"],
        "quantity": row["quantity"],
        "status": row["status"],
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }


@app.get("/metrics")
async def metrics() -> Response:
    PANDA_ENERGY.set(await panda.current())
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
