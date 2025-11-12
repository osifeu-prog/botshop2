import os
import json
import hmac
import hashlib
import logging
from typing import Any, Dict

from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
import uvicorn

# ========= Logging =========
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("botshop2")

# ========= Config =========
BOT_TOKEN       = os.getenv("BOT_TOKEN", "").strip()
WEBHOOK_SECRET  = os.getenv("WEBHOOK_SECRET", "").strip()
SITE_URL        = (os.getenv("SITE_URL") or "https://slh-nft.com/").strip().rstrip("/")
GROUP_INVITE    = (os.getenv("GROUP_STATIC_INVITE") or "").strip()
PRICE_NIS       = int(os.getenv("SLH_NIS", "39"))
VERSION_TAG     = os.getenv("VERSION_TAG") or os.getenv("RAILWAY_GIT_COMMIT_SHA") or "local"

# ========= App =========
app = FastAPI(title="BOTSHOP2", version=VERSION_TAG)

@app.get("/health")
def health() -> Dict[str, Any]:
    return {"status": "ok", "service": "botshop2", "version": VERSION_TAG}

@app.get("/meta")
def meta() -> Dict[str, Any]:
    return {
        "site_url": SITE_URL,
        "has_invite": bool(GROUP_INVITE),
        "price_nis": PRICE_NIS,
        "webhook_secret_configured": bool(WEBHOOK_SECRET),
        "bot_token_configured": bool(BOT_TOKEN),
        "version": VERSION_TAG,
    }

# ========= Telegram webhook =========
# דרישת אבטחה: Telegram שולח כותרת X-Telegram-Bot-Api-Secret-Token כשמגדירים secret_token ב-setWebhook.
# נאמת אותה כדי שלא נקבל קריאות זדוניות.
async def _require_secret(x_secret: str):
    if not WEBHOOK_SECRET:
        # אם לא הוגדר סוד  לא נכפה (לצורך בדיקות); בפרודקשן מומלץ חובה.
        return
    if x_secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Bad secret")

@app.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(default=None)
):
    await _require_secret(x_telegram_bot_api_secret_token)

    if not BOT_TOKEN:
        raise HTTPException(status_code=500, detail="BOT_TOKEN not configured")

    try:
        data = await request.json()
    except Exception:
        # טלגרם יכול לשלוח gzip; FastAPI פותח אוטומטית. אם נכשל, ננסה גוף טקסטואלי
        body = await request.body()
        try:
            data = json.loads(body.decode("utf-8"))
        except Exception as e:
            logger.exception("Invalid webhook payload")
            raise HTTPException(status_code=400, detail="Invalid payload") from e

    # לוג עדין
    msg = data.get("message") or data.get("edited_message") or data.get("callback_query") or {}
    chat_id = None
    text    = None

    if "message" in data and data["message"].get("chat"):
        chat_id = data["message"]["chat"].get("id")
        text = data["message"].get("text")

    # לוגיקת MVP:
    # - /start -> הודעת הסבר + כפתורים?
    # - /invite -> הצגת קישור לקבוצה אם קיים
    # - /site -> הצגת אתר
    # כאן נשיב באקנולדג' בלבד (200 OK) כדי שטלגרם לא ישנה מצב.
    # שליחת הודעות חזרה תתבצע בקריאת httpx ל- sendMessage (לא חובה בשלב זה).
    try:
        if text == "/start":
            logger.info(f"/start from chat_id={chat_id}")
        elif text == "/invite":
            logger.info(f"/invite from chat_id={chat_id}")
        elif text == "/site":
            logger.info(f"/site from chat_id={chat_id}")
        else:
            if text:
                logger.debug(f"msg '{text}' from chat_id={chat_id}")
    except Exception:
        logger.exception("handle webhook")

    return JSONResponse({"ok": True})

# ========= Runner =========
if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)