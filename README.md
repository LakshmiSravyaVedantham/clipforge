# clipforge

AI gameplay-to-content engine. Upload footage, get TikTok clip + YouTube reel + cinematic trailer — automatically.

## How it works

1. Upload any gameplay video (mp4, mov, mkv — max 500MB, max 10 min)
2. AI detects scene boundaries and ranks highlights by audio excitement
3. Download 3 ready-to-post formats as a ZIP:
   - **TikTok/Reels** (60s, vertical 9:16, auto-captions)
   - **YouTube highlight reel** (up to 10 min, top moments)
   - **Cinematic trailer** (90s, slow-mo climax + fast cuts)

## Stack

- **Backend**: Python, FastAPI, PySceneDetect, librosa, moviepy, Whisper
- **Frontend**: Next.js 15, Tailwind CSS
- **Deploy**: Railway (backend) + Vercel (frontend)

## Local development

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## License

MIT
