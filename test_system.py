"""
End-to-End System Test Suite.
Verifies all components of the Voice Clone Detection & Prevention framework:
1. Audio preprocessing & FFmpeg integration
2. Feature extraction (spectral, prosody, voiceprint)
3. Model inference & evaluation metrics
4. Dynamic risk engine scoring
5. Automated fraud prevention response
6. Privacy zero-retention compliance
7. FastAPI endpoints & response schemas
"""

import os
import sys
import unittest
import numpy as np

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.audio_processor import load_audio, chunk_waveform, voice_activity_filter
from core.feature_extraction import extract_temporal_feature_matrix, extract_forensic_summary
from core.model import AcousticProsodicNet, load_trained_model
from core.speaker_verifier import SpeakerVerifier
from core.risk_engine import RiskEngine
from core.prevention import PreventionEngine
from core.privacy import PrivacyComplianceGuard
from ensemble import VoiceIntegrityEnsemble
from starlette.testclient import TestClient
from api.server import app


class TestVoiceShieldFramework(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.sample_wav = os.path.join("data", "samples", "real_human_01.wav")
        cls.fake_wav = os.path.join("data", "samples", "replayed_spoof_03.wav")
        cls.client = TestClient(app)

    def test_01_audio_loading(self):
        self.assertTrue(os.path.exists(self.sample_wav))
        waveform = load_audio(self.sample_wav)
        self.assertIsInstance(waveform, np.ndarray)
        self.assertEqual(waveform.ndim, 1)
        self.assertGreater(len(waveform), 8000)

    def test_02_feature_extraction(self):
        waveform = load_audio(self.sample_wav)
        matrix = extract_temporal_feature_matrix(waveform)
        self.assertEqual(matrix.shape, (100, 32))

        summary = extract_forensic_summary(waveform)
        self.assertEqual(len(summary["vector"]), 78)
        self.assertIn("f0_mean_hz", summary["metrics"])
        self.assertIn("jitter", summary["metrics"])
        self.assertIn("spectral_rolloff_hz", summary["metrics"])

    def test_03_deep_learning_model(self):
        model = load_trained_model("models/acoustic_prosodic_net.pth")
        dummy_input = np.random.randn(100, 32).astype(np.float32)
        res = model.predict_sample(dummy_input)
        self.assertIn(res["prediction"], ["REAL", "FAKE"])
        self.assertGreaterEqual(res["fake_probability"], 0.0)
        self.assertLessEqual(res["fake_probability"], 1.0)

    def test_04_speaker_verification(self):
        verifier = SpeakerVerifier(profiles_file="data/test_profiles.json")
        wav1 = load_audio(self.sample_wav)
        enroll_res = verifier.enroll("VIP_CEO", wav1)
        self.assertEqual(enroll_res["status"], "ENROLLED")

        # Verify same speaker
        verify_same = verifier.verify("VIP_CEO", wav1)
        self.assertTrue(verify_same["enrolled"])
        self.assertGreater(verify_same["similarity"], 0.90)

    def test_05_prevention_playbook(self):
        risk_assessment = {
            "risk_level": "HIGH",
            "risk_score": 0.88,
            "badge": "🔴 HIGH RISK (ATTACK)",
            "context_flags": ["High-Value Financial Transaction"]
        }
        plan = PreventionEngine.generate_prevention_plan(risk_assessment)
        self.assertTrue(plan["block_transaction"])
        self.assertTrue(plan["require_secondary_auth"])
        self.assertEqual(plan["action_code"], "CRITICAL_ATTACK_BLOCK")

    def test_06_privacy_zero_retention(self):
        dummy_audio = np.ones(16000, dtype=np.float32)
        sha = PrivacyComplianceGuard.generate_audio_fingerprint(dummy_audio)
        self.assertEqual(len(sha), 64)
        PrivacyComplianceGuard.purge_raw_audio(dummy_audio)
        self.assertEqual(np.sum(dummy_audio), 0.0)

    def test_07_api_endpoints(self):
        # Health check
        res = self.client.get("/api/system-status")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "ONLINE")

        # Benchmarks list
        res = self.client.get("/api/benchmark-samples")
        self.assertEqual(res.status_code, 200)
        self.assertGreaterEqual(len(res.json()["samples"]), 1)

        # File analysis endpoint
        with open(self.sample_wav, "rb") as f:
            files = {"file": ("real_sample.wav", f, "audio/wav")}
            data = {"transaction_amount": "25000", "is_cxo_call": "true"}
            res = self.client.post("/api/analyze-audio", files=files, data=data)
            self.assertEqual(res.status_code, 200)
            res_json = res.json()
            self.assertEqual(res_json["status"], "success")
            self.assertIn("risk_assessment", res_json)
            self.assertIn("prevention_plan", res_json)
            self.assertIn("enterprise_telemetry", res_json)
            self.assertIn("cef_event", res_json["enterprise_telemetry"])
            self.assertIn("glottal_biometrics", res_json)
            self.assertIn("phase_forensics", res_json)

    def test_08_enterprise_forensics_and_telemetry(self):
        from core.glottal_forensics import analyze_glottal_biometrics
        from core.spectral_phase import analyze_phase_coherence
        from core.enterprise_telemetry import EnterpriseTelemetryEngine

        waveform = load_audio(self.sample_wav)
        
        # Test Glottal inverse filtering
        glottal = analyze_glottal_biometrics(waveform)
        self.assertIn("residual_kurtosis", glottal)
        self.assertIn("glottal_anomaly_score", glottal)
        self.assertGreaterEqual(glottal["glottal_anomaly_score"], 0.0)

        # Test Spectral Phase Coherence
        phase = analyze_phase_coherence(waveform)
        self.assertIn("mgd_variance", phase)
        self.assertIn("phase_incoherence_score", phase)
        self.assertGreaterEqual(phase["phase_incoherence_score"], 0.0)

        # Test Enterprise Telemetry & CEF Syslog
        risk_eval = {
            "composite_risk_score": 0.85,
            "risk_score": 0.85,
            "risk_level": "HIGH",
            "badge": "🔴 HIGH RISK (ATTACK)",
            "decision": "SYNTHETIC_ATTACK_DETECTED"
        }
        prevention_plan = {
            "incident_id": "INC-TEST-001",
            "call_id": "CALL-TEST-001",
            "timestamp": "2026-09-09T12:00:00Z",
            "action_code": "CRITICAL_ATTACK_BLOCK",
            "primary_action": "BLOCK_TRANSACTION",
            "block_transaction": True,
            "require_secondary_auth": True
        }
        audio_meta = {
            "duration_sec": 3.0,
            "sha256": "abcdef1234567890"
        }
        cef = EnterpriseTelemetryEngine.generate_cef_event(risk_eval, prevention_plan, audio_meta)
        self.assertTrue(cef.startswith("CEF:0|VoiceShieldAI|VoiceDefensePlatform|2.0|"))
        self.assertEqual(EnterpriseTelemetryEngine.MITRE_MAPPING["technique_id"], "T1656")

    def test_09_live_stream_chunk_endpoint(self):
        with open(self.sample_wav, "rb") as f:
            files = {"file": ("stream_chunk.wav", f, "audio/wav")}
            data = {
                "call_id": "STREAM-LIVE-TEST",
                "timestamp_sec": "3.0",
                "transaction_amount": "50000",
                "is_cxo_call": "true"
            }
            res = self.client.post("/api/stream-chunk", files=files, data=data)
            self.assertEqual(res.status_code, 200)
            res_json = res.json()
            self.assertIn("session_assessment", res_json)
            self.assertIn("chunk_record", res_json)
            self.assertIn("glottal_biometrics", res_json)
            self.assertIn("phase_forensics", res_json)
            self.assertIn("neural_detector", res_json)
            self.assertIn("prevention_plan", res_json)
            self.assertIn("enterprise_telemetry", res_json)

    def test_10_mpeg_audio_support(self):
        mpeg_path = os.path.join("data", "samples", "authentic_human_id.mpeg")
        self.assertTrue(os.path.exists(mpeg_path))
        with open(mpeg_path, "rb") as f:
            files = {"file": ("test_voice.mpeg", f, "audio/mpeg")}
            res = self.client.post("/api/analyze-audio", files=files)
            self.assertEqual(res.status_code, 200)
            res_json = res.json()
            self.assertEqual(res_json["status"], "success")
            self.assertIn("risk_assessment", res_json)
            self.assertIn("neural_detector", res_json)
            self.assertEqual(res_json["risk_assessment"]["risk_level"], "LOW")


if __name__ == "__main__":
    unittest.main()




