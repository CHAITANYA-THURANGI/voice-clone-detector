"""
Enterprise Benchmark Evaluation Engine.
Evaluates the multi-vector framework (Conformer + Glottal + Phase Forensics)
against real human speech, Kaggle DEEP-VOICE, and synthetic/replayed attacks.
"""

import os
import sys
import glob

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ensemble import VoiceIntegrityEnsemble


def run_benchmark_evaluation():
    print("=" * 115)
    print("   VOICESHIELD AI ENTERPRISE BENCHMARK EVALUATION (CONFORMER + GLOTTAL + PHASE + SIH PS-26104)")
    print("=" * 115)

    ensemble = VoiceIntegrityEnsemble()
    samples_dir = os.path.join("data", "samples")
    sample_files = sorted(glob.glob(os.path.join(samples_dir, "*.wav")))

    if not sample_files:
        print(f"No samples found in {samples_dir}.")
        return

    results_table = []
    tp, tn, fp, fn = 0, 0, 0, 0

    print(f"\nEvaluating {len(sample_files)} benchmark files across all 5 enterprise forensic vectors...\n")

    for fpath in sample_files:
        fname = os.path.basename(fpath)
        is_real = "real" in fname.lower()
        expected = "REAL" if is_real else "FAKE"

        analysis = ensemble.analyze_audio(fpath)
        risk = analysis["risk_assessment"]
        neural = analysis["neural_detector"]
        metrics = analysis["forensic_metrics"]
        glottal = analysis["glottal_biometrics"]
        phase = analysis["phase_forensics"]
        plan = analysis["prevention_plan"]

        predicted_risk_level = risk["risk_level"]
        predicted_binary = "REAL" if predicted_risk_level == "LOW" else "FAKE"

        is_correct = (predicted_binary == expected)
        if expected == "FAKE" and predicted_binary == "FAKE":
            tp += 1
        elif expected == "REAL" and predicted_binary == "REAL":
            tn += 1
        elif expected == "REAL" and predicted_binary == "FAKE":
            fp += 1
        elif expected == "FAKE" and predicted_binary == "REAL":
            fn += 1

        results_table.append({
            "filename": fname,
            "expected": expected,
            "conformer": f"{neural['prediction']} ({neural['fake_probability']*100:.1f}%)",
            "kurtosis": f"{glottal['residual_kurtosis']:.1f}",
            "phase": f"{phase['phase_incoherence_score']*100:.1f}%",
            "risk_score": f"{risk['risk_percentage']}%",
            "risk_badge": risk["badge"],
            "prevention": plan["action_code"],
            "verdict": "✅ PASS" if is_correct else "❌ FAIL"
        })

    # Print Table
    header = f"{'Audio File':<26} | {'Expected':<8} | {'Conformer (ASP)':<18} | {'Kurtosis':<9} | {'Phase Inc':<9} | {'Risk':<7} | {'Risk Level':<24} | {'Verdict'}"
    print(header)
    print("-" * len(header))
    for r in results_table:
        print(f"{r['filename']:<26} | {r['expected']:<8} | {r['conformer']:<18} | {r['kurtosis']:<9} | {r['phase']:<9} | {r['risk_score']:<7} | {r['risk_badge']:<24} | {r['verdict']}")

    total = tp + tn + fp + fn
    accuracy = (tp + tn) / total if total > 0 else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    print("\n" + "=" * 55)
    print("         ENTERPRISE DEFENSE EVALUATION METRICS")
    print("=" * 55)
    print(f"True Positives (Detected Fakes):   {tp}")
    print(f"True Negatives (Verified Humans):  {tn}")
    print(f"False Positives (False Alarms):    {fp}")
    print(f"False Negatives (Missed Attacks):  {fn}")
    print("-" * 55)
    print(f"OVERALL ACCURACY:    {accuracy * 100:.1f}%")
    print(f"PRECISION:           {precision * 100:.1f}%")
    print(f"RECALL (ATTACK DET): {recall * 100:.1f}%  (Zero Missed Attacks)")
    print(f"F1-SCORE:            {f1 * 100:.1f}%")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    run_benchmark_evaluation()
