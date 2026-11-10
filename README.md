<<<<<<< HEAD
# Scheme Sathi

A small voice-first scholarship finder for Indian students, built for the Gnani internship challenge. You tell it a bit about yourself (by speaking or typing), and it shows scholarships from a short list that might fit, with the reason each one came up and a link to the official portal.

We kept the scope small on purpose. No login, no database, no LLM, and it never submits anything on your behalf.

## What it does

- Takes a request in Hindi, Hinglish or English, typed or spoken.
- Records from the browser mic and sends the audio to our backend, which sends it to Gnani Prisma STT. The API key stays on the backend.
- Asks for education level, category and annual family income (state is optional).
- Matches education level and category against a small JSON file (`backend/data/schemes.json`) using plain rules, so you can always see why something showed up. Income figures that have not been confirmed in current official guidelines are displayed as references and never used to silently exclude a student.
- If your typed or spoken request mentions something specific (like "IIT", "fees" or "merit"), schemes that relate to it are moved to the top and the card says so.
- Every result is labelled "potential match" and shows what to double check before applying.

## Read this before demoing the data

The catalogue is a starter list of three schemes, not a live or complete list of open scholarships. Income limits, deadlines and rules change. Here is where each entry stands right now (checked 10 Nov 2026):

| Scheme | Status | Outstanding official checks |
|---|---|---|
| Post-Matric Scholarship (SC) | Not officially verified | Confirm current central/state guidelines, income ceiling, domicile rules, course coverage and application window. |
| Top Class Education (SC) | Not officially verified | Confirm current income ceiling, notified-institution list, eligible courses, seat limits and application window. |
| Central Sector Scholarship (CSSS) | Not officially verified | Confirm the current official income rule, Class XII percentile requirement, eligible courses and application window. |

The source notes are research leads, not proof of current eligibility. All three income ceilings are marked `income_rule_verified: false`; the matching engine therefore does not use them to exclude a student. Nothing is marked `VERIFIED` until the current official guideline has been read and the exact criteria, source URL and review date have been recorded. Please don't present a result as confirmed eligibility.

## Requirements

- Python 3.10+
- Node.js 20+
- **ffmpeg** on your PATH. Browsers record WebM or MP4, so the backend converts to 16 kHz mono WAV before sending to Gnani. Without it, text search still works but voice returns an error saying ffmpeg is missing.
  - Windows: `winget install Gyan.FFmpeg` (then open a new terminal)
  - macOS: `brew install ffmpeg`
  - Ubuntu/Debian: `sudo apt install ffmpeg`
- A Gnani API key (only needed for voice)

## Running the backend (Windows PowerShell)
=======
# Scheme Sathi — Scholarship MVP

A deliberately small, voice-first scholarship discovery prototype for Indian students.

## MVP features
- Hindi / Hinglish / English text query.
- Browser microphone recording.
- Backend-only Gnani Prisma STT integration.
- Short student profile (education level, category, annual family income).
- Transparent, deterministic matching against a small editable JSON catalogue.
- Results show why a record matched, what to verify, and an official portal link.
- No login, no LLM dependency, no training, no application submission.

## Important data disclaimer
The included catalogue is a **demo starter catalogue**, not an authoritative or live list of open scholarships. Scholarship rules, income ceilings, deadlines, category conditions, and scheme availability can change. The UI labels results as potential matches and tells users to verify current details on the official portal. Before a public judging demo, the team must verify each included record from the relevant official scheme guidelines and update `backend/data/schemes.json` with the source URL and date checked. Do not present a potential match as confirmed eligibility or guaranteed award.

## Requirements
- Python 3.10+
- Node.js 20+
- Gnani API key (only required for voice transcription)

## Run backend (Windows PowerShell)
>>>>>>> 206e645de10ec6b529e384e4d67daaf6482d9345

```powershell
cd backend
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

<<<<<<< HEAD
Put your key in `backend/.env`:
=======
Edit `backend/.env`:
>>>>>>> 206e645de10ec6b529e384e4d67daaf6482d9345

```env
GNANI_API_KEY=your_real_key_here
GNANI_STT_URL=https://api.vachana.ai/stt/v3
```

<<<<<<< HEAD
Then start it:
=======
Start the API:
>>>>>>> 206e645de10ec6b529e384e4d67daaf6482d9345

```powershell
uvicorn main:app --reload
```

<<<<<<< HEAD
API docs are at http://127.0.0.1:8000/docs. The `/health` endpoint also tells you whether the key and ffmpeg were picked up, which saves a lot of guessing.

## Running the frontend (second terminal)
=======
API docs: http://127.0.0.1:8000/docs

## Run frontend (second terminal)
>>>>>>> 206e645de10ec6b529e384e4d67daaf6482d9345

```powershell
cd frontend
npm install
npm run dev
```

<<<<<<< HEAD
Open http://localhost:5173. If the backend is on a different address, copy `frontend/.env.example` to `frontend/.env` and change `VITE_API_BASE_URL`. If the frontend is on a different origin, set `ALLOWED_ORIGINS` in `backend/.env`.

## Tests

```powershell
cd backend
pip install -r requirements-dev.txt
pytest
```

These cover the matching rules and the edge cases from our checklist (missing income, category "other", no matching scheme, income just over a limit, Devanagari keywords), plus the transcribe endpoint with Gnani mocked out (success, empty speech, 401/403/429/500, missing ffmpeg, bad audio). Two tests run real ffmpeg and are skipped automatically if it isn't installed. None of the tests call the real Gnani API.

## Trying it by hand

1. Open http://127.0.0.1:8000/health.
2. In the app, pick education level, category and income.
3. Type something like "I am an undergraduate student looking for a scholarship".
4. Hit **Find scholarships**.
5. For voice, allow the mic, record up to 30 seconds, and stop. The text lands in the box and you can edit it before searching.

Also worth trying: clear the income field, pick "Other" as the category, or pick postgraduate + general to see the "nothing found" state.

## How we call Gnani

`POST /api/transcribe` converts the recording to WAV and forwards it to the STT endpoint. We checked the request against Gnani's REST docs on 10 Nov 2026:

- Header: `X-API-Key-ID`
- File field: `audio_file`
- Form fields: `language_code` (`hi-IN` or `en-IN`) and `format=transcribe`, which turns spoken numbers into digits
- Clips can be at most **30 seconds**. The UI counts down and stops automatically, and the backend trims anything longer as a safety net.
- Gnani returns an empty transcript (not an error) when it hears no speech. The UI shows a friendly message for that.
- The account may only allow one request at a time, so the record button is disabled while we wait for a transcript.

Choose "English / Hinglish" in the language dropdown if you speak mixed Hindi and English. Gnani writes that in Latin script, and Hindi mode writes Devanagari. The matching keywords cover both.

An earlier version of the backend also sent a `preferred_language` field. It isn't in Gnani's docs, so we removed it.

## Who did what

- Backend: `backend/main.py`, the matching rules, catalogue checks, API tests.
- Frontend: `frontend/src/App.jsx`, styling, browser testing, demo flow.
- Both of us: verifying scheme records against official guidelines and trying real Hindi / Hinglish recordings.

## Ideas if we have time

- More schemes (ST, OBC, EWS, minority, girls-only), each one verified before it goes in
- Real state-wise rules instead of just a "check your state" note
- Reading results aloud with Gnani TTS
=======
Open http://localhost:5173.

## Test
1. Check http://127.0.0.1:8000/health.
2. In the UI, fill in education level, category, and annual family income.
3. Type a request such as: "I am an undergraduate student looking for a scholarship".
4. Click **Find scholarships**.
5. For voice, allow microphone access, record a short Hindi/Hinglish query, and stop recording. The audio is sent to the backend and then to Gnani STT.

If voice transcription fails, text search remains fully usable.

## Gnani API adapter
`POST /api/transcribe` forwards multipart audio to the configured Gnani endpoint. The adapter uses:
- Header: `X-API-Key-ID`
- File field: `audio_file`
- Form fields: `language_code`, `preferred_language`, `format`, `itn_native_numerals`

Confirm the exact URL, authentication header, form fields, and supported audio MIME types against the API example in your Gnani console. The browser's MediaRecorder commonly emits WebM/Opus; if your account endpoint does not accept it, transcode to a supported format or use the console's supported upload format. Do not put the API key in frontend code.

## Team division
- Backend teammate: `backend/main.py`, matching logic, catalogue verification, API tests.
- Frontend teammate: `frontend/src/App.jsx`, styling, browser testing, demo flow.
- Both: verify every scheme record against official guidelines and test Hindi/Hinglish transcripts.

