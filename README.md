# 🌾 KrishiMitra (कृषिमित्र)

An AI farming companion for Nepali farmers — chat in Nepali (Devanagari or Romanized), get district-accurate crop advice, live weather alerts, market price forecasts, disease help, and a credit-readiness score built from your own conversation.

## Demo

<!-- Drag & drop your demo video (.mp4, <10 MB) into this file on GitHub's web editor
     and it will embed automatically. For YouTube, use the thumbnail-link form below. -->

> 🎬 Demo video coming soon.

<!-- YouTube option:
[![KrishiMitra Demo](https://img.youtube.com/vi/YOUR_VIDEO_ID/maxresdefault.jpg)](https://www.youtube.com/watch?v=YOUR_VIDEO_ID)
-->

## Features

- **Conversational profile collection** — the bot chats naturally in Nepali and extracts crop, district, land size, irrigation, experience, loans etc. from free-form messages (multi-slot LLM extraction + rule validation).
- **Advisory intent-router** — ask directly, get engine-computed answers (never hallucinated):
  - *"अहिले के लगाउने?"* → crop recommendations by district zone + altitude + month, annotated with live weather
  - *"आलुको भाउ कति?"* → Kalimati price forecast with trend % and best-selling month
  - *"पानी पर्छ?"* → 7-day Open-Meteo forecast with frost / heat / heavy-rain alerts
  - *"कहिले टिप्ने?"* → harvest window projected from sowing month
- **Disease & pest answers** — RAG-grounded first-aid guidance with treatment options.
- **Knowledge base (RAG)** — crop guide PDFs + the *Krishi Diary 2082* (legacy-font pages OCR'd to Devanagari via Gemini vision, table-aware chunking, BGE-M3 embeddings in Qdrant).
- **Credit scoring** — estimates seasonal income (district yields × market prices) and produces a 0–850 score with breakdown; admin dashboard included.


## Architecture

```
React (TanStack Router/Query) ──► FastAPI (/api/v1) ──► Dialogue policy (rules, unit-tested)
                      │                     │
                      │                     ├── Engines: crop_advisor · price_snapshot ·
                      │                     │   market_calendar · weather · calendar · credit scorer
                      ├── MongoDB           └── LLM (Gemini) renders replies from
                      │   users · profiles ·     engine-computed DATA facts
                      │   conversation_history · chat_sessions
                      └── Qdrant (embedded local or cloud) ── BGE-M3 embeddings
```

Design rule: **Python decides, the LLM only phrases.** Facts (crops, prices, dates, weather) come from engines/data and are injected as an authoritative DATA block.

## Setup

**Prereqs:** Python 3.11+, MongoDB (Atlas or local), a Google AI Studio API key.

```bash
pip install -r requirements.txt
```

Create `.env`:

```env
MONGODB_URI=mongodb+srv://...
GOOGLE_API_KEY=...
QDRANT_URL=./qdrant_local        # local embedded store — or https://<cluster>.qdrant.io for cloud
QDRANT_API_KEY=                  # only for cloud
JWT_SECRET=change-this-in-production
```

## Run

```bash
# Backend (port 8000)
uvicorn main:app --reload

# Frontend (port 5173)
cd frontend
npm install
npm run dev
```

Set `VITE_API_BASE_URL` in `frontend/.env.local` if the backend isn't on `http://127.0.0.1:8000/api/v1`.

API docs: http://localhost:8000/docs

## Knowledge-base ingestion

```bash
# Crop guide PDFs in ingest/ → Qdrant
python -m rag.ingest

# Krishi Diary (legacy fonts → Gemini vision OCR → Markdown cache → Qdrant)
python -m rag.ingest_vision transcribe   # paid, cached per page, resumable
python -m rag.ingest_vision ingest       # free, re-runnable
```

Transcribed pages are committed in `output/diary_md/`, so re-ingestion costs nothing.
Note: embedded Qdrant is single-process — stop the backend before running ingestion.

## Data

All CSV/JSON data lives under `data/` (previously split across `data/` and a separate `dataset/`, now merged):

| Source | Coverage |
|---|---|
| `data/crop_calendar.csv` | 90 crops — planting/harvest months, altitude range, diseases |
| `data/crop_risks.csv` | 90 crops — flood/drought/frost/price-volatility risk scores |
| `data/yield.csv` | 80 districts — per-district crop yields |
| `data/forecast_cache.csv` | Prophet price forecasts per crop per BS month |
| `rules/zone_classifier.py` | 83 districts → Terai / Hills / Mountains |
| `data/legacy/` | superseded/unused source files, kept for reference only |

## Key endpoints

| Endpoint | Purpose |
|---|---|
| `POST /api/v1/auth/register` · `/login` | JWT auth |
| `POST /api/v1/chat` | main conversational endpoint (accepts/returns `session_id`) |
| `GET /api/v1/chat/sessions` · `POST` | list / start chat sessions (sidebar threads) |
| `GET /api/v1/chat/sessions/{id}/messages` · `DELETE` | one session's history / delete it |
| `POST /api/v1/advisory` | full LangGraph advisory pipeline |
| `GET /api/v1/market/forecast` | Prophet price forecasts |
| `GET /api/v1/market/calendar` · `/{bs_month}` | harvest calendar × price forecast, joined |
| `GET /api/v1/crops/filtered/{bs_month}` | plantable crops for a BS month |
| `POST /api/v1/forecast/retrain` | refresh the Prophet cache |

## Tests

```bash
python -m pytest tests/ -q     # 114 tests: dialogue flow, intents, engines, extraction
```

## Project layout

```
api/        routes, auth                    rules/      dialogue policy, extractors, validators
engine/     crop/price/market/risk engines   rag/        embeddings, retriever, ingestion
core/       profile, credit score,           graph/      LangGraph advisory workflow
            scheduled notifications         data/       CSVs (calendar, risks, yields, prices)
db/         MongoDB models + CRUD           models/     trained model artifacts (.pkl, .keras)
tests/      pytest suite                    scripts/    one-off/maintenance scripts (run with -m)
frontend/   React + TanStack Router/Query UI
```
