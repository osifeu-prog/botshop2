# BOTSHOP2  Deploy (Railway)

## Vars (Railway → Variables)
- BOT_TOKEN         = ... (מ-BotFather)
- WEBHOOK_SECRET    = ... (GUID או מחרוזת חזקה  לשמור זהה למה שנשלח ל-Telegram setWebhook)
- SITE_URL          = https://slh-nft.com/
- GROUP_STATIC_INVITE = (קישור הזמנה קבוע, אם יש)
- SLH_NIS           = 39
- VERSION_TAG       = {תאריך-שעה או ערך חופשי}

(אופציונלי בעתיד)
- DATABASE_URL      = postgres://... (אם מוסיפים DB)

## Procfile
web: python main.py

## בדיקות
- GET https://<service>.up.railway.app/health  → {"status":"ok",...}
- GET https://<service>.up.railway.app/meta    → קונפיג תקין

## Webhook
במחשב המקומי:
8350943244:AAGA_VEXbu9rpXfvs29mfZaKoDZneCHXhuk = "<BOT_TOKEN>"
4520c953-5288-4151-bc04-d0c979dd64e7 = "<WEBHOOK_SECRET>"
botshop2-production.up.railway.app = "<service>.up.railway.app"
Invoke-RestMethod "https://api.telegram.org/bot8350943244:AAGA_VEXbu9rpXfvs29mfZaKoDZneCHXhuk/deleteWebhook?drop_pending_updates=true"
Invoke-RestMethod -Method Post -Uri "https://api.telegram.org/bot8350943244:AAGA_VEXbu9rpXfvs29mfZaKoDZneCHXhuk/setWebhook" -Body @{ url="https://botshop2-production.up.railway.app/webhook"; secret_token=4520c953-5288-4151-bc04-d0c979dd64e7; drop_pending_updates="true" }
Invoke-RestMethod "https://api.telegram.org/bot8350943244:AAGA_VEXbu9rpXfvs29mfZaKoDZneCHXhuk/getWebhookInfo"