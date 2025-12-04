import os
import httpx
from fastapi import FastAPI, Request

app = FastAPI()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

async def send_discord_notification(
    amount_sats: int,
    memo: str | None,
    note: str | None
):
    if not DISCORD_WEBHOOK_URL:
        print("DISCORD_WEBHOOK_URL not set")
        return

    # 메모/노트가 없을 경우 기본값
    memo_text = memo or "없음"
    note_text = note or "없음"

    embed = {
        "title": "⚡ 라이트닝 입금 감지",
        "description": f"**{amount_sats:,} sats** 가 BSL 라이트닝 주소로 입금되었습니다.",
        "color": 0xF7931A,
        "fields": [
            {
                "name": "메모 (invoice memo)",
                "value": memo_text,
                "inline": False
            },
            {
                "name": "송금시 입력한 note",
                "value": note_text,
                "inline": False
            },
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

    # 여기서 실제 필드명을 Blink payload에 맞게 바꿔야 함
    memo = tx.get("memo")          # 인보이스 메모
    note = tx.get("note")          # 송금시 note (예시)

    await send_discord_notification(amount_sats, memo, note)
    return {"ok": True}
