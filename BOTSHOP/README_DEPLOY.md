# BOTSHOP service (Railway)
- Root Directory (in Railway): **/BOTSHOP**
- Required variables:
  - BOT_TOKEN
  - WEBHOOK_URL = https://<service>.up.railway.app/webhook
  - WEBHOOK_SECRET (optional but recommended)
  - ADMIN_DASH_TOKEN
  - SITE_URL = https://slh-nft.com/
  - GROUP_STATIC_INVITE = <your permanent invite> (or leave empty)
  - SLH_NIS = 39
  - DATABASE_URL = postgresql://USER:PASSWORD@HOST:PORT/DB?sslmode=require
  - VERSION_TAG = manual-20251112-201058

Test endpoints:
- GET /health
- GET /meta
- GET /config
- GET /admin/stats?token=<ADMIN_DASH_TOKEN>
