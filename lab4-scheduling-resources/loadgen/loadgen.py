import asyncio
import os
import random
import time

import httpx

URL = os.getenv("TARGET_URL", "http://shop-api.default.svc.cluster.local:8000/orders")
WAVES = os.getenv("WAVES", "5:60,20:120,50:120,10:60,0:60")
CYCLES = int(os.getenv("CYCLES", "10"))
CATALOG = ["bamboo-snack-pack", "panda-sticker-sheet", "plush-panda", "kuberpandas-mug"]


def parse_waves(spec: str) -> list[tuple[int, int]]:
    return [(int(rps), int(sec)) for rps, sec in (part.split(":") for part in spec.split(","))]


async def one_order(client: httpx.AsyncClient) -> tuple[int, float]:
    body = {"item": random.choice(CATALOG), "quantity": random.randint(1, 3)}
    start = time.perf_counter()
    try:
        resp = await client.post(URL, json=body)
        return resp.status_code, time.perf_counter() - start
    except httpx.HTTPError:
        return 0, time.perf_counter() - start


def percentile(sorted_values: list[float], q: float) -> float:
    return sorted_values[min(len(sorted_values) - 1, int(len(sorted_values) * q))]


async def run_wave(client: httpx.AsyncClient, rps: int, seconds: int) -> tuple[int, int, float, float]:
    if rps == 0:
        await asyncio.sleep(seconds)
        return 0, 0, 0.0, 0.0

    tasks = []
    interval = 1 / rps
    end = time.monotonic() + seconds
    next_shot = time.monotonic()
    while time.monotonic() < end:
        tasks.append(asyncio.create_task(one_order(client)))
        next_shot += interval
        await asyncio.sleep(max(0.0, next_shot - time.monotonic()))

    results = await asyncio.gather(*tasks)
    ok = sum(1 for status, _ in results if status == 200)
    latencies = sorted(lat for _, lat in results)
    return ok, len(results) - ok, percentile(latencies, 0.5), percentile(latencies, 0.95)


async def main() -> None:
    waves = parse_waves(WAVES)
    # без keep-alive каждый запрос открывает новое соединение, и kube-proxy
    # раскидывает их по всем репликам api, а не липнет к одной
    limits = httpx.Limits(max_connections=300, max_keepalive_connections=0)
    async with httpx.AsyncClient(timeout=10, limits=limits) as client:
        for cycle in range(1, CYCLES + 1):
            for rps, seconds in waves:
                ok, failed, p50, p95 = await run_wave(client, rps, seconds)
                print(
                    f"cycle={cycle}/{CYCLES} rps={rps} sec={seconds} "
                    f"ok={ok} failed={failed} p50={p50 * 1000:.0f}ms p95={p95 * 1000:.0f}ms",
                    flush=True,
                )
    print("loadgen finished", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
