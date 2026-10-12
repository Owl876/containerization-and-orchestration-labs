import os

import httpx
from fastapi import FastAPI, Request

app = FastAPI(title="telegram-bridge")

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
STICKER_FILE_ID = os.environ["TELEGRAM_STICKER_FILE_ID"]
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
# ISP блокирует api.telegram.org напрямую; ходим через локальный SOCKS5 VPN-клиента
# на хосте (happ, 127.0.0.1:10808), прокинутый socat'ом на host.minikube.internal:18080
TELEGRAM_PROXY = os.getenv("TELEGRAM_PROXY_URL")


@app.get("/health")
async def health() -> dict:
    return {"ok": True}


@app.post("/webhook")
async def webhook(request: Request) -> dict:
    payload = await request.json()
    async with httpx.AsyncClient(timeout=10, proxy=TELEGRAM_PROXY) as client:
        for alert in payload.get("alerts", []):
            if alert.get("status") != "firing":
                continue
            summary = alert.get("annotations", {}).get("summary", "Панда истощена")
            await client.post(f"{API_URL}/sendSticker", json={"chat_id": CHAT_ID, "sticker": STICKER_FILE_ID})
            await client.post(f"{API_URL}/sendMessage", json={"chat_id": CHAT_ID, "text": summary})
    return {"ok": True}
