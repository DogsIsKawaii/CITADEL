import os
import httpx
from fastapi import FastAPI, Request

app = FastAPI()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
DISCORD_ROLE_ID = os.getenv("DISCORD_ROLE_ID")  # 멘션할 역할 ID (문자열로 사용)

async def send_discord_notification(amount_sats: int):
    if not DISCORD_WEBHOOK_URL:
        print("DISCORD_WEBHOOK_URL not set")
        return

    # sat 값을 그대로 쓰고, 앞에 ₿ 붙이고 천 단위 콤마만 추가
    amount_str = f"₿{amount_sats:,}"

    # 역할 멘션 텍스트 (위에 나오는 일반 텍스트)
    # 예: @라이트닝알림 역할에게만 알림
    if DISCORD_ROLE_ID:
        # 역할 멘션 문법: <@&ROLE_ID>
        mention_text = f"<@&{DISCORD_ROLE_ID}> 라이트닝 입금이 감지되었습니다."
    else:
        mention_text = "라이트닝 입금이 감지되었습니다."

    embed = {
        "title": "⚡ 라이트닝 입금 감지",
        "description": f"{amount_str} 가 BSL 라이트닝 주소로 입금되었습니다.",
        "color": 0xF7931A,
        # 기존처럼 fields 없음
    }

    payload = {
        # 이 content가 디스코드 메시지의 맨 위 텍스트가 됨 (역할 멘션 포함)
        "content": mention_text,
        "embeds": [embed],
        # allowed_mentions로 멘션 가능한 대상을 제한 (원하는 경우)
        "allowed_mentions": {
            "roles": [DISCORD_ROLE_ID] if DISCORD_ROLE_ID else []
        },
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

    raw_amount = tx.get("settlementAmount", 0)
    try:
        amount_sats = int(raw_amount)
    except (TypeError, ValueError):
        amount_sats = 0

    await send_discord_notification(amount_sats)
    return {"ok": True}
