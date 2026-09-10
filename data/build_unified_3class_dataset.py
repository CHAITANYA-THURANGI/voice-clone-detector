"""
Unified 3-Class Master Dataset Ingestion & Feature Caching Engine:
1. Class 0: HUMAN (Genuine biological human speech with natural glottal dynamics & prosody)
2. Class 1: NON_HUMAN (Synthetic voices, TTS, altered audio from aabdurazzoq/human-and-nonhuman-voices)
3. Class 2: VOICE_CLONING_ATTACK (High-threat targeted generative AI voice clones & vocoder deepfakes)

Outputs: data/unified_3class_cached_features.npz
"""

import os
import sys
import glob
import time
import argparse
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.audio_processor import load_audio, voice_activity_filter
from core.feature_extraction import extract_temporal_feature_matrix


DATA_DIR = os.path.join(PROJECT_ROOT, "data")
KAGGLE_DATASET_DIR = os.path.join(
    os.path.expanduser("~"),
    ".cache", "kagglehub", "datasets",
    "aabdurazzoq", "human-and-nonhuman-voices", "versions", "1", "human-nonhuman"
)
DEEPVOICE_CACHE = os.path.join(DATA_DIR, "deepvoice_cached_features.npz")
SYNTH_CACHE = os.path.join(DATA_DIR, "cached_features.npz")
UNIFIED_3CLASS_CACHE = os.path.join(DATA_DIR, "unified_3class_cached_features.npz")


def _process_single_audio_file(args):
    """Worker function to process one audio file and return (feature_matrix, label)."""
    fpath, label = args
    try:
        waveform = load_audio(fpath)
        active_speech = voice_activity_filter(waveform, sr=16000)
        # Ensure at least 1 second of active speech
        if len(active_speech) < 16000:
            if len(waveform) >= 16000:
                active_speech = waveform
            else:
                repeats = int(np.ceil(24000 / max(len(waveform), 1)))
                active_speech = np.tile(waveform, repeats)[:24000]

        feat = extract_temporal_feature_matrix(active_speech, sr=16000, target_frames=100)
        return feat, label, None
    except Exception as e:
        return None, label, str(e)


def process_audio_directory(folder_path: str, label: int, max_samples: int = None, max_workers: int = 12):
    """Processes a directory of MP3/WAV files in parallel."""
    files = sorted(glob.glob(os.path.join(folder_path, "*.mp3")) + glob.glob(os.path.join(folder_path, "*.wav")))
    if max_samples and len(files) > max_samples:
        files = files[:max_samples]

    print(f"  [>] Processing {len(files)} files from {folder_path} (Class {label})...")
    tasks = [(f, label) for f in files]
    features, labels = [], []
    errors = 0

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_process_single_audio_file, t) for t in tasks]
        for idx, fut in enumerate(as_completed(futures), start=1):
            feat, lbl, err = fut.result()
            if feat is not None:
                features.append(feat)
                labels.append(lbl)
            else:
                errors += 1
            if idx % 200 == 0 or idx == len(tasks):
                print(f"      Progress: {idx}/{len(tasks)} processed ({len(features)} valid, {errors} errors)")

    return np.array(features, dtype=np.float32), np.array(labels, dtype=np.int64)


def build_unified_3class_dataset(max_per_category: int = 850, max_workers: int = 12):
    print("=" * 80)
    print("🚀 INGESTING & BUILDING MASTER 3-CLASS VOICE INTEGRITY DATASET")
    print("   Class 0: HUMAN")
    print("   Class 1: NON_HUMAN (Synthetic / TTS / Altered)")
    print("   Class 2: VOICE_CLONING_ATTACK (High-Threat Deepfake Voice Impersonation)")
    print("=" * 80)

    # 1. Ingest Kaggle human-and-nonhuman-voices
    human_dir = os.path.join(KAGGLE_DATASET_DIR, "human")
    nonhuman_dir = os.path.join(KAGGLE_DATASET_DIR, "nonhuman")

    if not os.path.exists(human_dir) or not os.path.exists(nonhuman_dir):
        raise FileNotFoundError(f"Kaggle human-nonhuman directories not found at {KAGGLE_DATASET_DIR}")

    t0 = time.time()
    # Process Class 0 (Human) from Kaggle
    X_k_human, y_k_human = process_audio_directory(human_dir, label=0, max_samples=max_per_category, max_workers=max_workers)
    # Process Class 1 (Non-Human) from Kaggle
    X_k_nonhuman, y_k_nonhuman = process_audio_directory(nonhuman_dir, label=1, max_samples=max_per_category, max_workers=max_workers)

    # 2. Ingest Existing DEEP-VOICE Cached Dataset
    print("\n  [>] Loading Kaggle DEEP-VOICE benchmark cache...")
    d_dv = np.load(DEEPVOICE_CACHE)
    X_dv, y_dv = d_dv["X"], d_dv["y"]
    # DEEP-VOICE: 0 was Real (Human -> Class 0), 1 was Fake (Cloned Impersonation -> Class 2)
    mask_dv_real = (y_dv == 0)
    mask_dv_fake = (y_dv == 1)
    X_dv_human = X_dv[mask_dv_real]
    y_dv_human = np.zeros(len(X_dv_human), dtype=np.int64)
    X_dv_attack = X_dv[mask_dv_fake]
    y_dv_attack = np.full(len(X_dv_attack), 2, dtype=np.int64)
    print(f"      DEEP-VOICE: {len(X_dv_human)} Human samples, {len(X_dv_attack)} Voice Cloning Attack samples")

    # 3. Ingest Diverse Vocoders & Replay Cache
    print("\n  [>] Loading Diverse Vocoders & Acoustic Replay cache...")
    d_syn = np.load(SYNTH_CACHE)
    X_syn, y_syn = d_syn["X"], d_syn["y"]
    mask_syn_real = (y_syn == 0)
    mask_syn_fake = (y_syn == 1)
    X_syn_human = X_syn[mask_syn_real]
    y_syn_human = np.zeros(len(X_syn_human), dtype=np.int64)
    X_syn_attack = X_syn[mask_syn_fake]
    y_syn_attack = np.full(len(X_syn_attack), 2, dtype=np.int64)
    print(f"      Diverse Vocoders: {len(X_syn_human)} Human samples, {len(X_syn_attack)} Voice Cloning Attack samples")

    # 4. Augment Attack Vectors for Class 2 to ensure rich balance
    num_attacks_needed = max(0, len(X_k_nonhuman) - (len(X_dv_attack) + len(X_syn_attack)))
    extra_attacks_X, extra_attacks_y = [], []
    if num_attacks_needed > 0:
        print(f"\n  [>] Augmenting {num_attacks_needed} advanced neural vocoder attack patterns for Class 2...")
        rng = np.random.RandomState(42)
        indices = rng.choice(len(X_dv_attack), size=num_attacks_needed, replace=True)
        for idx in indices:
            base_mat = X_dv_attack[idx].copy()
            noise = rng.normal(0, 0.04, size=base_mat.shape)
            base_mat[:, 26:] = np.clip(base_mat[:, 26:] + noise[:, 26:] * 0.5, 0.0, 1.0)
            extra_attacks_X.append(base_mat)
            extra_attacks_y.append(2)
        extra_attacks_X = np.array(extra_attacks_X, dtype=np.float32)
        extra_attacks_y = np.array(extra_attacks_y, dtype=np.int64)
    else:
        extra_attacks_X = np.empty((0, 100, 32), dtype=np.float32)
        extra_attacks_y = np.empty((0,), dtype=np.int64)

    # 5. Concatenate all 3 classes
    X_all = np.concatenate([
        X_k_human, X_dv_human, X_syn_human,
        X_k_nonhuman,
        X_dv_attack, X_syn_attack, extra_attacks_X
    ], axis=0)

    y_all = np.concatenate([
        y_k_human, y_dv_human, y_syn_human,
        y_k_nonhuman,
        y_dv_attack, y_syn_attack, extra_attacks_y
    ], axis=0)

    # Shuffle dataset
    perm = np.random.RandomState(42).permutation(len(y_all))
    X_all = X_all[perm]
    y_all = y_all[perm]

    # 6. Save cache
    os.makedirs(DATA_DIR, exist_ok=True)
    np.savez_compressed(UNIFIED_3CLASS_CACHE, X=X_all, y=y_all)

    elapsed = time.time() - t0
    c0 = int((y_all == 0).sum())
    c1 = int((y_all == 1).sum())
    c2 = int((y_all == 2).sum())

    print("\n" + "=" * 80)
    print("✅ MASTER 3-CLASS DATASET CREATED SUCCESSFULLY!")
    print(f"   Destination: {UNIFIED_3CLASS_CACHE}")
    print(f"   Total Samples: {len(y_all)} | Shape: {X_all.shape}")
    print(f"   Distribution:")
    print(f"     - Class 0 (HUMAN):                    {c0} ({c0/len(y_all)*100:.1f}%)")
    print(f"     - Class 1 (NON_HUMAN SYNTHETIC):      {c1} ({c1/len(y_all)*100:.1f}%)")
    print(f"     - Class 2 (VOICE CLONING ATTACK):     {c2} ({c2/len(y_all)*100:.1f}%)")
    print(f"   Elapsed Time: {elapsed:.1f}s")
    print("=" * 80)

    return UNIFIED_3CLASS_CACHE


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build unified 3-class voice dataset.")
    parser.add_argument("--max-per-category", type=int, default=850)
    parser.add_argument("--max-workers", type=int, default=12)
    args = parser.parse_args()

    build_unified_3class_dataset(max_per_category=args.max_per_category, max_workers=args.max_workers)
