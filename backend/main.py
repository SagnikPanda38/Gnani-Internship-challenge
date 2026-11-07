import json
import os
from pathlib import Path
from typing import Literal, Optional

import httpx
import subprocess
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
CATALOGUE_PATH = BASE_DIR / "data" / "schemes.json"

app = FastAPI(
    title="Scheme Sathi",
    version="1.0.0",
    description="A voice-first scholarship discovery MVP. Results are guidance, not official eligibility decisions.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

GNANI_API_KEY = os.getenv("GNANI_API_KEY")
GNANI_STT_URL = os.getenv("GNANI_STT_URL", "https://api.vachana.ai/stt/v3")


class StudentProfile(BaseModel):
    query: str = Field(default="", max_length=1500)
    education_level: Literal["undergraduate", "postgraduate", "diploma"] = "undergraduate"
    category: Literal["general", "obc", "sc", "st", "ews", "other"] = "general"
    annual_income_inr: Optional[int] = Field(default=None, ge=0, le=100000000)
    state: str = Field(default="", max_length=80)

def to_wav(audio_bytes: bytes) -> bytes:
    """Convert any browser-recorded audio (webm/mp4/ogg) to 16kHz mono WAV."""
    proc = subprocess.run(
        ["ffmpeg", "-i", "pipe:0", "-ar", "16000", "-ac", "1",
         "-f", "wav", "pipe:1", "-loglevel", "error"],
        input=audio_bytes,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {proc.stderr.decode()}")
    return proc.stdout

def load_schemes():
    with CATALOGUE_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


@app.get("/")
async def root():
    return {"service": "Scheme Sathi", "status": "running", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/schemes")
async def list_schemes():
    """Return the small catalogue for the frontend / project demo."""
    return {"count": len(load_schemes()), "schemes": load_schemes()}


@app.post("/api/match")
async def match_schemes(profile: StudentProfile):
    """Transparent rule-based potential matching; never a legal eligibility decision."""
    matches = []
    review = []
    for scheme in load_schemes():
        reasons = []
        warnings = []

        if profile.education_level not in scheme["levels"]:
            continue
        if profile.category not in scheme["categories"]:
            continue

        reasons.append("Education level and category match the catalogue filters.")

        ceiling = scheme.get("max_annual_income_inr")
        if profile.annual_income_inr is None:
            warnings.append("Add annual family income to apply the catalogue's income filter.")
        elif ceiling is not None and profile.annual_income_inr > ceiling:
            continue
        elif ceiling is not None:
            reasons.append("Reported family income is within the demo catalogue threshold.")

        if profile.state.strip():
            warnings.append("Check domicile / state-specific rules for your state.")

        if scheme.get("verification_status") != "VERIFIED":
            warnings.append("Current availability and detailed rules have not been verified by this prototype.")

        matches.append({
            **scheme,
            "match_reasons": reasons,
            "warnings": warnings,
            "match_type": "potential"
        })

    return {
        "success": True,
        "count": len(matches),
        "matches": matches,
        "notice": "Potential matches only. This prototype does not determine official eligibility or guarantee an award. Verify current rules and application dates on the official portal."
    }


@app.post("/api/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    language_code: str = "hi-IN",
):
    if not GNANI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Voice service is not configured. Add GNANI_API_KEY to backend/.env. Text search still works.",
        )

    audio_data = await audio.read()
    if not audio_data:
        raise HTTPException(status_code=400, detail="The audio recording is empty.")
    if len(audio_data) > 15 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio is too large. Keep recordings under 15 MB.")

    try:
        wav_data = to_wav(audio_data)
    except (RuntimeError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail="Could not convert the audio recording to WAV.") from exc

    files = {
        "audio_file": ("scheme-sathi-recording.wav", wav_data, "audio/wav")
    }
    form_data = {
        "language_code": language_code,
        "preferred_language": language_code,
        "format": "transcribe",
        "itn_native_numerals": "true",
    }
    headers = {"X-API-Key-ID": GNANI_API_KEY}

    try:
        async with httpx.AsyncClient(timeout=75.0) as client:
            response = await client.post(
                GNANI_STT_URL,
                headers=headers,
                files=files,
                data=form_data,
            )
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Gnani STT returned HTTP {exc.response.status_code}: {exc.response.text[:500]}",
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not connect to Gnani STT ({type(exc).__name__}).",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Gnani returned a non-JSON response.") from exc

    transcript = payload.get("transcript")
    if not transcript and isinstance(payload.get("data"), dict):
        transcript = payload["data"].get("transcript")
    if payload.get("success") is False:
        raise HTTPException(status_code=502, detail=payload.get("message", "Gnani transcription failed."))
    if transcript is None:
        raise HTTPException(status_code=502, detail="Transcript not found in Gnani response. Check the response schema in your console.")

    return {"success": True, "transcript": transcript, "request_id": payload.get("request_id")}
