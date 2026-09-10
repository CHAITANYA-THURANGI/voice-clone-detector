"""
Unit & Integration Tests for 3-Second Micro-Clip Forensics,
Voicemod Real-Time Voice Changer Detection, and Family/Boss Scam Recognition.
"""

import os
import sys
import unittest
import numpy as np

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.audio_processor import load_audio
from core.voicemod_detector import analyze_voicemod_and_microclip
from core.semantic_fraud_detector import SemanticFraudDetector, CAT_FAMILY_BOSS_CLONE
from ensemble import ensemble_instance


class Test3SecAndVoicemodForensics(unittest.TestCase):

    def setUp(self):
        self.samples_dir = os.path.join(PROJECT_ROOT, "data", "samples")
        self.family_clone_path = os.path.join(self.samples_dir, "3sec_social_media_family_clone.wav")
        self.voicemod_path = os.path.join(self.samples_dir, "3sec_voicemod_voice_changer.wav")
        self.authentic_path = os.path.join(self.samples_dir, "3sec_authentic_voice_note.wav")

    def test_sample_files_exist(self):
        """Ensure the 3-second benchmark audio files are generated and present."""
        self.assertTrue(os.path.exists(self.family_clone_path), "Family clone sample missing")
        self.assertTrue(os.path.exists(self.voicemod_path), "Voicemod changer sample missing")
        self.assertTrue(os.path.exists(self.authentic_path), "Authentic voice note sample missing")

    def test_voicemod_forensics_on_voice_changer(self):
        """Verify harmonic comb filtering and vocoder dispersion flags on Voicemod audio."""
        wav = load_audio(self.voicemod_path)
        res = analyze_voicemod_and_microclip(wav, sr=16000)

        self.assertTrue(res["is_micro_clip"], "3-second file should be marked as micro-clip")
        self.assertTrue(res["is_voicemod_suspicious"], "Voicemod artifacts should be flagged as suspicious")
        self.assertGreater(res["comb_ripple"], 0.40, f"Comb ripple expected > 0.40, got {res['comb_ripple']}")
        self.assertGreater(res["voicemod_confidence"], 0.70)
        print(f"\n[TEST PASS] Voicemod Forensics: Comb Ripple = {res['comb_ripple']}, Confidence = {res['voicemod_confidence']}")

    def test_voicemod_forensics_on_authentic_voice(self):
        """Verify authentic voice does not trigger Voicemod pitch-shifter alarms."""
        wav = load_audio(self.authentic_path)
        res = analyze_voicemod_and_microclip(wav, sr=16000)

        self.assertTrue(res["is_micro_clip"], "3-second file should be marked as micro-clip")
        self.assertFalse(res["is_voicemod_suspicious"], "Authentic voice should not be flagged as Voicemod")
        self.assertLess(res["comb_ripple"], 0.35, f"Comb ripple expected < 0.35, got {res['comb_ripple']}")
        print(f"\n[TEST PASS] Authentic Voice: Comb Ripple = {res['comb_ripple']} (Normal, no comb filtering)")

    def test_semantic_family_boss_scam_detection(self):
        """Verify semantic analysis identifies family distress / boss credential extortion in voice notes."""
        detector = SemanticFraudDetector()

        # Test familial emergency distress pattern
        distress_transcript = (
            "Mom, I broke my phone and lost my wallet in an emergency. "
            "Please send five hundred dollars immediately."
        )
        res = detector.analyze_semantic_threat(distress_transcript)
        self.assertTrue(res["is_threat"], "Family distress money request should be flagged as threat")
        self.assertEqual(res["scam_category"], CAT_FAMILY_BOSS_CLONE)
        self.assertIn("familial intimate greeting", str(res["matched_cues"]))
        print(f"\n[TEST PASS] Semantic Engine: Identified {res['display_name']} with confidence {res['confidence']}")

        # Test boss credential harvest pattern
        boss_transcript = (
            "Hi, this is your boss from the director's office. "
            "I need you to send me the login password and credentials right now."
        )
        res_boss = detector.analyze_semantic_threat(boss_transcript)
        self.assertTrue(res_boss["is_threat"], "Boss credential extortion should be flagged as threat")
        self.assertEqual(res_boss["scam_category"], CAT_FAMILY_BOSS_CLONE)
        print(f"[TEST PASS] Boss Impersonation: Identified {res_boss['display_name']} with confidence {res_boss['confidence']}")

    def test_end_to_end_ensemble_analysis(self):
        """Verify the full 7-vector ensemble correctly routes and classifies the 3-second samples."""
        # 1. Family clone
        clone_result = ensemble_instance.analyze_audio(
            self.family_clone_path, 
            call_id="TEST-3SEC-CLONE",
            context={"transcript": "Mom, I broke my phone and need money urgently"}
        )
        self.assertEqual(clone_result["ensemble_fusion"]["predicted_class"], "VOICE_CLONING_ATTACK")
        self.assertGreaterEqual(clone_result["risk_assessment"]["risk_score"], 0.70)
        self.assertEqual(clone_result["semantic_fraud_detector"]["scam_category"], CAT_FAMILY_BOSS_CLONE)

        # 2. Authentic note
        auth_result = ensemble_instance.analyze_audio(self.authentic_path, call_id="TEST-3SEC-AUTH")
        self.assertEqual(auth_result["ensemble_fusion"]["predicted_class"], "HUMAN")
        self.assertLess(auth_result["risk_assessment"]["risk_score"], 0.35)

        # 3. Voicemod changer
        voicemod_result = ensemble_instance.analyze_audio(self.voicemod_path, call_id="TEST-3SEC-VOICEMOD")
        self.assertTrue(voicemod_result["voicemod_forensics"]["is_voicemod_suspicious"])
        self.assertEqual(voicemod_result["ensemble_fusion"]["predicted_class"], "VOICE_CLONING_ATTACK")
        explanations = str(voicemod_result["ensemble_fusion"].get("forensic_explanations", []))
        self.assertIn("Voicemod", explanations)
        print("\n[TEST PASS] Full Ensemble Consensus: All 3-second scenarios accurately classified!")


if __name__ == "__main__":
    unittest.main()
