import asyncio
import os
import random

import asyncpg
from fastapi import FastAPI, Response
from opentelemetry import trace
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from logging_conf import configure_logging
from telemetry import setup_tracing

SERVICE_NAME = "worker"
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://shop:shop@shop-postgresql:5432/shop")
POLL_INTERVAL_SECONDS = float(os.getenv("POLL_INTERVAL_SECONDS", "1"))
CONCURRENCY = int(os.getenv("WORKER_CONCURRENCY", "16"))

CLAIM_NEXT_ORDER = """
UPDATE orders
SET status = 'processing', updated_at = now()
WHERE id = (
    SELECT id FROM orders WHERE status = 'new'
    ORDER BY created_at
    LIMIT 1
    FOR UPDATE SKIP LOCKED
)
RETURNING id, item, quantity
"""

setup_tracing(SERVICE_NAME)
log = configure_logging()
tracer = trace.get_tracer(__name__)

app = FastAPI(title=SERVICE_NAME)

db_pool: asyncpg.Pool | None = None
_poll_tasks: list[asyncio.Task] = []

ORDERS_PROCESSED_TOTAL = Counter("shop_orders_processed_total", "Заказы, обработанные воркером-кладовщицей")
ORDER_PROCESSING_DURATION = Histogram(
    "shop_order_processing_duration_seconds", "Сколько панда-кладовщица собирала заказ"
)


async def fulfill_order(order_id: int) -> None:
    pack_time = random.uniform(0.5, 2.5)
    with tracer.start_as_current_span("pack-order"):
        await asyncio.sleep(pack_time)
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE orders SET status = 'fulfilled', updated_at = now() WHERE id = $1", order_id)
    ORDER_PROCESSING_DURATION.observe(pack_time)
    ORDERS_PROCESSED_TOTAL.inc()
    log.info("order fulfilled", extra={"order_id": order_id, "pack_seconds": round(pack_time, 2)})


async def poll_loop() -> None:
    while True:
        try:
            async with db_pool.acquire() as conn:
                async with conn.transaction():
                    order = await conn.fetchrow(CLAIM_NEXT_ORDER)
            if order is not None:
                await fulfill_order(order["id"])
                continue
        except Exception:
            log.exception("poll loop failed")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


@app.on_event("startup")
async def startup() -> None:
    global db_pool, _poll_tasks
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=CONCURRENCY)
    _poll_tasks = [asyncio.create_task(poll_loop()) for _ in range(CONCURRENCY)]


@app.on_event("shutdown")
async def shutdown() -> None:
    for task in _poll_tasks:
        task.cancel()
    if db_pool is not None:
        await db_pool.close()


@app.get("/health")
async def health() -> Response:
    return Response(content="ok", media_type="text/plain")


@app.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
