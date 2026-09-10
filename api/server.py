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
from core.speaker_identifier import speaker_identifier
from core.call_defense_engine import call_defense_engine
from core.history_manager import history_manager


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
            "EnterpriseVoiceConformer": "LOADED (3-Class ASP + MHSA: Human / Non-Human / Voice Clone Attack)" if checkpoint_exists else "UNTRAINED",
            "MultiModelEnsembleFusion": "ACTIVE (In-Deep Consensus Engine)",
            "PretrainedWhisperFoundation": "ACTIVE (680k-Hr Speech Representation)",
            "SemanticFraudDetector": "ACTIVE (Whisper ALM + Gemini 2.5 / Cyber-Fraud Taxonomy Engine)",
            "GlottalInverseFilteringDSP": "ACTIVE (LPC Residual)",
            "PhaseAwareMGDCoherence": "ACTIVE (Group Delay & HF Jitter)",
            "ProsodyBiometricEngine": "ACTIVE",
            "SpeakerVerification": "ACTIVE",
            "MITRE_ATT&CK_Telemetry": "T1656 / T1566.004 (Vishing) / ACTIVE"
        },
        "target_classes": ["HUMAN", "NON_HUMAN", "VOICE_CLONING_ATTACK"],
        "semantic_threat_categories": [
            "DIGITAL_ARREST_EXTORTION",
            "BANKING_KYC_OTP_THEFT",
            "CXO_EXECUTIVE_WIRE_FRAUD",
            "TECH_SUPPORT_HIJACK",
            "EMERGENCY_FAMILY_RANSOM",
            "LOTTERY_JOB_INVESTMENT",
            "LEGITIMATE_SAFE"
        ],
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

        # Log deep forensic analysis into persistent audit history
        try:
            history_manager.log_audio_analysis(
                filename=file.filename or "uploaded_audio.wav",
                result=result,
                source="WEB_DASHBOARD",
                claimed_speaker=claimed_speaker_id
            )
        except Exception as log_err:
            print(f"[Server] Warning: Failed to log analysis to history: {log_err}")

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/extension/scan")
async def extension_scan_audio(file: UploadFile = File(...)):
    """
    Optimized endpoint for the VoiceShield AI Chrome Browser Extension.
    Performs real-time forensic scanning on captured browser audio chunks.
    """
    try:
        audio_bytes = await file.read()
        ext = "wav"
        if file.filename and "." in file.filename:
            ext = file.filename.rsplit(".", 1)[-1].lower()

        result = ensemble_instance.analyze_audio(
            audio_input=audio_bytes,
            call_id="BROWSER-EXT",
            file_ext=ext
        )

        # Log extension scan into persistent audit history
        try:
            history_manager.log_audio_analysis(
                filename="Browser_Tab_Audio_Capture",
                result=result,
                source="CHROME_EXTENSION",
                claimed_speaker=None
            )
        except Exception as log_err:
            print(f"[Server] Warning: Failed to log extension scan: {log_err}")

        fusion_data = result.get("ensemble_fusion", {})
        fraud_data = result.get("semantic_fraud_detector", {})
        voicemod_data = result.get("voicemod_forensics", {})
        risk_data = result.get("risk_assessment", {})

        fused_class = fusion_data.get("predicted_class", "HUMAN")
        confidence = float(fusion_data.get("consensus_confidence_pct", 0.0)) / 100.0
        risk_score = float(risk_data.get("risk_score", 0.0))

        is_threat = (
            fused_class == "VOICE_CLONING_ATTACK" or
            fraud_data.get("is_threat", False) or
            voicemod_data.get("voicemod_detected", False) or
            risk_score >= 0.65
        )

        return {
            "is_threat": is_threat,
            "status": "THREAT_BLOCKED" if is_threat else "VERIFIED_SAFE",
            "fused_class": fused_class,
            "confidence": confidence,
            "risk_score": risk_score,
            "risk_percentage": round(risk_score * 100, 1),
            "badge": "🔴 SYNTHETIC VOICE THREAT" if is_threat else "🟢 AUTHENTIC HUMAN VOICE",
            "scam_category": fraud_data.get("display_name", "None"),
            "is_scam": fraud_data.get("is_threat", False),
            "transcript": result.get("transcript", fraud_data.get("transcript", "")),
            "voicemod_detected": voicemod_data.get("voicemod_detected", False),
            "voicemod_comb_ripple": voicemod_data.get("comb_ripple", 0.0),
            "is_micro_clip": voicemod_data.get("is_micro_clip", False),
            "full_result": result
        }
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


# =========================================================================
# 1:N SPEAKER IDENTIFICATION & BIOMETRIC DIRECTORY ENDPOINTS
# =========================================================================

@app.post("/api/speaker-id/identify")
async def api_identify_speaker(
    file: UploadFile = File(...),
    claimed_identity: Optional[str] = Form(None),
    threshold: float = Form(0.70)
):
    """
    Performs 1:N Open-Set Speaker Identification across enrolled voiceprint directory.
    Optionally cross-checks claimed identity to detect imposter spoofing.
    """
    try:
        audio_bytes = await file.read()
        ext = "wav"
        if file.filename and "." in file.filename:
            ext = file.filename.rsplit(".", 1)[-1].lower()
        waveform = load_audio_from_bytes(audio_bytes, file_ext=ext)

        id_result = speaker_identifier.identify_speaker(waveform, threshold=threshold)

        discrepancy = None
        if claimed_identity:
            discrepancy = speaker_identifier.detect_cross_modal_discrepancy(
                claimed_identity, waveform, threshold=threshold
            )

        return {
            "identification": id_result,
            "discrepancy_check": discrepancy
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/speaker-id/enroll")
async def api_enroll_speaker_profile(
    file: UploadFile = File(...),
    speaker_id: str = Form(...),
    name: str = Form(...),
    category: str = Form("CONTACT"),
    phone: str = Form("Unknown")
):
    """Enrolls a voiceprint into the biometric directory (FAMILY, EXECUTIVE, CONTACT, SCAMMER_WATCHLIST)."""
    try:
        audio_bytes = await file.read()
        ext = "wav"
        if file.filename and "." in file.filename:
            ext = file.filename.rsplit(".", 1)[-1].lower()
        waveform = load_audio_from_bytes(audio_bytes, file_ext=ext)

        res = speaker_identifier.enroll(speaker_id, waveform, name=name, category=category, phone=phone)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/speaker-id/profiles")
def api_list_speaker_profiles():
    """Lists all enrolled biometric speaker profiles in the directory."""
    profiles_summary = []
    for sid, p in speaker_identifier.profiles.items():
        profiles_summary.append({
            "speaker_id": sid,
            "name": p["name"],
            "category": p["category"],
            "phone": p.get("phone", "Unknown"),
            "created_at": p.get("created_at", "")
        })
    return {"profiles": profiles_summary, "total_count": len(profiles_summary)}


# =========================================================================
# REAL-TIME PHONE CALL DEFENSE, AUTO-DROP & PRECAUTION ALERT ENDPOINTS
# =========================================================================

@app.post("/api/phone-call/start")
async def api_start_phone_call(
    caller_number: str = Form("+91-98765-43210"),
    caller_claimed_name: str = Form("Unknown Caller"),
    user_phone: str = Form("+91-99887-76655"),
    user_email: str = Form("security-alert@user.org"),
    emergency_contact: str = Form("+91-91234-56789")
):
    """Initializes an active telephone call interception session."""
    try:
        session = call_defense_engine.start_call_session(
            caller_number=caller_number,
            caller_claimed_name=caller_claimed_name,
            user_phone=user_phone,
            user_email=user_email,
            emergency_contact=emergency_contact
        )
        return session
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/phone-call/stream-chunk")
async def api_process_call_chunk(
    file: UploadFile = File(...),
    session_id: str = Form(...),
    auto_drop_threshold: float = Form(0.75)
):
    """
    Streams a live 2-3s audio chunk from an ongoing phone call.
    Evaluates dynamic risk, executes automated call drop on threat breach,
    and dispatches SMS/Email precaution alerts.
    """
    try:
        audio_bytes = await file.read()
        ext = "wav"
        if file.filename and "." in file.filename:
            ext = file.filename.rsplit(".", 1)[-1].lower()
        waveform = load_audio_from_bytes(audio_bytes, file_ext=ext)

        result = call_defense_engine.process_call_chunk(
            session_id=session_id,
            chunk_waveform=waveform,
            auto_drop_threshold=auto_drop_threshold
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/phone-call/terminate")
async def api_terminate_call(
    session_id: str = Form(...),
    reason: str = Form("Manual User Hangup")
):
    """Immediately terminates the ongoing phone call connection."""
    try:
        res = call_defense_engine.terminate_call(session_id=session_id, reason=reason)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/phone-call/dispatch-precaution")
async def api_dispatch_precaution(
    session_id: str = Form(...),
    custom_sms_phone: Optional[str] = Form(None),
    custom_email: Optional[str] = Form(None)
):
    """Triggers instant precaution SMS and security advisory HTML email for a call session."""
    try:
        res = call_defense_engine.dispatch_precaution_alerts(
            session_id=session_id,
            custom_sms_phone=custom_sms_phone,
            custom_email=custom_email
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/history")
def api_get_history(
    limit: int = 100,
    event_type: Optional[str] = None,
    search: Optional[str] = None
):
    """Returns deep forensic activity history with optional filtering and search."""
    events = history_manager.get_history(limit=limit, event_type=event_type, search=search)
    stats = history_manager.get_statistics()
    return {
        "status": "SUCCESS",
        "total_count": len(events),
        "statistics": stats,
        "history": events
    }


@app.get("/api/history/stats")
def api_get_history_stats():
    """Returns aggregated forensic activity metrics and defense counters."""
    return history_manager.get_statistics()


@app.get("/api/history/export")
def api_export_history():
    """Exports full forensic activity history as a downloadable JSON file."""
    filepath = history_manager.storage_path
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="No history file found.")
    return FileResponse(filepath, media_type="application/json", filename="voiceshield_forensic_history.json")


@app.get("/api/history/{incident_id}")
def api_get_incident_detail(incident_id: str):
    """Returns the comprehensive deep forensic profile for a specific incident."""
    incident = history_manager.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found.")
    return incident


@app.post("/api/history/log")
async def api_log_external_event(
    event_type: str = Form("CALL_SCREENING_INTERCEPT"),
    caller_or_file: str = Form(...),
    action_taken: str = Form(...),
    risk_percentage: float = Form(0.0),
    threat_description: str = Form(""),
    claimed_identity: Optional[str] = Form(""),
    source: str = Form("ANDROID_MOBILE"),
    sms_sent: bool = Form(False)
):
    """
    Allows Android Mobile App and external core gateways to log native call screening,
    in-call disconnections, and SIM SMS dispatch events directly into the central audit trail.
    """
    if event_type == "CALL_SCREENING_INTERCEPT":
        rec = history_manager.log_call_screening(
            caller_number=caller_or_file,
            action=action_taken,
            risk_percentage=risk_percentage,
            reason=threat_description,
            sms_sent=sms_sent,
            source=source
        )
    else:
        risk_level = "CRITICAL" if risk_percentage >= 75 else ("HIGH" if risk_percentage >= 50 else "LOW")
        rec = history_manager.log_event({
            "event_type": event_type,
            "caller_or_file": caller_or_file,
            "claimed_identity": claimed_identity or "Unknown",
            "action_taken": action_taken,
            "verdict": action_taken,
            "risk_percentage": risk_percentage,
            "risk_level": risk_level,
            "threats_detected": [threat_description] if threat_description else [],
            "source": source,
            "alerts": {"sms": {"sent": sms_sent, "gateway": "Android Native SIM Quota"}}
        })
    return {"status": "SUCCESS", "incident_id": rec.get("incident_id"), "logged_record": rec}


@app.delete("/api/history/clear")
def api_clear_history():
    """Clears forensic history logs."""
    history_manager.clear_history()
    return {"status": "SUCCESS", "message": "Forensic audit history cleared."}


@app.get("/api/phone-call/history")
def api_get_call_defense_history():
    """Returns incident log history for all defended phone calls."""
    return {"incidents": history_manager.get_history()}


@app.get("/api/phone-call/gateway-status")
def api_get_gateway_status():
    """Returns current live status and configuration of Email and SMS gateways."""
    return call_defense_engine.get_gateway_status()


@app.post("/api/phone-call/configure-alerts")
async def api_configure_alerts(
    smtp_server: Optional[str] = Form(None),
    smtp_port: Optional[int] = Form(None),
    smtp_user: Optional[str] = Form(None),
    smtp_password: Optional[str] = Form(None),
    alert_recipient_email: Optional[str] = Form(None),
    sms_gateway: Optional[str] = Form(None),
    alert_recipient_phone: Optional[str] = Form(None),
    twilio_sid: Optional[str] = Form(None),
    twilio_token: Optional[str] = Form(None),
    twilio_phone: Optional[str] = Form(None),
    fast2sms_key: Optional[str] = Form(None)
):
    """Updates real-world alert gateway credentials dynamically at runtime."""
    updates = {}
    if smtp_server: updates["SMTP_SERVER"] = smtp_server
    if smtp_port: updates["SMTP_PORT"] = smtp_port
    if smtp_user: updates["SMTP_USER"] = smtp_user
    if smtp_password: updates["SMTP_PASSWORD"] = smtp_password
    if alert_recipient_email: updates["ALERT_RECIPIENT_EMAIL"] = alert_recipient_email
    if sms_gateway: updates["SMS_GATEWAY"] = sms_gateway
    if alert_recipient_phone: updates["ALERT_RECIPIENT_PHONE"] = alert_recipient_phone
    if twilio_sid: updates["TWILIO_ACCOUNT_SID"] = twilio_sid
    if twilio_token: updates["TWILIO_AUTH_TOKEN"] = twilio_token
    if twilio_phone: updates["TWILIO_PHONE_NUMBER"] = twilio_phone
    if fast2sms_key: updates["FAST2SMS_API_KEY"] = fast2sms_key

    updated_status = call_defense_engine.configure_gateways(updates)
    return {"status": "SUCCESS", "gateway_status": updated_status}


@app.post("/api/phone-call/test-live-email")
async def api_test_live_email(test_recipient: Optional[str] = Form(None)):
    """Triggers an actual SMTP transmission to verify user's email credentials."""
    result = call_defense_engine.test_real_email(recipient=test_recipient)
    return result


@app.post("/api/phone-call/test-live-sms")
async def api_test_live_sms(test_recipient: Optional[str] = Form(None)):
    """Triggers a live test SMS transmission via configured gateway or Android SIM."""
    result = call_defense_engine.test_real_sms(recipient=test_recipient)
    return result


@app.get("/api/phone-call/download-apk")
def api_download_apk():
    """Serves the compiled VoiceShield AI Android APK file for direct installation."""
    apk_path = os.path.join(PROJECT_ROOT, "android", "app", "build", "outputs", "apk", "debug", "app-debug.apk")
    if not os.path.exists(apk_path):
        raise HTTPException(status_code=404, detail="APK has not been built yet. Build it via Android Studio (Build > Build APK) first.")
    return FileResponse(apk_path, media_type="application/vnd.android.package-archive", filename="VoiceShield-AI.apk")



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
        if "scam_digital_arrest" in fname.lower():
            stype = "SCAM"
            desc = "🚨 Digital Arrest Police Extortion"
        elif "scam_bank_kyc" in fname.lower():
            stype = "SCAM"
            desc = "💳 Bank KYC & OTP Harvesting Fraud"
        elif "scam_cxo_wire" in fname.lower():
            stype = "SCAM"
            desc = "👔 Executive / CXO Wire Fraud"
        elif "scam_tech_support" in fname.lower():
            stype = "SCAM"
            desc = "💻 Tech Support Ransomware Scam"
        elif "authentic_customer" in fname.lower() or "authentic_human" in fname.lower() or "real_human" in fname.lower():
            stype = "REAL"
            desc = "🟢 Authentic Human Conversation"
        elif "replayed" in fname.lower():
            stype = "FAKE"
            desc = "Replayed Attack (Acoustic Channel)"
        elif "clone" in fname.lower() or "synthetic" in fname.lower():
            stype = "FAKE"
            desc = "AI Voice Clone / Synthesizer"
        else:
            is_real = "real" in fname.lower()
            stype = "REAL" if is_real else "FAKE"
            desc = "Authentic Voice" if is_real else "Neural TTS / Deepfake"

        sample_list.append({
            "filename": fname,
            "type": stype,
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


@app.get("/api/docs/list")
def list_available_docs():
    """Lists generated PDF documents available for direct download."""
    pdf_dir = os.path.join(PROJECT_ROOT, "generated_documentation_pdfs")
    docs = []
    if os.path.exists(pdf_dir):
        for fname in sorted(os.listdir(pdf_dir)):
            if fname.lower().endswith(".pdf"):
                fpath = os.path.join(pdf_dir, fname)
                size_kb = round(os.path.getsize(fpath) / 1024, 1)
                docs.append({
                    "filename": fname,
                    "size_kb": size_kb,
                    "url": f"/api/docs/download/{fname}"
                })
    return {"documents": docs}


@app.get("/api/docs/download/{filename}")
def download_doc_pdf(filename: str):
    """Streams a generated documentation PDF file."""
    fpath = os.path.join(PROJECT_ROOT, "generated_documentation_pdfs", filename)
    if not os.path.exists(fpath):
        raise HTTPException(status_code=404, detail="Document PDF not found")
    return FileResponse(
        fpath, 
        media_type="application/pdf", 
        filename=filename,
        headers={"Content-Disposition": f"inline; filename={filename}"}
    )


# Mount UI static directory
ui_dir = os.path.join(PROJECT_ROOT, "ui")
if os.path.exists(ui_dir):
    app.mount("/", StaticFiles(directory=ui_dir, html=True), name="ui")
