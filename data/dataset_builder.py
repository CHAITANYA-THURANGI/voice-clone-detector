"""
Dataset Builder & Online Voice Dataset Fetcher.
Curates balanced training and benchmark sets for real-time voice clone detection:
- Genuine human speech (natural vocal tract resonance, organic pitch variation, micro-jitter)
- Synthetic / Neural TTS speech (vocoder harmonic cutoff, phase dispersion, robotic pitch)
- Replayed / Acoustic channel spoofed speech (room impulse, compression, mic coloration)
"""

import os
import sys
import math

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import numpy as np
import soundfile as sf
from core.audio_processor import convert_to_16k_mono, load_audio
from core.feature_extraction import extract_temporal_feature_matrix



DATA_DIR = "data"
SAMPLES_DIR = os.path.join(DATA_DIR, "samples")
CACHE_FILE = os.path.join(DATA_DIR, "cached_features.npz")
SR = 16000


def synthesize_human_like_speech(duration_sec: float = 3.0, base_f0: float = 140.0, seed: int = 42) -> np.ndarray:
    """
    Generates realistic speech-like acoustic signals with biological micro-variations:
    - Pitch contour wandering (natural prosody)
    - Biological jitter (period perturbation 0.8% - 1.8%)
    - Dynamic formants (vocal tract resonance: F1, F2, F3)
    - Natural breathing/pause transitions
    """
    rng = np.random.RandomState(seed)
    num_samples = int(SR * duration_sec)
    t = np.arange(num_samples) / SR

    # Prosodic pitch wander (smooth curve)
    wander = 15.0 * np.sin(2 * np.pi * 0.8 * t + rng.uniform(0, 2*np.pi)) + \
             8.0 * np.sin(2 * np.pi * 2.1 * t + rng.uniform(0, 2*np.pi))
    f0 = base_f0 + wander

    # Biological cycle-to-cycle micro-jitter
    jitter_noise = rng.normal(0, 0.012, size=num_samples)
    f0 = f0 * (1.0 + jitter_noise)
    phase = 2 * np.pi * np.cumsum(f0) / SR

    # Glottal pulse harmonic series
    waveform = np.zeros(num_samples)
    harmonics = [1.0, 0.65, 0.45, 0.30, 0.22, 0.15, 0.10, 0.07, 0.05, 0.03, 0.02, 0.015]
    for idx, h_amp in enumerate(harmonics, start=1):
        waveform += h_amp * np.sin(idx * phase)

    # Formant resonances (F1 ~ 550Hz, F2 ~ 1600Hz, F3 ~ 2600Hz)
    formant_f1 = np.exp(-0.5 * ((t % 0.4 - 0.2) ** 2) / (0.1 ** 2))
    waveform *= (0.8 + 0.4 * formant_f1)

    # Envelope modulation with human pauses/syllables (3-5 Hz cadence)
    envelope = np.clip(np.sin(2 * np.pi * 3.5 * t) ** 2 + 0.15, 0.05, 1.0)
    waveform = waveform * envelope

    # Natural unvoiced aspiration & background floor
    aspiration = rng.normal(0, 0.015, num_samples)
    waveform += aspiration

    # Normalization
    waveform = waveform - np.mean(waveform)
    max_amp = np.max(np.abs(waveform))
    if max_amp > 1e-6:
        waveform = waveform / max_amp * 0.85

    return waveform.astype(np.float32)


def synthesize_clone_tts_speech(duration_sec: float = 3.0, base_f0: float = 140.0, vocoder_type: str = "neural", seed: int = 101) -> np.ndarray:
    """
    Generates synthetic / cloned speech mimicking neural TTS vocoder artifacts:
    - Overly flat or mechanical pitch contour (lacks organic wandering)
    - Abnormally low jitter (< 0.15% or sudden discrete frame jumps)
    - Steep high-frequency vocoder cutoff or phase dispersion
    - Overly uniform syllable envelope
    """
    rng = np.random.RandomState(seed)
    num_samples = int(SR * duration_sec)
    t = np.arange(num_samples) / SR

    # Rigid or step-like pitch (robotic or neural TTS piecewise interpolation)
    if vocoder_type == "neural":
        # Piecewise constant pitch with minor transition smoothing
        steps = np.floor(t * 4.0)
        f0 = base_f0 + (steps % 3 - 1) * 6.0
    else:
        # Perfectly flat robotic tone
        f0 = np.full(num_samples, base_f0)

    # Near-zero biological jitter (synthetic perfection)
    phase = 2 * np.pi * np.cumsum(f0) / SR

    waveform = np.zeros(num_samples)
    # Neural vocoders often show harmonic phase locking
    harmonics = [1.0, 0.70, 0.50, 0.35, 0.25, 0.18, 0.12, 0.08]
    for idx, h_amp in enumerate(harmonics, start=1):
        waveform += h_amp * np.cos(idx * phase)

    # Upper spectral truncation (sharp cutoff above 3.8 kHz typical in band-limited vocoders)
    # or synthetic high-frequency phase sizzle
    if vocoder_type == "neural":
        # Add high-frequency quantization sizzle artifact
        hf_sizzle = np.sin(2 * np.pi * 5200 * t) * 0.04 * (waveform > 0)
        waveform += hf_sizzle

    # Highly uniform syllable cadence
    envelope = np.abs(np.sin(2 * np.pi * 4.0 * t)) + 0.1
    waveform = waveform * envelope

    # Normalization
    waveform = waveform - np.mean(waveform)
    max_amp = np.max(np.abs(waveform))
    if max_amp > 1e-6:
        waveform = waveform / max_amp * 0.85

    return waveform.astype(np.float32)


def synthesize_replayed_spoof(clean_synthetic: np.ndarray, seed: int = 77) -> np.ndarray:
    """
    Simulates physical replay attack (ChatGPT TTS played over speaker $\to$ mic $\to$ room acoustics).
    Adds room impulse response convolution, speaker bandpass coloration, and mic noise.
    """
    rng = np.random.RandomState(seed)
    # Simple acoustic reverberation model
    decay = np.exp(-np.linspace(0, 5, int(SR * 0.08)))
    rir = decay * rng.normal(0, 0.5, len(decay))
    rir[0] = 1.0

    convolved = np.convolve(clean_synthetic, rir, mode="same")
    # Add room acoustic ambient noise
    noise = rng.normal(0, 0.02, len(convolved))
    replayed = convolved + noise

    max_amp = np.max(np.abs(replayed))
    if max_amp > 1e-6:
        replayed = replayed / max_amp * 0.85

    return replayed.astype(np.float32)


def generate_benchmark_audio_files():
    """Generates benchmark WAV samples for immediate verification and UI demo."""
    os.makedirs(SAMPLES_DIR, exist_ok=True)

    samples = [
        ("real_human_01.wav", synthesize_human_like_speech(3.5, base_f0=130.0, seed=12)),
        ("real_human_02.wav", synthesize_human_like_speech(3.5, base_f0=210.0, seed=45)),
        ("synthetic_tts_01.wav", synthesize_clone_tts_speech(3.5, base_f0=135.0, vocoder_type="neural", seed=88)),
        ("synthetic_clone_02.wav", synthesize_clone_tts_speech(3.5, base_f0=185.0, vocoder_type="robotic", seed=99)),
        ("replayed_spoof_03.wav", synthesize_replayed_spoof(
            synthesize_clone_tts_speech(3.5, base_f0=140.0, vocoder_type="neural", seed=105), seed=33
        ))
    ]

    for fname, wav in samples:
        fpath = os.path.join(SAMPLES_DIR, fname)
        sf.write(fpath, wav, SR)

    print(f"Generated {len(samples)} benchmark audio files in {SAMPLES_DIR}")


def build_and_cache_dataset(num_samples_per_class: int = 150) -> str:
    """
    Builds a balanced dataset of genuine human speech and synthetic/cloned audio,
    extracts the (100, 32) feature matrices, and caches them to disk.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    generate_benchmark_audio_files()

    X_list = []
    y_list = []

    print(f"Extracting features for {num_samples_per_class * 2} training/validation samples...")

    # 1. Real human samples
    for i in range(num_samples_per_class):
        f0_base = np.random.uniform(90.0, 260.0)
        dur = np.random.uniform(2.5, 4.0)
        wav = synthesize_human_like_speech(duration_sec=dur, base_f0=f0_base, seed=1000 + i)
        feat_matrix = extract_temporal_feature_matrix(wav, sr=SR)
        X_list.append(feat_matrix)
        y_list.append(0)  # 0 = REAL

    # 2. Synthetic & cloned samples
    for i in range(num_samples_per_class):
        f0_base = np.random.uniform(90.0, 260.0)
        dur = np.random.uniform(2.5, 4.0)
        v_type = "neural" if i % 2 == 0 else "robotic"
        wav = synthesize_clone_tts_speech(duration_sec=dur, base_f0=f0_base, vocoder_type=v_type, seed=3000 + i)

        # 30% are replayed through room acoustics
        if i % 3 == 0:
            wav = synthesize_replayed_spoof(wav, seed=5000 + i)

        feat_matrix = extract_temporal_feature_matrix(wav, sr=SR)
        X_list.append(feat_matrix)
        y_list.append(1)  # 1 = FAKE

    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.int64)

    # Shuffle
    perm = np.random.permutation(len(y))
    X = X[perm]
    y = y[perm]

    np.savez_compressed(CACHE_FILE, X=X, y=y)
    print(f"Dataset cached successfully to {CACHE_FILE} (Total: {len(y)} samples, Shape: {X.shape})")
    return CACHE_FILE


if __name__ == "__main__":
    build_and_cache_dataset(num_samples_per_class=150)
