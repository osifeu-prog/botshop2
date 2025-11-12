# BOTSHOP_CLEAN (single-file)

- FastAPI + Telegram Webhook ב-`main.py`
- עובד בלי DB (in-memory) או עם Postgres (`DATABASE_URL`)

## Railway
Variables (לפחות):
- `BOT_TOKEN`
- `WEBHOOK_URL` = https://<service>.up.railway.app/webhook

מומלץ:
- `ADMIN_DASH_TOKEN`, `SITE_URL`, `GROUP_STATIC_INVITE`, `SLH_NIS=39`
אופציונלי:
- `WEBHOOK_SECRET`, `DATABASE_URL`

## אחרי deploy: קבע webhook ידנית (ב-PowerShell)
$BOT = "<BOT_TOKEN>"
$URL = "https://<service>.up.railway.app/webhook"
$S   = "<WEBHOOK_SECRET>"   # אם השתמשת

Invoke-RestMethod "https://api.telegram.org/bot$BOT/deleteWebhook?drop_pending_updates=true"
$body = @{ url=$URL; drop_pending_updates="true" }
if ($S) { $body["secret_token"] = $S }
Invoke-RestMethod -Method Post -Uri "https://api.telegram.org/bot$BOT/setWebhook" -Body $body

## בדיקות
$BASE = "https://<service>.up.railway.app"
Invoke-RestMethod "$BASE/health"
Invoke-RestMethod "$BASE/meta"
Invoke-RestMethod "$BASE/config"
Invoke-RestMethod "$BASE/admin/stats?token=<ADMIN_DASH_TOKEN>"