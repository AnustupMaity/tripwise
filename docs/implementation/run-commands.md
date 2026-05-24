# TripWise Run Commands (Windows PowerShell)

## 1) Start Backend

From project root:

```powershell
Set-Location D:/CODES/Tripwise/backend
D:/CODES/Tripwise/.venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Health check:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/health
```

Expected: StatusCode 200.

## 2) Start Frontend

Open a second PowerShell terminal:

```powershell
Set-Location D:/CODES/Tripwise/web
npm run dev
```

If you hit chunk/module runtime errors, use:

```powershell
Set-Location D:/CODES/Tripwise/web
npm run dev:clean
```

Note: Dev now uses `.next-dev` while production build uses `.next` to avoid cache collisions.

Open in browser:

- <http://localhost:3000>
- <http://localhost:3000/dashboard>

## 3) First-Time Setup (if needed)

Backend dependencies:

```powershell
Set-Location D:/CODES/Tripwise/backend
D:/CODES/Tripwise/.venv/Scripts/python.exe -m pip install -r requirements.txt
```

Frontend dependencies:

```powershell
Set-Location D:/CODES/Tripwise/web
npm install
```

## 4) Quick Smoke Checks

In a third terminal, run:

```powershell
(Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/health -TimeoutSec 10).StatusCode
(Invoke-WebRequest -UseBasicParsing http://127.0.0.1:3000 -TimeoutSec 10).StatusCode
(Invoke-WebRequest -UseBasicParsing http://127.0.0.1:3000/dashboard -TimeoutSec 15).StatusCode
```

Expected: 200 for all three.

## 5) If Frontend Shows Missing Chunk Errors

If you see errors like Cannot find module from .next files, clear cache and restart frontend:

```powershell
Set-Location D:/CODES/Tripwise/web
if (Test-Path .next) { Remove-Item -Recurse -Force .next }
npm run dev
```

## 6) Stop Servers

In each terminal running the server:

- Press Ctrl + C

## 7) E2E Token Without OTP (Seed Test User)

If OTP delivery is unavailable during testing, seed a test user with a known password and generate a valid session token.

From project root:

```powershell
Set-Location D:/CODES/Tripwise/backend
D:/CODES/Tripwise/.venv/Scripts/python.exe scripts/seed_test_user.py --email e2e@tripwise.dev --password "Tripwise@123" --name "E2E User" --nickname "e2e"
```

The script prints `session_token=...`.

Set token for Playwright in the same terminal where you run E2E:

```powershell
$env:E2E_SESSION_TOKEN="paste-token-here"
Set-Location D:/CODES/Tripwise/web
npm run test:e2e
```

Optional: fetch a fresh token via password login API instead of using the seeded token output:

```powershell
$body = @{ identifier = "e2e@tripwise.dev"; password = "Tripwise@123" } | ConvertTo-Json
$resp = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/auth/login/password -ContentType "application/json" -Body $body
$env:E2E_SESSION_TOKEN = $resp.sessionToken
Set-Location D:/CODES/Tripwise/web
npm run test:e2e
```
