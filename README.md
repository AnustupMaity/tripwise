# TripWise

[![Live on Vercel](https://img.shields.io/badge/Live%20on-Vercel-black?logo=vercel)](https://tripwise-liard.vercel.app)

TripWise is a group trip expense management app for tracking shared costs, approvals, disputes, settlements, and reports.

## Tech Stack

- Frontend: Next.js 14, React 18, TypeScript
- Backend: FastAPI, Python 3.10+
- Database: Supabase Postgres
- Auth / Email / Payments: Supabase, Google Sign-In, Brevo

## What The App Does

- Register and login with OTP, password, and Google Sign-In
- Create and manage trips
- Add expenses with split strategies and multiple payers
- Review or reject pending expenses
- Raise and resolve disputes
- Calculate settlements and mark payments
- Generate trip reports

## Local Setup

### 1) Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend health check:

- [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

### 2) Web

```powershell
cd web
npm install
npm run dev
```

Web app:

- [http://localhost:3000](http://localhost:3000)

## Local Environment

For local development, keep the backend settings in `backend/.env`.

Recommended local values:

- `APP_ENV=development`
- `APP_BASE_URL=http://localhost:8000`
- `CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000`
- `USE_INMEMORY_STORES=false`
- `AUTH_EXPOSE_OTP_IN_RESPONSE=true`

If you want to use Supabase locally, add these too:

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_DB_URL`

Optional local integrations:

- `BREVO_API_KEY`
- `BREVO_SENDER_EMAIL`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `JWT_SECRET`

## Local Notes

- OTP values may be returned in API responses during local testing.
- The backend uses Supabase Postgres when `SUPABASE_DB_URL` is set and `USE_INMEMORY_STORES=false`.
- If you do not want external services locally, leave the optional integration values empty and use the in-memory stores.

## Project Files

- `backend/` - FastAPI backend
- `web/` - Next.js frontend
- `supabase/` - SQL migrations
- `docs/` - architecture and implementation notes
- `render.yaml` - backend deployment blueprint

## Useful Paths

- Backend health: [backend/app/main.py](backend/app/main.py)
- Auth routes: [backend/app/api/routes/auth.py](backend/app/api/routes/auth.py)
- Web login page: [web/app/auth/login/page.tsx](web/app/auth/login/page.tsx)
- Web register page: [web/app/auth/register/page.tsx](web/app/auth/register/page.tsx)
