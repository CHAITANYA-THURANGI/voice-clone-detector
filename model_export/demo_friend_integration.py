"""
Example Integration Script for Collaborators / External Models.
Demonstrates how to integrate the VoiceShield model into any external pipeline or model.
"""

import os
import sys

EXPORT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, EXPORT_DIR)

from voiceshield_client import VoiceCloneDetector

SAMPLE_REAL = os.path.join(EXPORT_DIR, "..", "data", "samples", "real_human_01.wav")
SAMPLE_FAKE = os.path.join(EXPORT_DIR, "..", "data", "samples", "kaggle_deepvoice_fake_01.wav")


def demo_integration():
    print("=" * 75)
    print("🤝 DEMO: EXTERNAL MODEL INTEGRATION WITH VOICESHIELD AI")
    print("=" * 75)

    # 1. Initialize detector with ONNX (Lightweight, No PyTorch required)
    print("\n[1] Initializing VoiceCloneDetector (Backend: ONNX Runtime)...")
    detector_onnx = VoiceCloneDetector(model_format="onnx")
    print("    Detector loaded successfully!")

    # 2. Test Real Human Sample
    if os.path.exists(SAMPLE_REAL):
        res_real = detector_onnx.predict(SAMPLE_REAL)
        print(f"\n[2] Testing Real Human Sample ({os.path.basename(SAMPLE_REAL)}):")
        print(f"    • Verdict:          {res_real['badge']}")
        print(f"    • Fake Probability: {res_real['fake_probability'] * 100:.2f}%")
        print(f"    • Confidence:       {res_real['confidence_pct']:.2f}%")

    # 3. Test Deepfake Voice Sample
    if os.path.exists(SAMPLE_FAKE):
        res_fake = detector_onnx.predict(SAMPLE_FAKE)
        print(f"\n[3] Testing Deepfake Clone Sample ({os.path.basename(SAMPLE_FAKE)}):")
        print(f"    • Verdict:          {res_fake['badge']}")
        print(f"    • Fake Probability: {res_fake['fake_probability'] * 100:.2f}%")
        print(f"    • Confidence:       {res_fake['confidence_pct']:.2f}%")

    # 4. Simulating Ensemble with Friend's Model
    print("\n[4] Example: Blending / Ensembling with your Friend's Model:")
    print("    -------------------------------------------------------")
    # Say friend's model gave fake probability of 0.92
    friend_model_fake_prob = 0.92
    voiceshield_fake_prob = res_fake["fake_probability"]

    # Weighted Ensemble (e.g. 50% VoiceShield Conformer + 50% Friend's Model)
    ensemble_prob = 0.50 * voiceshield_fake_prob + 0.50 * friend_model_fake_prob
    print(f"    VoiceShield Model Score:   {voiceshield_fake_prob:.4f}")
    print(f"    Friend's Model Score:      {friend_model_fake_prob:.4f}")
    print(f"    Ensembled Composite Score: {ensemble_prob:.4f}")
    print(f"    Final Combined Decision:   {'🔴 ATTACK BLOCKED' if ensemble_prob >= 0.50 else '🟢 AUTHENTIC'}")

    print("\n" + "=" * 75)
    print("✅ INTEGRATION DEMO COMPLETE!")
    print("=" * 75)


if __name__ == "__main__":
    demo_integration()
