# Private Render rehearsal

This branch contains deployment preparation only. No Render resources or production data are created here.

## Web service

- Runtime: Python
- Build: `pip install -r requirements.txt && cd app/frontend && npm install && npm run build`
- Start: `uvicorn app.api.main:app --host 0.0.0.0 --port $PORT`
- Health check: `/api/health`
- Frontend and `/api/*` are served from one HTTPS origin.

Create a temporary Render PostgreSQL database first, then set `DATABASE_URL` in the web service environment. The application accepts `postgresql://` and `postgresql+psycopg://` URLs and does not fall back to SQLite.

## Required environment names

`DATABASE_URL`, `KIDPRODUCTIONZ_AUTH_MODE=cloud`, `KIDPRODUCTIONZ_AUTH_USERNAME`, `KIDPRODUCTIONZ_AUTH_PASSWORD`, `SESSION_SECRET`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `HUBSPOT_ACCESS_TOKEN`, `HUBSPOT_PORTAL_ID`, `HUBSPOT_PIPELINE_ID`, `HUBSPOT_STAGE_ID`, `HUBSPOT_WRITE_ENABLED`, `BOOKING_URL`, `GMAIL_ENABLED`, `GOOGLE_CALENDAR_ENABLED`.

Do not commit values. Cloud mode must require authentication; cookies are HttpOnly/SameSite=Lax and Secure when `APP_ENV` is production/cloud, with CSRF headers required for mutations.

## Google callback

After Render assigns the service hostname, add:
`https://<render-service-host>/api/google/oauth/callback`
to Google Cloud OAuth redirect URIs. Keep the existing localhost callback for desktop use.

## Validation sequence

Set `DATABASE_URL` only in the local shell/environment, run `alembic upgrade head`, then exercise `database_v2` CRUD against the temporary database. Do not point migrations at the LocalAppData SQLite database and do not migrate real data during this rehearsal.
