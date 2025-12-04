import os
import asyncio
import httpx
from fastapi import FastAPI, Request

app = FastAPI()

# ----------------------------
# 환경 변수
# ----------------------------
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
DISCORD_ROLE_ID = os.getenv("DISCORD_ROLE_ID")            # 멘션할 역할 ID
WATCH_ADDRESS = os.getenv("WATCH_ADDRESS")                # 감시할 온체인 주소 (예: bc1q8u9...)
MEMPOOL_API_BASE = os.getenv("MEMPOOL_API_BASE", "https://mempool.space")

# 온체인 감시용 상태 (가장 마지막으로 본 funded 합계)
last_funded_sum: int | None = None


# ----------------------------
# 디스코드 알림 공통 함수
# ----------------------------
async def send_discord_notification(amount_sats: int, payment_kind: str):
    """
    payment_kind: "라이트닝" / "온체인"
    """
    if not DISCORD_WEBHOOK_URL:
        print("DISCORD_WEBHOOK_URL not set")
        return

    # sat 값을 그대로 쓰고, 앞에 ₿ + 천단위 콤마
    # 예: 100 -> ₿100 / 10000 -> ₿10,000
    amount_str = f"₿{amount_sats:,}"

    # 역할 멘션 텍스트
    if DISCORD_ROLE_ID:
        mention_text = f"<@&{DISCORD_ROLE_ID}> {payment_kind} 입금이 감지되었습니다."
    else:
        mention_text = f"{payment_kind} 입금이 감지되었습니다."

    # 라이트닝 / 온체인 공통 임베드
    embed = {
        "title": f"⚡ {payment_kind} 입금 감지",
        "description": f"{amount_str} 가 {payment_kind} 주소로 입금되었습니다.",
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


# ----------------------------
# Blink 웹훅 (라이트닝 전용)
# ----------------------------
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

    await send_discord_notification(amount_sats, payment_kind="라이트닝")
    return {"ok": True}


# ----------------------------
# 온체인 주소 감시 루프
# ----------------------------
async def watch_onchain_address():
    """
    WATCH_ADDRESS 로 설정된 온체인 주소를 mempool.space API로 주기적으로 조회해서
    새로 유입된 금액이 있으면 그 차액만큼 디스코드에 온체인 입금 알림을 보낸다.
    """
    global last_funded_sum

    if not WATCH_ADDRESS:
        print("WATCH_ADDRESS not set. Onchain watcher disabled.")
        return

    url = f"{MEMPOOL_API_BASE}/api/address/{WATCH_ADDRESS}"
    print(f"[onchain-watcher] Watching address: {WATCH_ADDRESS}")
    print(f"[onchain-watcher] Using API: {url}")

    async with httpx.AsyncClient() as client:
        while True:
            try:
                resp = await client.get(url, timeout=10)
                resp.raise_for_status()
                data = resp.json()

                # chain_stats: 확정된(confirmed) 입출금
                chain_funded = data["chain_stats"]["funded_txo_sum"]
                # mempool_stats: 아직 블록에 안 실린(미확정) 입출금
                mempool_funded = data["mempool_stats"]["funded_txo_sum"]

                # confirmed + unconfirmed 을 모두 합쳐서 "총 유입" 기준으로 사용
                total_funded = chain_funded + mempool_funded

                if last_funded_sum is None:
                    # 처음 기동 시에는 기준값만 맞춰두고 알림 보내지 않음
                    last_funded_sum = total_funded
                    print(f"[onchain-watcher] initial funded sum = {total_funded}")
                elif total_funded > last_funded_sum:
                    # 새 입금 발생
                    diff = total_funded - last_funded_sum
                    last_funded_sum = total_funded
                    print(f"[onchain-watcher] New deposit detected: +{diff} sats")

                    # 온체인 입금 알림
                    await send_discord_notification(diff, payment_kind="온체인")

            except Exception as e:
                print("[onchain-watcher] Error:", repr(e))

            # 조회 주기 (초) - 너무 짧게 하면 API rate limit 걸릴 수 있음
            await asyncio.sleep(30)


# ----------------------------
# FastAPI 시작 시 온체인 감시 태스크 시작
# ----------------------------
@app.on_event("startup")
async def on_startup():
    # 백그라운드로 온체인 주소 감시 시작
    asyncio.create_task(watch_onchain_address())
