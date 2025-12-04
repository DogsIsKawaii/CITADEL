import os
import httpx
from fastapi import FastAPI, Request

app = FastAPI()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
DISCORD_ROLE_ID = os.getenv("DISCORD_ROLE_ID")              # 멘션할 역할
TARGET_ONCHAIN_ADDRESS = os.getenv("TARGET_ONCHAIN_ADDRESS") # 모니터링할 온체인 주소 (예: bc1q....)


async def send_discord_notification(amount_sats: int, payment_kind: str):
    """
    payment_kind: "라이트닝" 또는 "온체인"
    """
    if not DISCORD_WEBHOOK_URL:
        print("DISCORD_WEBHOOK_URL not set")
        return

    # sat 값에 ₿ + 천단위 콤마
    amount_str = f"₿{amount_sats:,}"

    # 역할 멘션 텍스트
    if DISCORD_ROLE_ID:
        mention_text = f"<@&{DISCORD_ROLE_ID}> {payment_kind} 입금이 감지되었습니다."
    else:
        mention_text = f"{payment_kind} 입금이 감지되었습니다."

    embed = {
        "title": f"⚡ {payment_kind} 입금 감지",
        "description": f"{amount_str} 가 BSL {payment_kind} 주소로 입금되었습니다.",
        "color": 0xF7931A,
    }

    payload = {
        "content": mention_text,
        "embeds": [embed],
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

    event_type = data.get("eventType")
    if event_type not in ("receive.lightning", "receive.onchain"):
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

    # --- 온체인 전용 필터링: 특정 주소만 알림 ---
    if event_type == "receive.onchain":
        initiation = tx.get("initiationVia") or {}
        # ⚠️ 실제 필드명은 웹훅 로그에서 확인 필요
        onchain_address = initiation.get("address")

        # 환경변수에 주소가 설정돼 있고, 이 주소가 아니면 무시
        if TARGET_ONCHAIN_ADDRESS and onchain_address != TARGET_ONCHAIN_ADDRESS:
            print("Ignored onchain tx to other address:", onchain_address)
            return {"ok": True, "ignored": True}

        await send_discord_notification(amount_sats, payment_kind="온체인")
        return {"ok": True}

    # 라이트닝인 경우
    if event_type == "receive.lightning":
        await send_discord_notification(amount_sats, payment_kind="라이트닝")
        return {"ok": True}
