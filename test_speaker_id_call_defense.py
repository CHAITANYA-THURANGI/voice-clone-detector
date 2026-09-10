"""
Unit & Integration Tests for 1:N Speaker Identification,
Real-Time Phone Call Interception, Automated Call-Drop, and Precaution Dispatch.
"""

import os
import sys
import unittest
from fastapi.testclient import TestClient

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.audio_processor import load_audio
from core.speaker_identifier import speaker_identifier
from core.call_defense_engine import call_defense_engine
from api.server import app


class TestSpeakerIdAndCallDefense(unittest.TestCase):

    def setUp(self):
        self.samples_dir = os.path.join(PROJECT_ROOT, "data", "samples")
        self.client = TestClient(app)

    def test_1_speaker_identification_matches_family_contact(self):
        """Verify 1:N open-set search identifies enrolled Mom with high confidence."""
        mom_wav = load_audio(os.path.join(self.samples_dir, "3sec_authentic_voice_note.wav"))
        id_res = speaker_identifier.identify_speaker(mom_wav)

        self.assertTrue(id_res["identified"], "Enrolled voice should be identified")
        self.assertEqual(id_res["category"], "FAMILY")
        self.assertIn("Mom", id_res["name"])
        self.assertGreaterEqual(id_res["similarity"], 0.85)
        print(f"\n[TEST PASS] 1:N Speaker Identification: Identified {id_res['name']} ({id_res['confidence_pct']}%)")

    def test_2_cross_modal_imposter_discrepancy_detection(self):
        """Verify cross-modal engine catches an imposter claiming to be Mom."""
        # Scammer audio claiming to be Mom
        scam_wav = load_audio(os.path.join(self.samples_dir, "scam_digital_arrest_police.wav"))
        disc = speaker_identifier.detect_cross_modal_discrepancy("Mom", scam_wav)

        self.assertTrue(disc["is_discrepancy"], "Imposter acoustics claiming Mom must trigger discrepancy")
        self.assertEqual(disc["discrepancy_type"], "IMPOSTER_IDENTITY_MISMATCH")
        self.assertLess(disc["similarity_pct"], 50.0)
        self.assertIn("BIOMETRIC DISCREPANCY", disc["summary"])
        print(f"[TEST PASS] Imposter Discrepancy Caught: Claimed Mom, Similarity = {disc['similarity_pct']}%")

    def test_3_open_set_unknown_caller_rejection(self):
        """Verify voiceprints not in directory are tagged as UNKNOWN_CALLER."""
        # Test on replayed spoof audio
        replay_wav = load_audio(os.path.join(self.samples_dir, "replayed_spoof_03.wav"))
        id_res = speaker_identifier.identify_speaker(replay_wav, threshold=0.70)
        # Should not falsely identify as Mom or CEO
        if not id_res["identified"]:
            self.assertEqual(id_res["speaker_id"], "UNKNOWN_CALLER")
        print(f"[TEST PASS] Open-Set Search: Correctly handled as {id_res['name']}")

    def test_4_automated_call_drop_on_threat_breach(self):
        """Verify CallDefenseEngine executes immediate hangup when risk exceeds 75%."""
        session = call_defense_engine.start_call_session(
            caller_number="+91-140-776655",
            caller_claimed_name="Police Officer",
            user_phone="+91-99887-11223",
            user_email="victim@enterprise.com"
        )
        session_id = session["session_id"]

        scam_wav = load_audio(os.path.join(self.samples_dir, "scam_digital_arrest_police.wav"))
        res = call_defense_engine.process_call_chunk(session_id, scam_wav, auto_drop_threshold=0.75)

        self.assertTrue(res["call_terminated"], "High-risk call should be automatically terminated")
        self.assertEqual(res["status"], "TERMINATED_BY_SYSTEM")
        self.assertGreaterEqual(res["effective_risk"], 0.75)
        self.assertIn("Automated Defense", res["termination_reason"])
        print(f"\n[TEST PASS] Automated Call Drop: Terminated call {session_id} at {res['effective_risk_percentage']}% risk")

    def test_5_precaution_alerts_generation(self):
        """Verify instant Precaution SMS and Security Advisory HTML Email generation."""
        session = call_defense_engine.start_call_session(
            caller_number="+91-98765-00112",
            caller_claimed_name="Bank Security",
            user_phone="+91-99887-33445",
            user_email="victim@securemail.org",
            emergency_contact="+91-91234-56789"
        )
        session_id = session["session_id"]
        session["threats_detected"] = ["Banking KYC Scam", "Synthetic Voice Attack"]
        session["accumulated_transcript"] = "Your debit card is blocked. Send OTP immediately."

        alerts = call_defense_engine.dispatch_precaution_alerts(session_id)
        self.assertEqual(alerts["status"], "SUCCESS")

        # Check SMS
        sms = alerts["sms_alert"]
        self.assertEqual(sms["channel"], "SMS")
        self.assertEqual(sms["recipient"], "+91-99887-33445")
        self.assertIn("VOICESHIELD AI ALERT", sms["content"])
        self.assertIn("+91-98765-00112", sms["content"])

        # Check Email
        email = alerts["email_alert"]
        self.assertEqual(email["channel"], "EMAIL")
        self.assertEqual(email["recipient"], "victim@securemail.org")
        self.assertIn("Incident Reference", email["html_content"])
        self.assertIn("CRITICAL ATTACK TERMINATED", email["html_content"])
        print(f"[TEST PASS] Precaution Dispatch: Generated Incident {alerts['incident_id']} with SMS & HTML Email")

    def test_6_api_endpoints_integration(self):
        """Verify FastAPI endpoints for phone call streaming and speaker identification."""
        # Test 1: Profiles list
        p_resp = self.client.get("/api/speaker-id/profiles")
        self.assertEqual(p_resp.status_code, 200)
        self.assertGreaterEqual(p_resp.json()["total_count"], 3)

        # Test 2: Start Phone Call
        s_resp = self.client.post("/api/phone-call/start", data={
            "caller_number": "+91-88888-99999",
            "caller_claimed_name": "Unknown Caller"
        })
        self.assertEqual(s_resp.status_code, 200)
        call_id = s_resp.json()["session_id"]

        # Test 3: Stream Chunk to API
        with open(os.path.join(self.samples_dir, "3sec_social_media_family_clone.wav"), "rb") as f:
            c_resp = self.client.post(
                "/api/phone-call/stream-chunk",
                files={"file": ("chunk.wav", f, "audio/wav")},
                data={"session_id": call_id, "auto_drop_threshold": 0.75}
            )
        self.assertEqual(c_resp.status_code, 200)
        c_data = c_resp.json()
        self.assertTrue(c_data["call_terminated"], "Family clone call should trigger automated drop")
        self.assertGreaterEqual(len(c_data["dispatched_alerts"]), 2)
        print(f"\n[TEST PASS] API End-to-End: Tested /api/phone-call/stream-chunk (Call dropped: {c_data['call_terminated']})")


if __name__ == "__main__":
    unittest.main()
