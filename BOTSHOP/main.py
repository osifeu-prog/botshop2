import os, logging, re
from datetime import datetime
from typing import Optional, Any, Dict, List
from dataclasses import dataclass

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from http import HTTPStatus

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# ---------- Logging ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("botshop2")

# ---------- Config ----------
@dataclass
class BotConfig:
    BOT_TOKEN: str
    WEBHOOK_URL: str
    WEBHOOK_SECRET: Optional[str] = None
    ADMIN_DASH_TOKEN: Optional[str] = None
    SITE_URL: str = "https://slh-nft.com/"
    GROUP_STATIC_INVITE: str = ""
    SLH_NIS: int = 39

def load_config() -> BotConfig:
    b = os.getenv("BOT_TOKEN")
    w = os.getenv("WEBHOOK_URL")
    if not b: raise RuntimeError("BOT_TOKEN missing")
    if not w: raise RuntimeError("WEBHOOK_URL missing")
    return BotConfig(
        BOT_TOKEN=b,
        WEBHOOK_URL=w,
        WEBHOOK_SECRET=os.getenv("WEBHOOK_SECRET") or None,
        ADMIN_DASH_TOKEN=os.getenv("ADMIN_DASH_TOKEN") or None,
        SITE_URL=os.getenv("SITE_URL","https://slh-nft.com/").strip().rstrip("/"),
        GROUP_STATIC_INVITE=os.getenv("GROUP_STATIC_INVITE","").strip(),
        SLH_NIS=int(os.getenv("SLH_NIS","39"))
    )
config = load_config()

# ---------- Rate limiter ----------
limiter = Limiter(key_func=get_remote_address)
security = HTTPBearer()

# ---------- Telegram App ----------
ptb_app: Application = (
    Application.builder()
    .updater(None)    # webhook only
    .token(config.BOT_TOKEN)
    .build()
)

# ---------- Simple in-memory state ----------
class State:
    views = 0
    downloads = 0
state = State()

# ---------- UI ----------
def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 הצטרפות לקהילת העסקים (39 )", callback_data="join")],
        [InlineKeyboardButton("🔗 שתף את שער הקהילה", callback_data="share")],
        [InlineKeyboardButton("ℹ מה אני מקבל?", callback_data="info")],
        [InlineKeyboardButton("🆘 תמיכה", callback_data="support")],
    ])

def payment_methods() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏦 העברה בנקאית", callback_data="pay_bank")],
        [InlineKeyboardButton("📲 ביט / פייבוקס / PayPal", callback_data="pay_paybox")],
        [InlineKeyboardButton("💎 טלגרם (TON)", callback_data="pay_ton")],
        [InlineKeyboardButton("⬅ חזרה", callback_data="back_main")],
    ])

def payment_links() -> InlineKeyboardMarkup:
    def env(name, default=""): return os.getenv(name, default)
    buttons = [
        [InlineKeyboardButton("📲 תשלום בפייבוקס", url=env("PAYBOX_URL","https://links.payboxapp.com/1SNfaJ6XcYb"))],
        [InlineKeyboardButton("📲 תשלום בביט", url=env("BIT_URL","https://www.bitpay.co.il/app/share-info?i=190693822888_19l4oyvE"))],
        [InlineKeyboardButton("💳 תשלום ב-PayPal", url=env("PAYPAL_URL","https://paypal.me/osifdu"))],
        [InlineKeyboardButton("⬅ חזרה", callback_data="back_main")],
    ]
    return InlineKeyboardMarkup(buttons)

# ---------- Messages ----------
def start_text() -> str:
    return (
        "ברוך הבא לשער הכניסה לקהילת העסקים שלנו 🌐\n\n"
        "כאן מצטרפים למערכת של עסקים, שותפים וקהל יוצר ערך סביב:\n"
        "• שיווק רשתי חכם\n"
        "• נכסים דיגיטליים (NFT, טוקני SLH)\n"
        "• מתנות ופרסים על פעילות ושיתופים\n\n"
        f"אתר: {config.SITE_URL}\n"
        "לינק הזמנה (אם הוגדר): /invite\n\n"
        f"דמי הצטרפות חדפעמיים: *{config.SLH_NIS} *.\n\n"
        "כדי להתחיל  בחר אפשרות:"
    )

def info_text() -> str:
    return (
        "ℹ *מה מקבלים בקהילה?*\n\n"
        "🚀 גישה לקבוצת עסקים סגורה עם רעיונות ושיתופי פעולה\n"
        "📚 הדרכות על מכירות אונליין ונכסים דיגיטליים\n"
        "🎁 מתנות דיגיטליות, NFT והטבות בקהילה\n"
        "💎 חלוקת טוקני SLH על פעילות והפניות\n\n"
        f"דמי הצטרפות: *{config.SLH_NIS} *.\nבחר אמצעי תשלום:"
    )

# ---------- Bot Handlers ----------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m = update.effective_message
    state.views += 1
    await m.reply_text(start_text(), parse_mode="Markdown", reply_markup=main_menu())

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m = update.effective_message
    await m.reply_text("/start  התחלה מחדש\n/invite  קישור הזמנה (אם הוגדר)\n/site  כתובת אתר")

async def cmd_site(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(f"אתר: {config.SITE_URL}")

async def cmd_invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = config.GROUP_STATIC_INVITE
    if link:
        await update.effective_message.reply_text(f"קישור הצטרפות לקהילה:\n{link}")
    else:
        await update.effective_message.reply_text("קישור ההזמנה לא הוגדר (GROUP_STATIC_INVITE ריק).")

async def cbq_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data or ""
    if data == "join":
        await q.edit_message_text(
            "🔑 הצטרפות לקהילה  בחר אמצעי תשלום ואז שלח צילום של אישור התשלום:",
            reply_markup=payment_methods()
        )
    elif data == "info":
        await q.edit_message_text(info_text(), parse_mode="Markdown", reply_markup=payment_methods())
    elif data == "share":
        await q.message.reply_text(f"שתף את הדף: {config.SITE_URL}")
    elif data == "support":
        await q.message.reply_text("תמיכה: פנה למנהל/קבוצה")
    elif data == "back_main":
        await q.edit_message_text(start_text(), parse_mode="Markdown", reply_markup=main_menu())
    elif data.startswith("pay_"):
        await q.edit_message_text(
            "לאחר ביצוע התשלום:\n1) שלח כאן צילום מסך של האישור\n2) תקבל אישור ידני והזמנה",
            reply_markup=payment_links()
        )

async def photo_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # כאן אפשר להרחיב ל-DB וכו; לעת עתה הודעת תודה בסיסית
    await update.effective_message.reply_text("תודה! האישור התקבל ונשלח לבדיקה ✅")

# רישום
ptb_app.add_handler(CommandHandler("start", cmd_start))
ptb_app.add_handler(CommandHandler("help",  cmd_help))
ptb_app.add_handler(CommandHandler("site",  cmd_site))
ptb_app.add_handler(CommandHandler("invite",cmd_invite))
ptb_app.add_handler(CallbackQueryHandler(cbq_handler))
ptb_app.add_handler(MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE, photo_payment))

# ---------- FastAPI ----------
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

VERSION_TAG = os.getenv("VERSION_TAG") or os.getenv("RAILWAY_GIT_COMMIT_SHA") or "local"

@app.get("/health")
def health():
    return {"status":"ok","service":"botshop2","ts":datetime.utcnow().isoformat()}

@app.get("/meta")
def meta():
    return {"version":VERSION_TAG,"site_url":config.SITE_URL,"has_invite":bool(config.GROUP_STATIC_INVITE)}

@app.get("/config")
def cfg():
    return {"slh_nis":config.SLH_NIS}

@app.get("/admin/stats")
def admin_stats(credentials: HTTPAuthorizationCredentials = Depends(security), token: str = ""):
    provided = credentials.credentials if credentials else token
    if not config.ADMIN_DASH_TOKEN or provided != config.ADMIN_DASH_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {"ok":True,"views":state.views,"downloads":state.downloads,"ts":datetime.utcnow().isoformat()}

@app.post("/webhook")
@limiter.limit("60/minute")
async def webhook(request: Request):
    # הגנה אופציונלית עם WEBHOOK_SECRET
    if config.WEBHOOK_SECRET:
        given = request.headers.get("X-Telegram-Bot-Api-Secret-Token") or ""
        if given != config.WEBHOOK_SECRET:
            return JSONResponse(status_code=HTTPStatus.UNAUTHORIZED, content={"detail":"Bad secret"})
    data = await request.json()
    update = Update.de_json(data, ptb_app.bot)
    await ptb_app.process_update(update)
    return JSONResponse({"ok":True})
