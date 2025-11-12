from __future__ import annotations
import os, asyncio, logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# optional DB
try:
    import psycopg2, psycopg2.extras
except Exception:
    psycopg2 = None

logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO"))
logger = logging.getLogger("botshop")

# === ENV ===
BOT_TOKEN          = (os.getenv("BOT_TOKEN") or "").strip()
WEBHOOK_URL        = (os.getenv("WEBHOOK_URL") or "").strip()  # https://<railway>.up.railway.app/webhook
WEBHOOK_SECRET     = (os.getenv("WEBHOOK_SECRET") or "").strip()
ADMIN_DASH_TOKEN   = (os.getenv("ADMIN_DASH_TOKEN") or "").strip()
SITE_URL           = (os.getenv("SITE_URL") or "https://slh-nft.com/").strip().rstrip("/")
GROUP_STATIC_INVITE= (os.getenv("GROUP_STATIC_INVITE") or "").strip()
SLH_NIS            = int(os.getenv("SLH_NIS","39"))
DATABASE_URL       = (os.getenv("DATABASE_URL") or "").strip()
VERSION_TAG        = os.getenv("VERSION_TAG") or os.getenv("RAILWAY_GIT_COMMIT_SHA") or "local"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is required")

app: FastAPI = FastAPI(title="botshop-clean")
tg_app: Application = Application.builder().token(BOT_TOKEN).build()

# in-memory fallback
MEM_PAYMENTS: List[Dict[str,Any]] = []
_MEM_COUNTER = 0

def _get_conn():
    if not DATABASE_URL or not psycopg2:
        return None
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.DictCursor)

def db_init_schema():
    conn = _get_conn()
    if not conn:
        logger.info("DB not configured; using in-memory.")
        return
    try:
        with conn, conn.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS payments(
              id SERIAL PRIMARY KEY,
              user_id BIGINT NOT NULL,
              username TEXT,
              pay_method TEXT,
              status TEXT NOT NULL DEFAULT 'pending',
              reason TEXT,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_pay_user   ON payments(user_id);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_pay_status ON payments(status);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_pay_time   ON payments(created_at);")
        logger.info("DB schema ensured.")
    finally:
        conn.close()

async def db_log_payment(user_id:int, username:Optional[str], method:str):
    conn = _get_conn()
    if not conn:
        global _MEM_COUNTER
        _MEM_COUNTER += 1
        MEM_PAYMENTS.append(dict(
            id=_MEM_COUNTER, user_id=user_id, username=username, method=method,
            status="pending", reason=None, created_at=datetime.utcnow().isoformat()))
        return
    try:
        with conn, conn.cursor() as cur:
            cur.execute("""
            INSERT INTO payments(user_id, username, pay_method, status, created_at)
            VALUES (%s,%s,%s,'pending', NOW());
            """, (user_id, username, method))
    finally:
        conn.close()

async def db_update_last_status(user_id:int, status:str, reason:Optional[str]):
    conn = _get_conn()
    if not conn:
        for p in reversed(MEM_PAYMENTS):
            if p["user_id"] == user_id:
                p["status"] = status
                p["reason"] = reason
                return True
        return False
    try:
        with conn, conn.cursor() as cur:
            cur.execute("""
            UPDATE payments
               SET status=%s, reason=%s
             WHERE id = (
               SELECT id FROM payments WHERE user_id=%s ORDER BY created_at DESC LIMIT 1
             );
            """, (status, reason, user_id))
            return cur.rowcount > 0
    finally:
        conn.close()

def db_get_stats()->Dict[str,int]:
    conn = _get_conn()
    if not conn:
        return {
            "pending":  sum(1 for p in MEM_PAYMENTS if p["status"]=="pending"),
            "approved": sum(1 for p in MEM_PAYMENTS if p["status"]=="approved"),
            "rejected": sum(1 for p in MEM_PAYMENTS if p["status"]=="rejected"),
            "total":    len(MEM_PAYMENTS),
        }
    try:
        with conn, conn.cursor() as cur:
            cur.execute("""
            SELECT
              COUNT(*) FILTER (WHERE status='pending')  AS pending,
              COUNT(*) FILTER (WHERE status='approved') AS approved,
              COUNT(*) FILTER (WHERE status='rejected') AS rejected,
              COUNT(*) AS total
            FROM payments;
            """)
            row = cur.fetchone()
            return dict(row) if row else {"pending":0,"approved":0,"rejected":0,"total":0}
    finally:
        conn.close()

def is_admin_request(req: Request)->bool:
    if not ADMIN_DASH_TOKEN:
        return False
    auth = req.headers.get("Authorization") or ""
    if auth.startswith("Bearer "):
        if auth.replace("Bearer ","").strip() == ADMIN_DASH_TOKEN:
            return True
    token = req.query_params.get("token")
    return bool(token and token == ADMIN_DASH_TOKEN)

def main_menu()->InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f" הצטרפות לקהילת העסקים ({SLH_NIS})", callback_data="join")],
        [InlineKeyboardButton(" הזן/עדכן חשבון בנק", callback_data="update_bank")],
        [InlineKeyboardButton(" AI אסיסטנט", callback_data="ai_helper")],
        [InlineKeyboardButton("ℹ מה אני מקבל?", callback_data="info")],
        [InlineKeyboardButton(" שתף את שער הקהילה", callback_data="share")],
        [InlineKeyboardButton(" תמיכה", callback_data="support")],
    ])

def start_message()->str:
    return "\n".join([
        "🌐 שער הכניסה לקהילת העסקים",
        f"מחיר הצטרפות: {SLH_NIS} שח",
        "",
        "בחר את אמצעי התשלום:",
        "• העברה בנקאית",
        "• ביט / פייבוקס / PayPal",
        "• טלגרם (TON)",
        "",
        "לאחר ביצוע התשלום:",
        "1) שלח כאן צילום/מסמך של אישור התשלום.",
        "2) נבדק ידנית.",
        "3) לאחר אישור נשלח קישור לקהילה.",
        "",
        f"אתר: {SITE_URL}",
        "קישור הזמנה (אם הוגדר): /invite",
    ])

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(start_message(), reply_markup=main_menu())

async def cmd_site(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(f"אתר: {SITE_URL}")

async def cmd_invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if GROUP_STATIC_INVITE:
        await update.effective_message.reply_text(f"קישור הצטרפות לקהילה:\n{GROUP_STATIC_INVITE}")
    else:
        await update.effective_message.reply_text("קישור ההזמנה לא הוגדר. הגדר GROUP_STATIC_INVITE ב-Railway.")

async def on_payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    username = f"@{user.username}" if user and user.username else None
    method = "image" if (update.message and update.message.photo) else ("document" if (update.message and update.message.document) else "unknown")
    try:
        await db_log_payment(user.id, username, method)
        await update.effective_message.reply_text("תודה! האישור התקבל ונשלח לבדיקה ✅\nלאחר אישור ידני תקבל קישור לקהילה.")
    except Exception:
        logger.exception("log_payment failed")
        await update.effective_message.reply_text("שגיאה ברישום האישור. נסה שוב או פנה לתמיכה.")

async def cmd_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.effective_message.reply_text("שימוש: /approve <user_id> [סיבה]")
        return
    try:
        uid = int(context.args[0])
    except:
        await update.effective_message.reply_text("user_id לא תקין.")
        return
    reason = " ".join(context.args[1:]) if len(context.args) > 1 else None
    ok = await db_update_last_status(uid, "approved", reason)
    link = GROUP_STATIC_INVITE or "<לא הוגדר>"
    await update.effective_message.reply_text("עודכן ל-approved. קישור:\n"+link if ok else "לא נמצא תשלום אחרון למשתמש.")

async def cmd_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.effective_message.reply_text("שימוש: /reject <user_id> <סיבה>")
        return
    try:
        uid = int(context.args[0])
    except:
        await update.effective_message.reply_text("user_id לא תקין.")
        return
    reason = " ".join(context.args[1:]) if len(context.args) > 1 else "לא צוין"
    ok = await db_update_last_status(uid, "rejected", reason)
    await update.effective_message.reply_text("עודכן." if ok else "לא נמצא תשלום אחרון.")

def register_handlers():
    tg_app.add_handler(CommandHandler("start",   cmd_start))
    tg_app.add_handler(CommandHandler("site",    cmd_site))
    tg_app.add_handler(CommandHandler("invite",  cmd_invite))
    tg_app.add_handler(CommandHandler("approve", cmd_approve))
    tg_app.add_handler(CommandHandler("reject",  cmd_reject))
    tg_app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, on_payment_proof))

# ===== FastAPI =====
@app.get("/health")
def health(): return {"ok": True}

@app.get("/version")
def version(): return {"version": VERSION_TAG}

@app.get("/meta")
def meta():
    return {"status":"ok","service":"telegram-gateway-bot","version":VERSION_TAG,"site_url":SITE_URL,"has_invite":bool(GROUP_STATIC_INVITE)}

@app.get("/config")
def config():
    return {"site_url": SITE_URL, "invite_set": bool(GROUP_STATIC_INVITE), "price_nis": SLH_NIS}

@app.get("/admin/stats")
def admin_stats(request: Request):
    if not (ADMIN_DASH_TOKEN and (
        request.headers.get("Authorization","").replace("Bearer ","").strip()==ADMIN_DASH_TOKEN
        or request.query_params.get("token")==ADMIN_DASH_TOKEN
    )):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {"version": VERSION_TAG, "site_url": SITE_URL, "stats": db_get_stats()}

@app.post("/webhook")
async def webhook(request: Request):
    if WEBHOOK_SECRET and request.headers.get("X-Telegram-Bot-Api-Secret-Token","") != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Bad secret")
    data = await request.json()
    await tg_app.process_update(Update.de_json(data, tg_app.bot))
    return JSONResponse({"ok": True})

@app.on_event("startup")
async def on_startup():
    db_init_schema()
    register_handlers()
    try:
        await tg_app.bot.set_my_commands([
            ("start","התחל"), ("site","קישור לאתר"), ("invite","קישור לקהילה"),
            ("approve","אישור (Admin)"), ("reject","דחייה (Admin)"),
        ])
    except Exception:
        logger.warning("set_my_commands failed")
    logger.info(f"Bot ready | VERSION={VERSION_TAG} | SITE={SITE_URL}")