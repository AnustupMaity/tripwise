# TripWise

TripWise is a group trip expense management platform with web and mobile clients.

## Monorepo Layout

- `backend/` - FastAPI application for domain logic and APIs
- `web/` - Next.js web app (web-first rollout)
- `mobile/` - React Native app (planned)
- `supabase/` - SQL migrations and local config
- `docs/` - Architecture and product contracts

## Current Implementation Status

Initial scaffold is in place with:

- FastAPI app skeleton and route modules
- Supabase SQL migration for core domain entities
- Next.js app shell with animated welcome/auth placeholders
- In-memory auth workflow implementation for local development

## Auth API (Implemented)

Base prefix: `/api/v1/auth`

- `POST /register/request-otp` - begin registration and create OTP
- `POST /register/verify-otp` - verify registration OTP and create account/session
- `POST /login/request-otp` - request login OTP for email or phone
- `POST /login/verify-otp` - verify OTP and create session (email or phone)
- `POST /login/password` - login via password (email or phone)
- `POST /forgot-password/request-otp` - request forgot-password OTP
- `POST /forgot-password/verify-otp` - verify forgot-password OTP and issue reset token
- `POST /forgot-password/reset` - set new password using reset token
- `POST /google/callback` - Google login callback contract (stubbed verification)
- `POST /session/validate` - validate session with inactivity checks
- `POST /profile/complete` - collect missing phone/UPI details after OAuth login

## Trip API (Implemented)

Base prefix: `/api/v1/trips`

- `POST /` - create trip, attach admin creator member, and process initial members
- `GET /?creator_identifier=...` - list trips created by identifier
- `GET /{trip_id}/members` - list members with edit capability flags
- `GET /{trip_id}/members/eligible` - list only accepted members used for split calculations
- `POST /{trip_id}/members/invite` - invite/add a new member
- `POST /members/{member_id}/respond` - accept or reject pending invite
- `POST /members/{member_id}/reinvite` - set member invite status back to pending
- `DELETE /members/{member_id}` - remove member from trip
- `POST /{trip_id}/close` - close trip (admin only), freeze edits, return settlement snapshot
- `POST /{trip_id}/archive` - move trip to past (admin only)

Invite behavior implemented:

- Registered identifier (profile exists): member created in `pending` invite state
- Unregistered identifier: guest created in `pending` invite state as `guest` role (view-only after acceptance)
- Pending/rejected members are excluded from split-eligible list
- `member_count` is synchronized from all current trip members (accepted, pending, rejected) and updates on invite/respond/remove
- Invite edge protections: no duplicate invite per identifier in a trip, no removing last accepted admin, bulk invite-all endpoint available

## Expense API (Implemented)

Base prefix: `/api/v1/expenses`

- `POST /` - add expense with multi-payer and split strategy payload
- `GET /?trip_id=...` - list trip expenses
- `GET /pending?trip_id=...&admin_identifier=...` - list pending approvals for admin
- `POST /{expense_id}/approve` - approve a pending expense (admin)
- `POST /{expense_id}/reject` - reject an expense (admin)

Expense behavior implemented:

- Admin-added expense is auto-approved
- Member-added expense goes to `pending_approval`
- Guest members cannot add expenses
- Split strategies supported: `equal`, `unequal`, `percentage`, `selective`, `custom`
- Multiple payers supported; payer contributions must sum to total amount

## Dispute API (Implemented)

Base prefix: `/api/v1/disputes`

- `POST /` - raise dispute for an expense (accepted members)
- `GET /?trip_id=...` - list trip disputes
- `GET /{dispute_id}` - get dispute details and comments timeline
- `POST /{dispute_id}/review` - mark dispute in review (admin)
- `POST /{dispute_id}/resolve` - resolve dispute with resolution comment (admin)
- `POST /{dispute_id}/comments` - add comments by accepted members

Dispute states implemented:

- `open` -> `in_review` -> `resolved`

## Payment & Settlement API (Implemented)

Base prefix: `/api/v1/payments`

- `GET /settlement?trip_id=...` - compute who owes whom from approved expenses
- `POST /mark-paid` - record a completed settlement payment
- `GET /history?trip_id=...` - transaction history for a trip

Settlement behavior:

- Uses approved expenses only
- Builds pairwise obligations from expense splits and multi-payer contributions
- Collapses to net balances and minimizes transfers
- Includes unresolved dispute count (`open` / `in_review`) as a settlement blocker signal

## Realtime Events (Wired)

Base prefix: `/api/v1/realtime`

- `GET /{trip_id}` - view recent in-memory event feed (debug endpoint)

Events currently emitted:

- `expense_added`
- `expense_approved`
- `expense_rejected`
- `dispute_raised`
- `dispute_in_review`
- `dispute_resolved`
- `dispute_comment_added`
- `payment_marked_paid`

Additional lifecycle/report events:

- `trip_closed`
- `trip_archived`
- `report_generated`

## Reports API (Implemented)

Base prefix: `/api/v1/reports`

- `POST /generate` - generate report metadata + settlement snapshot
- `GET /?trip_id=...` - list generated reports for trip

Supported report types:

- `summary`
- `detailed`
- `settlement`
- `expense_breakdown`

Supported formats:

- `pdf`
- `excel`
- `json`

Note: OTP values are returned in API responses for development-only local testing.

### Persistence Modes

- Default: in-memory auth store (works without external services)
- Supabase-backed: set `SUPABASE_DB_URL` in `backend/.env` to persist users and sessions in Postgres
- Force local mode: set `USE_INMEMORY_STORES=true` to bypass Postgres while developing

Auth persistence now also supports DB-backed:

- pending registrations (pre-OTP-verified signup state)
- OTP challenges with expiry and attempt counters
- password reset tokens
- OTP send rate-limit counters

OTP abuse protection:

- Maximum `3` OTP send requests per identifier and flow within `30` minutes
- Maximum `5` OTP verification attempts per issued challenge

## Quick Start

### Backend

```powershell
cd backend
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
py -3.10 -m pip install -r requirements.txt
py -3.10 -m uvicorn app.main:app --reload
```

### Web

```powershell
cd web
npm install
npm run dev
```

## Production Deploy

- Backend + Web deploy steps: `docs/implementation/deploy-production.md`
- Render blueprint for backend: `render.yaml`
