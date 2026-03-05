# clipforge — Design Document
**Date:** 2026-03-05
**Status:** Approved

---

## Problem

Gamers, streamers, and studios have hours of raw gameplay footage but no fast way to turn it into polished content. Editing is skilled, slow, expensive work. Most great gameplay moments are never shared.

## Solution

Upload one gameplay video → AI identifies the best moments → download 3 ready-to-post formats:
- **TikTok/Reel** (60s) — single best moment, auto-captions, vertical crop
- **YouTube highlight** (5–10 min) — top moments sequenced with transitions
- **Cinematic trailer** (90s) — dramatic pacing, music sync, slow-mo on peaks

---

## Architecture

```
Upload (mp4/mov, up to 10 min)
     ↓
Scene Analysis (PySceneDetect — shot boundary detection)
     ↓
Highlight Scoring (audio peaks + motion intensity)
     ↓
Clip Selection (top N moments ranked by score)
     ↓
Format Assembly
  ├── TikTok: best single moment, auto-caption, vertical crop
  ├── YouTube: top moments sequenced, transitions
  └── Trailer: cinematic pacing, music sync, slow-mo on peaks
     ↓
Download as ZIP
```

## Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js (App Router) + Tailwind, deployed to Vercel |
| Backend API | FastAPI (Python) |
| Video processing | PySceneDetect, moviepy, librosa |
| Captions | OpenAI Whisper (local) |
| Hosting | Railway (backend), Vercel (frontend) |
| Storage | Local temp files → cleaned after download |

---

## MVP Scope

### In
- Upload gameplay video (mp4/mov, ≤10 min, ≤500MB)
- Auto-detect 5–10 highlight moments using audio + motion analysis
- Export 3 formats: TikTok clip, YouTube highlight reel, trailer
- Auto-generated captions via Whisper
- Download all 3 as a single ZIP file
- Processing status page with progress updates (SSE or polling)

### Out (v1)
- Real-time stream capture (Twitch/YouTube integration)
- Game-specific event detection (kills, deaths, wins)
- Custom branding / logo overlays
- Music licensing — royalty-free library or user-provided
- User accounts / history

---

## Data Flow

1. User uploads video via web UI
2. Backend receives file, assigns job ID, starts processing in background
3. Frontend polls `/status/{job_id}` every 2s
4. Processing pipeline runs: scene detect → score → assemble formats
5. On completion, ZIP available at `/download/{job_id}`
6. Files deleted from server after 1 hour

---

## Key Technical Decisions

- **PySceneDetect** over manual frame diffing — battle-tested, fast
- **librosa** for audio peak detection — audio excitement (explosions, kills) correlates strongly with highlight quality
- **moviepy** for assembly — Python-native, handles all format conversions
- **Whisper** for captions — runs locally, no API cost, good accuracy on gaming audio
- **No user accounts in v1** — reduces complexity; job ID is the only state

---

## Success Criteria

- Upload to download in <5 minutes for a 10-min video
- TikTok clip captures at least 1 genuinely exciting moment
- YouTube reel feels watchable without manual editing
- Works on footage from at least: FPS games, racing games, sports games

---

## Name

**clipforge** — raw footage in, polished content out.
