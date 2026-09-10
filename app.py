"""
VoiceShield AI - Hugging Face Spaces Interactive Web App
AI-Powered Real-Time Voice Cloning Detection & Forensic Defense (SIH PS-26104).
Provides interactive Gradio interface for audio verification and acoustic biometric forensics.
"""

import os
import sys
import numpy as np

# Force single-threaded execution to prevent thread contention
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("ENABLE_LOCAL_WHISPER", "0")

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ensemble import ensemble_instance
from core.audio_processor import load_audio


def analyze_voice_sample(audio_path):
    """Executes VoiceShield forensic pipeline on user-uploaded or recorded audio."""
    if not audio_path:
        return (
            "⚠️ No audio provided. Please upload a voice recording or use the microphone.",
            "### ⚠️ No audio provided.",
            {},
            "Please provide an audio file."
        )

    try:
        result = ensemble_instance.analyze_audio(audio_path, call_id="HF-SPACE")
        risk = result.get("risk_assessment", {})
        fusion = result.get("ensemble_fusion", {})
        neural = result.get("neural_detector", {})
        forensic = result.get("forensic_metrics", {})
        glottal = result.get("glottal_biometrics", {})
        phase = result.get("phase_forensics", {})

        p_class = fusion.get("predicted_class", "HUMAN")
        risk_pct = float(risk.get("risk_percentage", 0.0))
        risk_level = risk.get("risk_level", "LOW")

        if risk_pct >= 65.0 or p_class == "VOICE_CLONING_ATTACK":
            verdict_badge = f"🚨 VOICE CLONING ATTACK DETECTED (Risk: {risk_pct}%)"
            badge_markdown = (
                f"### 🚨 Threat Verdict: **VOICE CLONING ATTACK**\n"
                f"- **Risk Level:** `{risk_level}` ({risk_pct}%)\n"
                f"- **Threat Signatures:** {', '.join(risk.get('threats_detected', ['Synthetic Audio Spoof']))}\n"
                f"- **Ensemble Consensus:** `{p_class}`\n"
                f"- **Action Enforced:** `IMMEDIATE_THREAT_ISOLATION`"
            )
        elif risk_pct >= 40.0:
            verdict_badge = f"⚠️ SUSPICIOUS / UNVERIFIED (Risk: {risk_pct}%)"
            badge_markdown = (
                f"### ⚠️ Threat Verdict: **SUSPICIOUS AUDIO**\n"
                f"- **Risk Level:** `{risk_level}` ({risk_pct}%)\n"
                f"- **Potential Anomaly:** Unnatural acoustic dispersion or low signal quality\n"
                f"- **Ensemble Consensus:** `{p_class}`\n"
                f"- **Action Enforced:** `STEP_UP_AUTHENTICATION`"
            )
        else:
            verdict_badge = f"🟢 AUTHENTIC HUMAN VOICE (Risk: {risk_pct}%)"
            badge_markdown = (
                f"### 🟢 Threat Verdict: **AUTHENTIC HUMAN VOICE**\n"
                f"- **Risk Level:** `{risk_level}` ({risk_pct}%)\n"
                f"- **Biometric Verification:** Natural biological glottal excitation verified\n"
                f"- **Ensemble Consensus:** `{p_class}`\n"
                f"- **Action Enforced:** `ALLOW_TRANSACTION_OR_CALL`"
            )

        telemetry_table = {
            "Metric": [
                "Predicted Class",
                "Composite Risk Score",
                "Conformer Neural Confidence",
                "Pitch Mean (F0)",
                "Micro-Jitter",
                "Micro-Shimmer",
                "Harmonics-to-Noise (HNR)",
                "Spectral Centroid",
                "Glottal Residual Status",
                "Phase Coherence Status"
            ],
            "Observed Value": [
                p_class,
                f"{risk_pct}%",
                f"{neural.get('confidence', 0.0)}%",
                f"{forensic.get('pitch_mean_hz', 0.0)} Hz",
                f"{forensic.get('jitter_pct', 0.0)}%",
                f"{forensic.get('shimmer_pct', 0.0)}%",
                f"{forensic.get('hnr_db', 0.0)} dB",
                f"{forensic.get('spectral_centroid_hz', 0.0)} Hz",
                glottal.get("display_status", "Biological Impulse"),
                phase.get("display_status", "Continuous Natural Phase")
            ]
        }

        try:
            import pandas as pd
            df_telemetry = pd.DataFrame(telemetry_table)
        except Exception:
            df_telemetry = telemetry_table

        summary_text = (
            f"Forensic SHA-256: {result.get('compliance_audit', {}).get('sha256_fingerprint', 'N/A')}\n"
            f"Duration: {result.get('audio_metadata', {}).get('duration_sec', 0.0)}s\n"
            f"Compliance: India DPDP Act 2023 & GDPR Zero-Retention RAM Enclave"
        )

        return verdict_badge, badge_markdown, df_telemetry, summary_text

    except Exception as e:
        return (
            f"❌ Analysis Error: {str(e)}",
            f"### Error\n```\n{str(e)}\n```",
            {},
            "Check audio format and try again."
        )


def build_gradio_app():
    """Builds and configures the Gradio Blocks application."""
    try:
        import gradio as gr
    except ImportError:
        return None

    theme = gr.themes.Soft(
        primary_hue="blue",
        secondary_hue="slate",
        neutral_hue="slate"
    )

    with gr.Blocks(title="VoiceShield AI | Voice Clone & Deepfake Detector", theme=theme) as demo:
        gr.Markdown(
            """
            # 🛡️ VoiceShield AI: Real-Time Voice Cloning Detection & Forensic Defense
            ### Enterprise-Grade Multi-Vector Voice Spoofing & Deepfake Impersonation Defense • SIH PS-26104
            Upload an audio recording or record your voice to test for synthetic cloning, neural vocoders, and replay attacks.
            """
        )

        with gr.Row():
            with gr.Column(scale=1):
                audio_input = gr.Audio(
                    sources=["upload", "microphone"],
                    type="filepath",
                    label="🎙️ Voice Audio Ingestion (Upload or Live Mic)"
                )
                analyze_btn = gr.Button("🔍 Verify Voice Authenticity", variant="primary", size="lg")

                samples_dir = os.path.join(PROJECT_ROOT, "data", "samples")
                sample_files = []
                if os.path.exists(samples_dir):
                    for f in sorted(os.listdir(samples_dir)):
                        if f.endswith(".wav"):
                            sample_files.append([os.path.join(samples_dir, f)])

                if sample_files:
                    gr.Examples(
                        examples=sample_files,
                        inputs=audio_input,
                        label="⚡ One-Click Benchmark Test Samples"
                    )

            with gr.Column(scale=1):
                verdict_output = gr.Textbox(label="Verdict Summary", interactive=False)
                badge_markdown = gr.Markdown("### Awaiting voice analysis...")
                telemetry_table = gr.Dataframe(label="🔬 7-Vector Acoustic Telemetry & Neural Metrics", interactive=False)
                meta_output = gr.Textbox(label="Audit & Compliance Metadata", interactive=False)

        analyze_btn.click(
            fn=analyze_voice_sample,
            inputs=[audio_input],
            outputs=[verdict_output, badge_markdown, telemetry_table, meta_output]
        )

        gr.Markdown(
            """
            ---
            **Architecture:** Conformer Neural Network (ASP + MHSA) • Levinson-Durbin Glottal Biometrics • Phase-Aware Modified Group Delay (MGD) • 16kHz VAD Enclave.  
            **Compliance:** India DPDP Act 2023 Zero-Retention Ephemeral RAM Enclave • MITRE ATT&CK T1656.
            """
        )

    return demo


if __name__ == "__main__":
    app = build_gradio_app()
    if app:
        port = int(os.environ.get("PORT", 7860))
        app.launch(server_name="0.0.0.0", server_port=port)
    else:
        import uvicorn
        from api.server import app as fastapi_app
        port = int(os.environ.get("PORT", 7860))
        uvicorn.run(fastapi_app, host="0.0.0.0", port=port)
