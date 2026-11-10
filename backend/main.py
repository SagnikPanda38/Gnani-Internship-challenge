import asyncio
import json
import os
import shutil
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
CATALOGUE_PATH = BASE_DIR / "data" / "schemes.json"

# Gnani's REST endpoint only takes clips up to 30 seconds.
MAX_AUDIO_SECONDS = 30
MAX_UPLOAD_BYTES = 15 * 1024 * 1024
SUPPORTED_LANGUAGES = {"hi-IN", "en-IN"}

app = FastAPI(
    title="Scheme Sathi",
    version="1.1.0",
    description="A voice-first scholarship discovery MVP. Results are guidance, not official eligibility decisions.",
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
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


# ---------------------------------------------------------------- catalogue

@lru_cache(maxsize=1)
def _read_catalogue():
    with CATALOGUE_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_schemes():
    """Catalogue is read once per process. Restart uvicorn after editing schemes.json
    (--reload does this for you)."""
    return _read_catalogue()


def find_query_hits(query: str, scheme: dict) -> list[str]:
    """Very simple keyword check so the typed / spoken request actually does something.
    Works for English, romanised Hindi and Devanagari, since the keywords in the
    catalogue are written in all three."""
    text = query.casefold()
    if not text.strip():
        return []
    return [kw for kw in scheme.get("keywords", []) if kw.casefold() in text]


def source_warning(scheme: dict) -> Optional[str]:
    status = scheme.get("verification_status")
    checked = scheme.get("source_checked_on")
    if status == "VERIFIED":
        return None
    if status == "CROSS_CHECKED" and checked:
        return (
            f"Income ceiling was cross-checked on {checked} against parliamentary / "
            "government references, but the latest official guidelines still need to be confirmed."
        )
    return "Current availability and detailed rules have not been verified by this prototype."


# ---------------------------------------------------------------- audio

def to_wav(audio_bytes: bytes) -> bytes:
    """Convert browser audio (webm / mp4 / ogg) to 16 kHz mono WAV, capped at 30 s.

    We go through temp files on both sides because ffmpeg writes a WAV header with an
    unknown length when it outputs to a pipe, and some servers dislike that.
    """
    if shutil.which("ffmpeg") is None:
        raise FileNotFoundError("ffmpeg")

    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "in.bin"
        dst = Path(tmp) / "out.wav"
        src.write_bytes(audio_bytes)
        proc = subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(src),
                "-t", str(MAX_AUDIO_SECONDS),
                "-ar", "16000", "-ac", "1",
                str(dst),
            ],
            capture_output=True,
            timeout=30,
        )
        if proc.returncode != 0 or not dst.exists():
            raise RuntimeError(f"ffmpeg failed: {proc.stderr.decode(errors='replace')}")
        return dst.read_bytes()


def gnani_error_message(response: httpx.Response) -> str:
    """Pull a readable message out of Gnani's two error shapes:
    {"success": false, "error": {"type", "message"}} and {"detail": {"error_code", "message"}}."""
    try:
        body = response.json()
    except ValueError:
        return response.text[:300]
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict) and err.get("message"):
            return str(err["message"])[:300]
        detail = body.get("detail")
        if isinstance(detail, dict) and detail.get("message"):
            return str(detail["message"])[:300]
        if isinstance(detail, list) and detail:
            return str(detail[0].get("msg", detail[0]))[:300]
        if body.get("message"):
            return str(body["message"])[:300]
    return response.text[:300]


# ---------------------------------------------------------------- routes

@app.get("/")
async def root():
    return {"service": "Scheme Sathi", "status": "running", "version": app.version}


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "voice_configured": bool(GNANI_API_KEY),
        "ffmpeg_available": shutil.which("ffmpeg") is not None,
        "schemes_loaded": len(load_schemes()),
    }


@app.get("/api/schemes")
async def list_schemes():
    """Return the small catalogue for the frontend / project demo."""
    schemes = load_schemes()
    return {"count": len(schemes), "schemes": schemes}


@app.post("/api/match")

async def match_schemes(profile: StudentProfile):
    """Transparent rule-based potential matching; never a legal eligibility decision."""
    matches = []
    search_warning = None

    query_lower = (profile.query or "").lower()

    school_keywords = [
        "school",
        "school student",
        "class 10",
        "class 12",
        "10th",
        "12th",
    ]

    college_keywords = [
        "college",
        "undergraduate",
        "university",
        "degree",
    ]

    if any(word in query_lower for word in school_keywords):
        if profile.education_level != "school":
            search_warning = (
                "Your search mentions school-level scholarships, "
                "but your selected education level is different. "
                "Please check your profile details."
            )
    for scheme in load_schemes():
        reasons = []
        warnings = []

        if profile.education_level not in scheme["levels"]:
            continue
        if profile.category not in scheme["categories"]:
            continue

        reasons.append("Education level and category match the catalogue filters.")

        ceiling = scheme.get("max_annual_income_inr")
        income_rule_verified = (
            scheme.get("verification_status") == "VERIFIED"
            and scheme.get("income_rule_verified") is True
        )
        if profile.annual_income_inr is None:
            warnings.append("Add annual family income and compare it with the latest official income rules.")
        elif ceiling is not None and income_rule_verified:
            if profile.annual_income_inr > ceiling:
                continue
            reasons.append("Reported family income is within the officially verified catalogue threshold.")
        elif ceiling is not None:
            warnings.append(
                f"The catalogue lists an income reference of ₹{ceiling:,}, "
                "but it is not officially verified and was not used to exclude this scheme."
            )

        hits = find_query_hits(profile.query, scheme)
        if hits:
            reasons.append("Your request mentions: " + ", ".join(hits[:4]) + ".")

        if profile.state.strip():
            warnings.append("Check domicile / state-specific rules for your state.")

        extra = source_warning(scheme)
        if extra:
            warnings.append(extra)

        matches.append({
            **scheme,
            "match_reasons": reasons,
            "warnings": warnings,
            "match_type": "potential",
            "query_hits": hits,
        })

    # Schemes the user's own words point to go first; otherwise keep catalogue order.
    matches.sort(key=lambda m: -len(m["query_hits"]))

    return {
        "success": True,
        "count": len(matches),
        "matches": matches,
        "search_warning": search_warning,
        "notice": "Potential matches only. This prototype does not determine official eligibility or guarantee an award. Verify current rules and application dates on the official portal.",
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
    if language_code not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported language_code '{language_code}'. Use one of: {', '.join(sorted(SUPPORTED_LANGUAGES))}.",
        )

    audio_data = await audio.read(MAX_UPLOAD_BYTES + 1)
    if not audio_data:
        raise HTTPException(status_code=400, detail="The audio recording is empty.")
    if len(audio_data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Audio is too large. Keep recordings under 15 MB.")

    try:
        # ffmpeg is blocking, so keep it off the event loop
        wav_data = await asyncio.to_thread(to_wav, audio_data)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail="ffmpeg is not installed on the server, so recordings can't be converted. Install ffmpeg or type your request instead.",
        ) from exc
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        raise HTTPException(status_code=400, detail="Could not convert the audio recording to WAV.") from exc

    files = {"audio_file": ("scheme-sathi-recording.wav", wav_data, "audio/wav")}
    form_data = {
        "language_code": language_code,
        # 'transcribe' turns spoken numbers into digits ("do lakh" -> 2,00,000)
        "format": "transcribe",
    }
    headers = {"X-API-Key-ID": GNANI_API_KEY}

    try:
        async with httpx.AsyncClient(timeout=75.0) as client:
            response = await client.post(GNANI_STT_URL, headers=headers, files=files, data=form_data)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not connect to Gnani STT ({type(exc).__name__}).",
        ) from exc

    if response.status_code >= 400:
        message = gnani_error_message(response)
        if response.status_code in (401, 403):
            raise HTTPException(status_code=502, detail="Gnani rejected the API key. Check GNANI_API_KEY in backend/.env.")
        if response.status_code == 429:
            raise HTTPException(status_code=429, detail="Voice service is busy. Wait a few seconds and try again.")
        raise HTTPException(status_code=502, detail=f"Gnani STT returned HTTP {response.status_code}: {message}")

    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Gnani returned a non-JSON response.") from exc

    if payload.get("success") is False:
        raise HTTPException(status_code=502, detail=gnani_error_message(response))

    transcript = payload.get("transcript")
    if transcript is None and isinstance(payload.get("data"), dict):
        transcript = payload["data"].get("transcript")
    if transcript is None:
        raise HTTPException(status_code=502, detail="Transcript not found in Gnani response. Check the response schema in your console.")

    # Gnani returns "" (not an error) when it hears no speech.
    return {
        "success": True,
        "transcript": transcript.strip(),
        "empty": not transcript.strip(),
        "request_id": payload.get("request_id"),
    }
