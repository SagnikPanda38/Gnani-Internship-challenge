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



## Requirements

- Python 3.10+
- Node.js 20+
- **ffmpeg** on your PATH. Browsers record WebM or MP4, so the backend converts to 16 kHz mono WAV before sending to Gnani. Without it, text search still works but voice returns an error saying ffmpeg is missing.
  - Windows: `winget install Gyan.FFmpeg` (then open a new terminal)
  - macOS: `brew install ffmpeg`
  - Ubuntu/Debian: `sudo apt install ffmpeg`
- A Gnani API key (only needed for voice)


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


## Team division
- Backend teammate: `backend/main.py`, matching logic, catalogue verification, API tests.
- Frontend teammate: `frontend/src/App.jsx`, styling, browser testing, demo flow.
- Both: verify every scheme record against official guidelines and test Hindi/Hinglish transcripts.

