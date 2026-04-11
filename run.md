## Prerequisites (install once)

```bash
# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install pnpm
npm install -g pnpm
```

---

## Step 1 — Install dependencies

```bash
# Backend
cd backend && uv sync

# Dashboard
cd ../dashboard && pnpm install

# Desktop client (optional)
cd ../desktop-client && uv sync
```

---

## Step 2 — Create `.env` files

**.env** (copy from example and set these key values):

```bash
cp backend/.env.example backend/.env
```

Then edit .env with these values to **skip Vertex AI** and use a Gemini API key instead:

```env
# --- Switch OFF Vertex AI ---
GOOGLE_GENAI_USE_VERTEXAI=false
GOOGLE_API_KEY=your-gemini-api-key          # get from https://aistudio.google.com

# --- Disable Vertex AI Agent Engine (use in-memory sessions instead) ---
USE_AGENT_ENGINE_SESSIONS=false
USE_AGENT_ENGINE_MEMORY_BANK=false
USE_AGENT_ENGINE_CODE_EXECUTION=false

# --- Firebase (still needed for auth) ---
FIREBASE_PROJECT_ID=your-firebase-project-id
FIREBASE_SERVICE_ACCOUNT=path/to/firebase-service-account.json

# --- App ---
ENVIRONMENT=development
BACKEND_PORT=8000
BACKEND_HOST=0.0.0.0
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
FRONTEND_URL=http://localhost:5173
BACKEND_URL=http://localhost:8000

# --- E2B (optional, for code sandboxing) ---
E2B_API_KEY=your-e2b-api-key

# --- Models (Gemini AI Studio versions, not Vertex) ---
LIVE_MODEL=gemini-2.0-flash-live-001
TEXT_MODEL=gemini-2.5-flash
```

**.env** (copy from example):

```bash
cp dashboard/.env.example dashboard/.env
```

Fill in your Firebase web config (from Firebase Console → Project Settings → Your apps).

---

## Step 3 — Run the servers

**Terminal 1 — Backend:**
```bash
cd backend
uv run python dev.py
# → http://localhost:8000
# → API docs: http://localhost:8000/docs
```

**Terminal 2 — Dashboard:**
```bash
cd dashboard
pnpm run dev
# → http://localhost:5173
```

**Terminal 3 — Desktop client (optional):**
```bash
cd desktop-client
uv run python src/main.py
```

---

## What you still need (non-AI cloud services)

| Service | Why needed | Free tier? |
|---|---|---|
| **Firebase project** | Auth (login) | Yes |
| **Gemini API key** | AI (replaces Vertex AI) | Yes (AI Studio) |
| **E2B API key** | Code execution sandbox | Optional |

The key env vars that bypass Vertex AI are:
- `GOOGLE_GENAI_USE_VERTEXAI=false` — use Gemini AI Studio instead
- `USE_AGENT_ENGINE_SESSIONS=false` — use in-memory sessions locally
- `USE_AGENT_ENGINE_MEMORY_BANK=false`
- `USE_AGENT_ENGINE_CODE_EXECUTION=false`