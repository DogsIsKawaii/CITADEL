import os
import httpx
from fastapi import FastAPI, Request

app = FastAPI()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

async def send_discord_notification(amount_sats: int, memo: str | None):
    if not DISCORD_WEBHOOK_URL:
        print("DISCORD_WEBHOOK_URL not set")
        return

    embed = {
        "title": "⚡ 라이트닝 입금 감지",
        "description": f"**{amount_sats:,} sats** 가 라이트닝 주소로 입금되었습니다.",
        "color": 0xF7931A,
        "fields": [
            {
                "name": "메모",
                "value": memo or "없음",
                "inline": False
            }
        ]
    }

    payload = {
        "embeds": [embed]
    }

    async with httpx.AsyncClient() as client:
        await client.post(DISCORD_WEBHOOK_URL, json=payload)


@app.post("/blink/webhook")
async def blink_webhook(request: Request):
    data = await request.json()
    print("Blink webhook data:", data)

    if data.get("eventType") != "receive.lightning":
        return {"ok": True, "ignored": True}

    tx = data.get("transaction") or {}
    if tx.get("status") != "success":
        return {"ok": True, "ignored": True}

    if tx.get("settlementCurrency") != "BTC":
        return {"ok": True, "ignored": True}

    amount_sats = int(tx.get("settlementAmount", 0))
    memo = tx.get("memo")

    await send_discord_notification(amount_sats, memo)
    return {"ok": True}
