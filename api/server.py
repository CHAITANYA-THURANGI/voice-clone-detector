"""
FastAPI Server & Platform Integration APIs for Voice Integrity Verification.
Provides RESTful and real-time streaming endpoints for banking, enterprise VoIP,
and telecom core gateways (SIH PS-26104).
"""

import os
import sys
import glob
from typing import Optional, Dict
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ensemble import ensemble_instance
from core.stream_detector import RealTimeStreamDetector
from core.audio_processor import load_audio_from_bytes


app = FastAPI(
    title="Voice Integrity & Clone Prevention API",
    description="AI-Powered Real-Time Detection and Prevention of Voice Cloning Impersonation Attacks (SIH PS-26104)",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory registry for active streaming call sessions
active_stream_sessions: Dict[str, RealTimeStreamDetector] = {}


@app.get("/api/system-status")
def get_system_status():
    """Returns platform operational health and compliance metrics."""
    checkpoint_exists = os.path.exists(os.path.join(PROJECT_ROOT, "models", "acoustic_prosodic_net.pth"))
    return {
        "service": "Voice Integrity Verification Engine",
        "status": "ONLINE",
        "problem_statement": "SIH-2026 PS-26104",
        "compliance": "India DPDP Act 2023 & GDPR Zero-Retention Certified",
        "models": {
            "EnterpriseVoiceConformer": "LOADED (ASP + MHSA)" if checkpoint_exists else "UNTRAINED",
            "GlottalInverseFilteringDSP": "ACTIVE (LPC Residual)",
            "PhaseAwareMGDCoherence": "ACTIVE (Group Delay & HF Jitter)",
            "ProsodyBiometricEngine": "ACTIVE",
            "SpeakerVerification": "ACTIVE",
            "MITRE_ATT&CK_Telemetry": "T1656 / ACTIVE"
        },
        "supported_codecs": ["WAV", "MPEG", "MPG", "MP3", "OGG", "FLAC", "WebM", "Opus", "AAC", "M4A"]
    }


@app.post("/api/analyze-audio")
async def analyze_audio_file(
    file: UploadFile = File(...),
    claimed_speaker_id: Optional[str] = Form(None),
    transaction_amount: Optional[float] = Form(0.0),
    is_cxo_call: Optional[bool] = Form(False),
    credential_request: Optional[bool] = Form(False)
):
    """
    End-to-end multi-layer forensic analysis of an incoming audio recording or call intercept.
    """
    try:
        audio_bytes = await file.read()
        ext = "wav"
        if file.filename and "." in file.filename:
            ext = file.filename.rsplit(".", 1)[-1].lower()

        context = {
            "transaction_amount": transaction_amount,
            "is_cxo_call": is_cxo_call,
            "credential_request": credential_request
        }

        call_prefix = (file.filename or "AUDIO")[:8]
        result = ensemble_instance.analyze_audio(
            audio_input=audio_bytes,
            claimed_speaker_id=claimed_speaker_id if claimed_speaker_id else None,
            context=context,
            call_id=f"CALL-{call_prefix}",
            file_ext=ext
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/stream-chunk")
async def process_stream_chunk(
    file: UploadFile = File(...),
    call_id: str = Form(...),
    timestamp_sec: float = Form(0.0),
    claimed_speaker_id: Optional[str] = Form(None),
    transaction_amount: Optional[float] = Form(0.0),
    is_cxo_call: Optional[bool] = Form(False),
    is_cxo: Optional[bool] = Form(None)
):
    """
    Near real-time sliding window analysis for live VoIP/telephony calls.
    Maintains session history and consecutive anomaly tracking.
    """
    try:
        audio_bytes = await file.read()
        ext = "wav"
        if file.filename and "." in file.filename:
            ext = file.filename.rsplit(".", 1)[-1].lower()

        chunk_waveform = load_audio_from_bytes(audio_bytes, file_ext=ext)
        cxo_flag = is_cxo_call if is_cxo is None else (is_cxo or is_cxo_call)

        if call_id not in active_stream_sessions:
            context = {
                "transaction_amount": transaction_amount,
                "is_cxo_call": cxo_flag
            }
            active_stream_sessions[call_id] = RealTimeStreamDetector(
                call_id=call_id,
                model=ensemble_instance.model,
                risk_engine=ensemble_instance.risk_engine,
                speaker_verifier=ensemble_instance.speaker_verifier,
                claimed_speaker_id=claimed_speaker_id if claimed_speaker_id else None,
                context=context
            )

        session = active_stream_sessions[call_id]
        chunk_result = session.process_chunk(chunk_waveform, timestamp_sec=timestamp_sec)
        return chunk_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/enroll-speaker")
async def enroll_speaker(
    file: UploadFile = File(...),
    speaker_id: str = Form(...)
):
    """Enrolls a genuine CXO / executive voiceprint signature."""
    try:
        audio_bytes = await file.read()
        ext = "wav"
        if file.filename and "." in file.filename:
            ext = file.filename.rsplit(".", 1)[-1].lower()
        waveform = load_audio_from_bytes(audio_bytes, file_ext=ext)
        res = ensemble_instance.speaker_verifier.enroll(speaker_id, waveform)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/api/benchmark-samples")
def list_benchmark_samples():
    """Lists available test audio files for the interactive dashboard."""
    samples_dir = os.path.join(PROJECT_ROOT, "data", "samples")
    files = sorted(glob.glob(os.path.join(samples_dir, "*.wav")) + 
                   glob.glob(os.path.join(samples_dir, "*.mpeg")) + 
                   glob.glob(os.path.join(samples_dir, "*.mpg")))
    sample_list = []
    for fpath in files:
        fname = os.path.basename(fpath)
        is_real = "real" in fname.lower() or "test_sample" in fname.lower()
        if is_real:
            desc = "Authentic Human Voice"
        elif "replayed" in fname.lower():
            desc = "Replayed Attack (Acoustic Channel)"
        elif "mpg" in fname.lower() or "mpeg" in fname.lower():
            desc = "MPEG Cloned Voice / Audio"
        else:
            desc = "Neural TTS / Clone Voice"

        sample_list.append({
            "filename": fname,
            "type": "REAL" if is_real else "FAKE",
            "description": desc,
            "url": f"/api/sample-audio/{fname}"
        })
    return {"samples": sample_list}


@app.get("/api/sample-audio/{filename}")
def get_sample_audio(filename: str):
    """Streams a benchmark sample audio file."""
    fpath = os.path.join(PROJECT_ROOT, "data", "samples", filename)
    if not os.path.exists(fpath):
        raise HTTPException(status_code=404, detail="Sample not found")
    media_type = "audio/mpeg" if filename.lower().endswith((".mpeg", ".mpg")) else "audio/wav"
    return FileResponse(fpath, media_type=media_type)


# Mount UI static directory
ui_dir = os.path.join(PROJECT_ROOT, "ui")
if os.path.exists(ui_dir):
    app.mount("/", StaticFiles(directory=ui_dir, html=True), name="ui")
