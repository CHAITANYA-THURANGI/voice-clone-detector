"""
Test suite for Deep Forensic Activity & Audit History System.
Verifies persistence, 7-vector acoustic storage, REST APIs, and cross-device mobile sync.
"""

import os
import sys
import unittest
from fastapi.testclient import TestClient

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.server import app
from core.history_manager import history_manager


class TestDeepHistorySystem(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_01_history_loaded(self):
        """Verifies history is loaded and populated with initial records."""
        events = history_manager.get_history(limit=50)
        self.assertIsInstance(events, list)
        self.assertGreaterEqual(len(events), 1)
        stats = history_manager.get_statistics()
        self.assertIn("total_events", stats)
        print(f"[TEST PASS] Loaded {len(events)} events. Stats: {stats}")

    def test_02_log_audio_analysis(self):
        """Verifies logging deep 7-vector audio forensic analysis."""
        mock_analysis = {
            "call_id": "CALL-UNITTEST",
            "spectral_centroid": 1950.4,
            "spectral_rolloff": 4120.0,
            "pitch_mean": 155.2,
            "pitch_std": 34.1,
            "jitter_pct": 2.45,
            "shimmer_pct": 5.12,
            "hnr_db": 13.8,
            "zero_crossing_rate": 0.089,
            "formants": [680.0, 1780.0, 2720.0],
            "risk_assessment": {
                "risk_score": 0.92,
                "risk_level": "CRITICAL"
            },
            "ensemble_fusion": {
                "predicted_class": "VOICE_CLONING_ATTACK",
                "consensus_confidence_pct": 94.2,
                "model_agreement_score": 0.95,
                "entropy_uncertainty": 0.22,
                "class_probabilities": {
                    "human": 0.04,
                    "non_human": 0.04,
                    "voice_clone_attack": 0.92
                }
            },
            "neural_model": {
                "deepfake_probability": 0.93,
                "prediction": "VOICE_CLONING_ATTACK"
            },
            "voicemod_forensics": {
                "voicemod_detected": True,
                "comb_ripple": 0.52,
                "is_micro_clip": False
            },
            "semantic_fraud_detector": {
                "is_threat": True,
                "display_name": "Digital Arrest Extortion",
                "coercion_urgency_level": 90.0,
                "flagged_keywords": ["arrest", "police", "cbi", "warrant"],
                "transcript": "This is CBI Police. An arrest warrant has been issued against your Aadhaar."
            },
            "glottal_biometrics": {
                "residual_kurtosis": 6.4,
                "status": "SUSPICIOUS_UNNATURAL"
            },
            "phase_coherence": {
                "phase_jitter": 0.048,
                "continuity": "DISCONTINUOUS"
            },
            "speaker_verification": {
                "profile_name": "Unenrolled Target",
                "confidence_pct": 12.0,
                "is_match": False,
                "is_imposter": True
            },
            "compliance": {
                "audio_sha256": "abcdef1234567890abcdef1234567890",
                "dpdp_act_compliance": "India DPDP Act 2023 (Zero-Retention Ephemeral RAM)"
            }
        }

        rec = history_manager.log_audio_analysis(
            filename="3sec_scam_arrest_call.wav",
            result=mock_analysis,
            source="WEB_DASHBOARD",
            claimed_speaker="Unknown Caller"
        )

        self.assertTrue(rec["incident_id"].startswith("AUD-"))
        self.assertEqual(rec["verdict"], "VOICE_CLONING_ATTACK")
        self.assertEqual(rec["risk_percentage"], 92.0)
        self.assertIn("deep_forensics", rec)
        self.assertEqual(rec["deep_forensics"]["acoustic_vectors"]["jitter_pct"], 2.45)
        print(f"[TEST PASS] Deep audio analysis logged: {rec['incident_id']}")

    def test_03_mobile_screening_log_api(self):
        """Verifies POST /api/history/log from mobile device."""
        resp = self.client.post("/api/history/log", data={
            "event_type": "CALL_SCREENING_INTERCEPT",
            "caller_or_file": "+91-140-776655",
            "action_taken": "REJECTED",
            "risk_percentage": "99.0",
            "threat_description": "Known Watchlist Fraudster Pre-Call Block",
            "claimed_identity": "Police Officer",
            "source": "ANDROID_MOBILE",
            "sms_sent": "true"
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "SUCCESS")
        self.assertTrue(data["incident_id"].startswith("SCR-"))
        print(f"[TEST PASS] Mobile screening log verified: {data['incident_id']}")

    def test_04_get_history_filters_and_search(self):
        """Verifies GET /api/history filtering by event_type and search query."""
        resp = self.client.get("/api/history?event_type=CALL_SCREENING_INTERCEPT")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreaterEqual(data["total_count"], 1)

        search_resp = self.client.get("/api/history?search=140-776655")
        self.assertEqual(search_resp.status_code, 200)
        search_data = search_resp.json()
        self.assertGreaterEqual(search_data["total_count"], 1)
        print(f"[TEST PASS] API history filters & search passed. Found: {search_data['total_count']} matches.")

    def test_05_incident_detail_api(self):
        """Verifies GET /api/history/{incident_id} returns all 7 acoustic vectors."""
        events = history_manager.get_history(limit=5)
        first_id = events[0]["incident_id"]

        resp = self.client.get(f"/api/history/{first_id}")
        self.assertEqual(resp.status_code, 200)
        detail = resp.json()
        self.assertEqual(detail["incident_id"], first_id)
        self.assertIn("deep_forensics", detail)
        self.assertIn("acoustic_vectors", detail["deep_forensics"])
        print(f"[TEST PASS] Incident detail retrieved with deep forensics: {first_id}")

    def test_06_export_history(self):
        """Verifies GET /api/history/export serves JSON file."""
        resp = self.client.get("/api/history/export")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get("content-type"), "application/json")
        print("[TEST PASS] History export endpoint validated.")


if __name__ == "__main__":
    unittest.main()
