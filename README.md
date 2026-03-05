# clipforge

> AI gameplay-to-content engine. Upload raw footage → get TikTok clip + YouTube reel + cinematic trailer. Automatically.

[![CI](https://github.com/LakshmiSravyaVedantham/clipforge/actions/workflows/ci.yml/badge.svg)](https://github.com/LakshmiSravyaVedantham/clipforge/actions/workflows/ci.yml)
[![Deploy](https://github.com/LakshmiSravyaVedantham/clipforge/actions/workflows/deploy.yml/badge.svg)](https://github.com/LakshmiSravyaVedantham/clipforge/actions/workflows/deploy.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-violet.svg)](LICENSE)

---

## Demo

```
Upload gameplay.mp4 (10 min)
        ↓
   clipforge AI
        ↓
┌───────────────────────────────────┐
│  tiktok.mp4   → 60s  · 9:16      │
│  youtube.mp4  → 8min · 16:9      │
│  trailer.mp4  → 90s  · cinematic │
└───────────────────────────────────┘
   Download as ZIP
```

## How it works

```
Upload (mp4/mov/mkv, ≤500MB, ≤10min)
     ↓
Scene detection  — PySceneDetect finds cut boundaries
     ↓
Highlight scoring — librosa RMS audio energy ranks scenes
     ↓
Clip selection   — top 10 moments by score
     ↓
Format assembly  — moviepy cuts, crops, composes
  ├── TikTok  : best moment · vertical crop · Whisper captions
  ├── YouTube : top moments sequenced · transitions
  └── Trailer : fast cuts → slow-mo climax (0.5x)
     ↓
ZIP download (all 3 files)
```

## Stack

| Layer | Tech |
|---|---|
| Backend API | FastAPI + BackgroundTasks |
| Scene detection | PySceneDetect |
| Audio scoring | librosa (RMS energy) |
| Video editing | moviepy |
| Captions | OpenAI Whisper (local, base model) |
| Frontend | Next.js 15 · Tailwind CSS |
| Deploy | Railway (backend) · Vercel (frontend) |

## Local setup

```bash
# Clone
git clone https://github.com/LakshmiSravyaVedantham/clipforge
cd clipforge

# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

Open http://localhost:3000 — drag in a gameplay video.

## Deploy your own

### Backend → Railway
1. Create a Railway project, add a service from this repo (`/backend` root)
2. Set start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
3. Add `RAILWAY_TOKEN` to GitHub Actions secrets

### Frontend → Vercel
1. `vercel` in the `frontend/` directory
2. Set `NEXT_PUBLIC_API_URL` to your Railway URL
3. Add `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` to GitHub secrets

GitHub Actions will deploy both on every push to `main`.

## Tests

```bash
cd backend
pip install pytest numpy
python -m pytest tests/ -v
# 21 tests · all passing
```

## License

MIT — [Lakshmi Sravya Vedantham](https://github.com/LakshmiSravyaVedantham)
