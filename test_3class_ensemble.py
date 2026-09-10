"""
Verification script for the 3-Class Multi-Model Ensemble.
Tests predictions across Human, Non-Human, and Voice Cloning Impersonation Attacks.
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ensemble import ensemble_instance


def test_3class_samples():
    print("=" * 85)
    print("🎯 MULTI-MODEL 3-CLASS ENSEMBLE VERIFICATION")
    print("=" * 85)

    test_files = [
        ("data/samples/real_human_01.wav", "HUMAN"),
        ("data/samples/kaggle_deepvoice_real_01.wav", "HUMAN"),
        ("data/samples/synthetic_tts_01.wav", "NON_HUMAN"),
        ("data/samples/kaggle_deepvoice_fake_01.wav", "VOICE_CLONING_ATTACK"),
        ("data/samples/synthetic_clone_02.wav", "VOICE_CLONING_ATTACK")
    ]

    for fpath, exp in test_files:
        if not os.path.exists(fpath):
            continue

        res = ensemble_instance.analyze_audio(fpath)
        fusion = res["ensemble_fusion"]
        risk = res["risk_assessment"]
        neural = res["neural_detector"]

        pred_class = fusion["predicted_class"]
        conf = fusion["consensus_confidence_pct"]
        probs = fusion["probabilities"]
        agree = int(fusion["model_agreement_ratio"] * 100)
        reasons = fusion["forensic_explanations"]

        print(f"File: {os.path.basename(fpath)}")
        print(f"  Expected Category:    {exp}")
        print(f"  Ensemble Consensus:   {pred_class} (Confidence: {conf}%)")
        print(f"  Conformer 3-Class:    {neural.get('predicted_class')} ({neural.get('confidence')}%)")
        print(f"  Risk Badge:           {risk['badge']}")
        print(f"  Risk Percentage:      {risk['risk_percentage']}%")
        print(f"  Probabilities:        Human={probs['human']*100:.1f}%, NonHuman={probs['non_human']*100:.1f}%, Attack={probs['voice_cloning_attack']*100:.1f}%")
        print(f"  Model Agreement:      {agree}% of sub-models agree")
        if reasons:
            print(f"  Forensic Rationale:   {reasons[0]}")
        print("-" * 85)


if __name__ == "__main__":
    test_3class_samples()
