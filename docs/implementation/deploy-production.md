# TripWise Production Deploy

## 1) Supabase (Database)

1. Open Supabase project `vawunfhyxczxqszavtkn`.
2. Use one connection string only (same project for all keys):
   - `SUPABASE_URL`
   - `SUPABASE_ANON_KEY`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `SUPABASE_DB_URL`
3. Prefer Session Pooler URI for IPv4 networks, and keep `?sslmode=require`.
4. Run SQL migrations in `supabase/migrations` on this project.

## 2) Backend Deploy (Render)

1. Push repo to GitHub.
2. In Render: `New +` -> `Blueprint`.
3. Select this repo; Render reads `render.yaml`.
4. Fill environment values when prompted:
   - `APP_BASE_URL=https://<your-backend-domain>`
   - `CORS_ALLOWED_ORIGINS=https://tripwise-liard.vercel.app,http://localhost:3000,http://127.0.0.1:3000`
   - `SUPABASE_DB_URL=<session-pooler-uri>`
   - `SUPABASE_URL=<project-url>`
   - `SUPABASE_ANON_KEY=<anon-key>`
   - `SUPABASE_SERVICE_ROLE_KEY=<service-role-key>`
   - `BREVO_API_KEY=<brevo-key>`
   - `BREVO_SENDER_EMAIL=<sender-email>`
   - `GOOGLE_CLIENT_ID=<google-client-id>`
   - `GOOGLE_CLIENT_SECRET=<google-client-secret>`
   - `JWT_SECRET=<long-random-secret>`
5. Deploy and confirm:
   - `GET /health` returns `{"status":"ok"}`.

## 3) Web Deploy (Vercel)

1. In Vercel: `Add New...` -> `Project`.
2. Import same repo.
3. Set Root Directory to `web`.
4. Environment variables:
   - `NEXT_PUBLIC_API_BASE_URL=https://<your-backend-domain>/api/v1`
   - `NEXT_PUBLIC_GOOGLE_CLIENT_ID=<google-client-id>`
5. Deploy.

## 4) Post-Deploy Smoke Test

1. Open web app.
2. Register/login flow.
3. Create trip.
4. Add expense and approve.
5. Generate report.
6. Verify email jobs in backend:
   - `GET /api/v1/notifications/jobs`

## 5) If DB Connection Fails

1. Confirm all Supabase values belong to the same project ref.
2. Confirm password in `SUPABASE_DB_URL` is URL-encoded.
3. Keep `sslmode=require`.
4. Check host/username matches Supabase dashboard exactly.
5. For local-only fallback:
   - `USE_INMEMORY_STORES=true`

## 6) Exact Env Checklist

Use this to keep Render and Vercel aligned with the deployed code.

### Render backend

- `APP_ENV=production`
- `APP_BASE_URL=https://<your-backend-domain>`
- `CORS_ALLOWED_ORIGINS=https://tripwise-liard.vercel.app,http://localhost:3000,http://127.0.0.1:3000`
- `AUTH_EXPOSE_OTP_IN_RESPONSE=false`
- `USE_INMEMORY_STORES=false`
- `SUPABASE_DB_URL=<session-pooler-uri>`
- `SUPABASE_URL=<project-url>`
- `SUPABASE_ANON_KEY=<anon-key>`
- `SUPABASE_SERVICE_ROLE_KEY=<service-role-key>`
- `BREVO_API_KEY=<brevo-key>`
- `BREVO_SENDER_EMAIL=<sender-email>`
- `BREVO_SENDER_NAME=TripWise`
- `GOOGLE_CLIENT_ID=<google-client-id>`
- `GOOGLE_CLIENT_SECRET=<google-client-secret>`
- `PUSH_WEBHOOK_URL=<optional-webhook-url-or-empty>`
- `NOTIFICATION_RETRY_MAX_ATTEMPTS=3`
- `NOTIFICATION_RETRY_BASE_DELAY_SECONDS=5`
- `JWT_SECRET=<long-random-secret>`

### Vercel web

- `NEXT_PUBLIC_API_BASE_URL=https://<your-backend-domain>/api/v1`
- `NEXT_PUBLIC_GOOGLE_CLIENT_ID=<google-client-id>`

### Quick smoke checks

1. Open `https://<your-backend-domain>/health` and confirm `{"status":"ok"}`.
2. Open `https://<your-backend-domain>/` and confirm a JSON landing payload, not `Not Found`.
3. Open the web app and confirm login/register pages can reach the backend without `Failed to fetch`.
4. Run a register OTP request and verify the browser network call goes to `https://<your-backend-domain>/api/v1/auth/register/request-otp`.
5. Sign in, open the dashboard, and confirm the session validator calls `https://<your-backend-domain>/api/v1/auth/session/validate`.
6. Create a trip and confirm the dashboard can load trips, members, and expenses without CORS errors.

