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

```powershell
cd backend
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `backend/.env`:

```env
GNANI_API_KEY=your_real_key_here
GNANI_STT_URL=https://api.vachana.ai/stt/v3
```

Start the API:

```powershell
uvicorn main:app --reload
```

API docs: http://127.0.0.1:8000/docs

## Run frontend (second terminal)

```powershell
cd frontend
npm install
npm run dev
```

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

## Before submission checklist
- [ ] Confirm Gnani API endpoint and request schema from your own console.
- [ ] Test voice transcription with Hindi and Hinglish recordings.
- [ ] Verify scheme names, current availability, criteria, deadlines, and official URLs.
- [ ] Add `source_checked_on` and source URL for each verified catalogue entry.
- [ ] Test edge cases: missing income, category not applicable, no matching record.
- [ ] Never expose `.env` or API keys in GitHub, screenshots, or demo video.
- [ ] Make clear that the prototype provides guidance, not an official eligibility decision.
