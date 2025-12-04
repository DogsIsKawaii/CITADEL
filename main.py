import os
import httpx
from fastapi import FastAPI, Request

app = FastAPI()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

async def send_discord_notification(amount_sats: int):
    if not DISCORD_WEBHOOK_URL:
        print("DISCORD_WEBHOOK_URL not set")
        return

    # sat 값을 그대로 쓰고, 앞에 ₿ 붙이고 천 단위 콤마만 추가
    # 예: 100 -> ₿100 / 10000 -> ₿10,000
    amount_str = f"₿{amount_sats:,}"

    embed = {
        "title": "⚡ 라이트닝 입금 감지",
        "description": f"{amount_str} 가 BSL 라이트닝 주소로 입금되었습니다.",
        "color": 0xF7931A,
        # fields 제거 (메모/노트 안 보여줌)
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

    # settlementAmount 가 문자열일 수도 있어서 안전하게 변환
    raw_amount = tx.get("settlementAmount", 0)
    try:
        amount_sats = int(raw_amount)
    except (TypeError, ValueError):
        amount_sats = 0

    await send_discord_notification(amount_sats)
    return {"ok": True}
