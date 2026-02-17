# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AlQuran AI is a two-part project:
- **Frontend**: React + Vite app in `sacred-scroll-ai-main/` (this directory)
- **Backend**: FastAPI app in the parent directory (`../`)

## Frontend Commands

```bash
npm run dev          # Dev server at localhost:8080
npm run build        # Production build to dist/
npm run build:dev    # Dev build with source maps
npm run lint         # ESLint
npm test             # Vitest (single run)
npm run test:watch   # Vitest watch mode
npm run preview      # Preview production build
npm run build:mobile # Build + Capacitor mobile sync
```

## Backend Commands

From the parent directory (`../`):

```bash
# Cloud deployment version (Groq/OpenAI)
pip install -r requirements-cloud.txt
uvicorn backend_cloud:app --host 0.0.0.0 --port 8000

# Local development version (Ollama)
pip install -r requirements.txt
uvicorn backend:app --host 0.0.0.0 --port 8000

# Docker
docker build -f Dockerfile -t alquran-backend .
docker run -p 8000:8000 --env-file .env alquran-backend
```

## Architecture

### Frontend (`src/`)

- **Entry**: `main.tsx` → wraps app with `GoogleOAuthProvider`
- **Routing** (`App.tsx`): `/` → Index (chat), `/login` → Login, `/privacy`, `*` → NotFound
- **Main chat interface**: `pages/Index.tsx` — sends/receives messages, manages sidebar, bookmarks, dark mode
- **Authentication**: Google OAuth → backend JWT; stored in `localStorage` as `user_token` + `user_profile`
- **API base**: `http://localhost:8000/api` (overridden by `VITE_API_URL` env var)
- **State**: Local React state + React Query for server data; no global store
- **Path alias**: `@/` maps to `./src/`

### Backend (`../`)

- **`backend_cloud.py`**: Primary FastAPI app used in production (Groq/OpenAI/Together.ai LLM providers)
- **`backend.py`**: Local-only version using Ollama
- **`auth.py`**: Google OAuth2 validation + JWT issuance (3-day expiry)
- **`database.py`**: SQLAlchemy ORM with SQLite; models: User, Chat, Message, Bookmark
- **`embeddings.py`**: ONNX Runtime-based embeddings (replaces PyTorch for smaller Docker image)
- **Vector search**: HNSW index files in `quran_data/` (quran_hadith.index + metadata.json)
- **Docker**: Multi-stage Python 3.11-slim build; deployed on Railway.app

### Key Backend Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/auth/google` | Exchange Google token for JWT |
| POST | `/api/chat` | Send message (auth required) |
| GET | `/api/chats` | User's chat list |
| GET | `/api/chats/{id}` | Chat + messages |
| DELETE | `/api/chats/{id}` | Delete chat |
| POST | `/api/messages/{id}/bookmark` | Bookmark message |
| GET | `/api/bookmarks` | User's bookmarks |

## Environment Variables

**Frontend** (`.env` in `sacred-scroll-ai-main/`):
```
VITE_API_URL=https://aiquran-production.up.railway.app
```

**Backend** (`.env` in `../`):
```
LLM_PROVIDER=groq|together|openai
GROQ_API_KEY=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
JWT_SECRET=
DATABASE_URL=sqlite:///./quranai.db
DATA_DIR=./quran_data
FRONTEND_URL=http://localhost:5173
PORT=8000
```

## Design System

- **Primary color**: `#007f80` (teal)
- **Accent**: `#D4AF37` (gold)
- **Dark bg**: `#0f2323`
- **Fonts**: Manrope (display), Amiri (Arabic/Quranic text)
- **Component library**: Radix UI + shadcn/ui pattern in `src/components/ui/`
- **Tailwind**: Custom theme in `tailwind.config.ts`; CSS vars in `src/index.css`

## Testing

- **Framework**: Vitest with jsdom environment
- **Test files**: `src/**/*.{test,spec}.{ts,tsx}`
- **Setup**: `src/test/setup.ts`
- Backend has no automated tests; use curl or Postman against the running API.

## Deployment

- Hosted on Railway.app via `Dockerfile` + `railway.json`
- Healthcheck: `GET /health` (120s timeout)
- Port is read from `$PORT` env var in the Dockerfile CMD
- ONNX Runtime used instead of PyTorch to keep the image ~1–1.5 GB
