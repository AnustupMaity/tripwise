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
   - `CORS_ALLOWED_ORIGINS=https://<your-vercel-domain>,http://localhost:3000`
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

