# TripWise ✈️ — Lightning-Fast Group Expense Management

[![Live on Vercel](https://img.shields.io/badge/Live%20on-Vercel-black?logo=vercel)](https://tripwise-liard.vercel.app)
[![0ms Latency](https://img.shields.io/badge/UI%20Latency-0ms-38bdf8?style=flat&logo=speedtest)](https://tripwise-liard.vercel.app)
[![Design System](https://img.shields.io/badge/UI-Apple%20OS%20%2F%20Oxygen%20OS-818cf8?style=flat)](https://tripwise-liard.vercel.app)

**TripWise** is an industry-grade group trip expense management application designed for tracking shared costs, approvals, disputes, settlements, and reports. 

Recently engineered with a state-of-the-art **Apple OS / Oxygen OS glassmorphic design system** and an ultra-optimized **0ms instant hydration SWR caching architecture**, TripWise delivers a lag-free, premium user experience.

---

## 🌟 What's New: Next-Gen Architecture & UI

### 📱 Progressive Web App (Mobile App)
- **Native WebAPK Generation**: TripWise is fully PWA compliant. It can be installed directly from Google Chrome on Android as a native application without needing an App Store.
- **Offline Capable Service Worker**: Uses `next-pwa` to aggressively cache static assets and network requests, ensuring the app loads instantly even on weak networks.
- **Standalone Experience**: Hides the browser UI completely, features custom splash screens, and perfectly formatted OS icons (192x192 & 512x512).

### ⚡ 0ms SWR Caching & Synchronous Hydration
- **Zero Blocking Spinners**: Route navigation and tab switching hydrate instantly in **0ms** from a synchronous local cache (`cache-store.ts`), eliminating UI lag and spinners.
- **Optimistic UI Updates**: Adding expenses, reviewing approvals, and marking payments update the UI instantaneously in memory while syncing with the backend silently in the background.
- **Non-Blocking Auth Shell**: Synchronous session checks allow the application shell and navigation bars to render immediately without waiting for network verification.

### 🎨 Premium "Apple OS / Oxygen OS" Glassmorphism
- **Midnight Dark Mode**: Engineered with rich HSL obsidian/midnight color tokens (`#0a0b0e`, `#12141a`, `#181b24`), vibrant cyan/indigo accents (`#38bdf8`, `#818cf8`), and emerald positive indicators (`#34d399`).
- **Frosted Glass Cards & Modals**: Implements deep backdrop blurring (`backdrop-filter: blur(20px)`), translucent borders, and subtle glowing hover effects.
- **Micro-Animations & Toast Banners**: Features smooth cubic-bezier transitions, `fadeInUp` card mounting animations, and macOS-style floating toast notification banners (`.os-toast`).

---

## 🛠️ Tech Stack

- **Frontend**: Next.js 14 (App Router), React 18, TypeScript, Custom Vanilla CSS Design System
- **Backend**: FastAPI, Python 3.10+, Pydantic v2
- **Database**: Supabase Postgres (with optional local in-memory fallback)
- **Auth / Notifications**: Supabase Auth, Google Sign-In, Brevo Email

---

## 🚀 Quick Start & Run Commands

### 📱 How to Install the Mobile App (Android)
The easiest way to get the TripWise mobile app on your Android device:
1. Open **Google Chrome** on your Android phone.
2. Navigate to the live deployment URL (e.g., `https://tripwise-mu.vercel.app`).
3. Tap the **Three Dots (⋮)** in the top right corner of Chrome.
4. Tap **"Install app"** (or "Add to Home screen").
5. Chrome will silently generate a native APK in the background and install TripWise directly into your app drawer!

---

### Local Development Setup

Follow these exact commands to start the application locally in Windows PowerShell:

### 1️⃣ Start the Backend (FastAPI Server)

Open a terminal and run:

```powershell
# Navigate to backend directory
cd backend

# Create and activate virtual environment (if not already created)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Start the FastAPI development server
uvicorn app.main:app --reload --port 8000
```
> **Backend URL**: [http://127.0.0.1:8000](http://127.0.0.1:8000)  
> **Health Check**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)  
> **API Docs (Swagger)**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

### 2️⃣ Start the Frontend (Next.js Web App)

Open a **new terminal window** and run:

```powershell
# Navigate to web directory
cd web

# Install npm dependencies (if not installed)
npm install

# Start the Next.js development server
npm run dev
```
> **Web Application URL**: [http://localhost:3000](http://localhost:3000)

---

### 3️⃣ Run Automated Verification Suite (E2E Tests)

TripWise includes a comprehensive automated test script (`backend/test_e2e_all.py`) that thoroughly verifies every single application function, including user registration, authentication lifecycle, OTP notification delivery, trip creation, member invitations, equal and percentage expense splitting, admin approvals, debt simplification algorithms ("Who Owes Whom"), settlement execution, and PDF report generation without needing Selenium or external tools.

Open a terminal and run:

```powershell
# Navigate to backend directory
cd backend

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Run the automated verification suite
python test_e2e_all.py
```
> **Expected Output**: `[SUCCESS] ALL TRIPWISE FUNCTIONS & SPLITTING ALGORITHMS VERIFIED 100%!`

---

## 💡 Key Features & Workflow

- **🔐 Multi-Modal Authentication**: Register and log in via OTP, secure password, or Google Sign-In.
- **✈️ Trip & Member Management**: Create self-managed trips or send dynamic email invitations to group members.
- **💸 Intelligent Split Strategies**: Split expenses equally, by custom exact amounts, or by percentage shares. Supports multiple payers per expense.
- **✋ Real-Time Approvals**: Transparent workflow requiring leader or member approval before expenses are confirmed into the ledger.
- **⚖️ Dispute Resolution System**: Raise formalized disputes on contested expenses with audit comments and resolution notes.
- **🤝 Automated Settlements**: Calculates the simplest debt resolution matrix ("Who Owes Whom") and supports one-click payment marking.
- **📄 Comprehensive Reports**: Generate summary links and export detailed trip audit reports in multiple formats.

---

## ⚙️ Local Environment Configuration

For local development, configure your backend settings in `backend/.env`.

### Recommended Local Settings (`backend/.env`)
```ini
APP_ENV=development
APP_BASE_URL=http://localhost:8000
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
USE_INMEMORY_STORES=false
AUTH_EXPOSE_OTP_IN_RESPONSE=true
```

### Optional Supabase Database Integration
To use Supabase Postgres instead of local storage, append your database credentials:
```ini
SUPABASE_URL=your_supabase_project_url
SUPABASE_ANON_KEY=your_supabase_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key
SUPABASE_DB_URL=postgresql://user:password@host:port/dbname
```

---

## 📁 Project Directory Structure

```text
├── backend/                  # FastAPI backend application & API routes
│   ├── app/
│   │   ├── api/routes/       # Endpoints for trips, expenses, auth, settlements
│   │   ├── services/         # Business logic and database access layers
│   │   └── main.py           # Application entry point & CORS configuration
├── web/                      # Next.js 14 frontend web application
│   ├── app/
│   │   ├── (main)/dashboard/ # 0ms latency dashboard pages (Trips, Ledger, Invites)
│   │   ├── components/       # Reusable UI components & SVG Icon library
│   │   ├── lib/              # Cache store, SWR client, API client
│   │   └── globals.css       # Apple OS / Oxygen OS Glassmorphic design tokens
├── supabase/                 # Database migrations and schema definitions
└── docs/                     # Architectural diagrams and implementation notes
```
