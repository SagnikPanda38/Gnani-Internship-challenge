import shutil
import subprocess

import httpx
import pytest
from fastapi.testclient import TestClient

import main

client = TestClient(main.app)


def match(**overrides):
    body = {"query": "", "education_level": "undergraduate", "category": "general",
            "annual_income_inr": 200000, "state": ""}
    body.update(overrides)
    r = client.post("/api/match", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def ids(result):
    return [m["id"] for m in result["matches"]]


# ---------- catalogue / health

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_catalogue_entries_have_required_fields():
    for s in client.get("/api/schemes").json()["schemes"]:
        for key in ("id", "name", "levels", "categories", "official_url",
                    "source_url", "source_checked_on", "verification_status"):
            assert s.get(key), f"{s.get('id')} is missing {key}"


# ---------- matching

def test_general_ug_gets_csss_only():
    assert ids(match()) == ["csss"]


def test_sc_ug_gets_all_three():
    assert set(ids(match(category="sc"))) == {"csss", "sc-post-matric", "top-class-sc"}


def test_unverified_income_ceiling_does_not_exclude_scheme():
    # Catalogue ceilings are not official-verified, so they must not hard-filter results.
    result = match(category="sc", annual_income_inr=300000)
    assert "sc-post-matric" in ids(result)
    assert any("not officially verified" in w for w in result["matches"][1]["warnings"])


def test_missing_income_still_matches_with_warning():
    result = match(category="sc", annual_income_inr=None)
    assert result["count"] == 3
    for m in result["matches"]:
        assert any("income" in w.lower() for w in m["warnings"])


def test_category_other_is_handled():
    assert ids(match(category="other")) == ["csss"]


def test_no_matching_record():
    result = match(education_level="postgraduate", category="general")
    assert result["count"] == 0
    assert result["matches"] == []
    assert "Potential matches only" in result["notice"]


def test_very_high_income_does_not_use_unverified_ceiling_as_exclusion():
    assert match(category="sc", annual_income_inr=5000000)["count"] == 3


def test_zero_income_is_valid():
    assert match(annual_income_inr=0)["count"] >= 1


def test_state_adds_domicile_warning():
    m = match(category="sc", state="West Bengal")["matches"][0]
    assert any("domicile" in w.lower() for w in m["warnings"])


def test_unverified_records_are_never_called_verified():
    for m in match(category="sc")["matches"]:
        assert m["match_type"] == "potential"
        assert m["warnings"], "every non-VERIFIED record should carry a warning"


def test_query_keywords_reorder_results_english():
    result = match(category="sc", query="I got into IIT and want help")
    assert ids(result)[0] == "top-class-sc"
    assert any("iit" in r.lower() for r in result["matches"][0]["match_reasons"])


def test_query_keywords_work_in_devanagari():
    result = match(category="sc", query="मुझे फीस के लिए मदद चाहिए")
    assert ids(result)[0] == "sc-post-matric"


def test_unrelated_query_does_not_filter_anything():
    assert match(category="sc", query="hello there")["count"] == 3


def test_invalid_category_rejected():
    r = client.post("/api/match", json={"category": "nonsense"})
    assert r.status_code == 422


def test_negative_income_rejected():
    r = client.post("/api/match", json={"annual_income_inr": -5})
    assert r.status_code == 422


# ---------- transcription

def fake_wav():
    return b"RIFF....WAVEfake"


def audio_upload(content=b"abc"):
    return {"audio": ("rec.webm", content, "audio/webm")}


def test_transcribe_without_key_is_503(monkeypatch):
    monkeypatch.setattr(main, "GNANI_API_KEY", None)
    r = client.post("/api/transcribe", files=audio_upload())
    assert r.status_code == 503
    assert "Text search still works" in r.json()["detail"]


def test_transcribe_rejects_unknown_language(monkeypatch):
    monkeypatch.setattr(main, "GNANI_API_KEY", "k")
    r = client.post("/api/transcribe?language_code=xx-XX", files=audio_upload())
    assert r.status_code == 400


def test_transcribe_empty_audio(monkeypatch):
    monkeypatch.setattr(main, "GNANI_API_KEY", "k")
    r = client.post("/api/transcribe", files=audio_upload(b""))
    assert r.status_code == 400


def test_transcribe_too_large(monkeypatch):
    monkeypatch.setattr(main, "GNANI_API_KEY", "k")
    monkeypatch.setattr(main, "MAX_UPLOAD_BYTES", 10)
    r = client.post("/api/transcribe", files=audio_upload(b"x" * 11))
    assert r.status_code == 413


def patch_gnani(monkeypatch, handler):
    """Replace httpx.AsyncClient so no real network call is made."""
    real = httpx.AsyncClient
    monkeypatch.setattr(main, "GNANI_API_KEY", "test-key")
    monkeypatch.setattr(main, "to_wav", lambda _b: fake_wav())
    monkeypatch.setattr(
        main.httpx, "AsyncClient",
        lambda **kw: real(transport=httpx.MockTransport(handler), **kw),
    )


def test_transcribe_success_sends_documented_fields(monkeypatch):
    seen = {}

    def handler(request: httpx.Request):
        seen["key"] = request.headers.get("x-api-key-id")
        seen["body"] = request.content
        return httpx.Response(200, json={"success": True, "transcript": " मुझे स्कॉलरशिप चाहिए ", "request_id": "r1"})

    patch_gnani(monkeypatch, handler)
    r = client.post("/api/transcribe?language_code=hi-IN", files=audio_upload())
    assert r.status_code == 200
    assert r.json()["transcript"] == "मुझे स्कॉलरशिप चाहिए"
    assert r.json()["empty"] is False
    assert seen["key"] == "test-key"
    assert b'name="audio_file"' in seen["body"]
    assert b'name="language_code"' in seen["body"]
    assert b"preferred_language" not in seen["body"]


def test_transcribe_empty_transcript_is_not_an_error(monkeypatch):
    patch_gnani(monkeypatch, lambda req: httpx.Response(200, json={"success": True, "transcript": ""}))
    r = client.post("/api/transcribe", files=audio_upload())
    assert r.status_code == 200
    assert r.json()["empty"] is True


@pytest.mark.parametrize("status,expected", [(401, 502), (403, 502), (429, 429), (500, 502)])
def test_transcribe_upstream_errors(monkeypatch, status, expected):
    patch_gnani(monkeypatch, lambda req: httpx.Response(status, json={"detail": {"error_code": "X", "message": "nope"}}))
    r = client.post("/api/transcribe", files=audio_upload())
    assert r.status_code == expected
    assert "test-key" not in r.text


def test_transcribe_envelope_error_message_is_surfaced(monkeypatch):
    body = {"success": False, "error": {"type": "MAX_AUDIO_DURATION_EXCEEDED", "message": "Audio duration exceeds maximum allowed duration of 30 seconds"}}
    patch_gnani(monkeypatch, lambda req: httpx.Response(400, json=body))
    r = client.post("/api/transcribe", files=audio_upload())
    assert r.status_code == 502
    assert "30 seconds" in r.json()["detail"]


def test_transcribe_missing_ffmpeg(monkeypatch):
    monkeypatch.setattr(main, "GNANI_API_KEY", "k")

    def boom(_b):
        raise FileNotFoundError("ffmpeg")

    monkeypatch.setattr(main, "to_wav", boom)
    r = client.post("/api/transcribe", files=audio_upload())
    assert r.status_code == 503
    assert "ffmpeg" in r.json()["detail"]


def test_transcribe_bad_audio(monkeypatch):
    monkeypatch.setattr(main, "GNANI_API_KEY", "k")

    def bad(_b):
        raise RuntimeError("ffmpeg failed")

    monkeypatch.setattr(main, "to_wav", bad)
    r = client.post("/api/transcribe", files=audio_upload())
    assert r.status_code == 400


# ---------- real ffmpeg conversion (skipped if ffmpeg isn't installed)

@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_to_wav_converts_and_caps_length(tmp_path):
    webm = tmp_path / "tone.webm"
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=40",
         "-c:a", "libopus", str(webm)],
        check=True,
    )
    wav = main.to_wav(webm.read_bytes())
    assert wav[:4] == b"RIFF" and wav[8:12] == b"WAVE"
    # 16 kHz, mono, 16-bit => 32,000 bytes per second; 40 s input must be cut to ~30 s
    seconds = (len(wav) - 44) / 32000
    assert 29 <= seconds <= 31


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_to_wav_rejects_garbage():
    with pytest.raises(RuntimeError):
        main.to_wav(b"this is not audio")
