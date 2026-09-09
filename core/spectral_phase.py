"""
Phase-Aware Spectral Forensics & Modified Group Delay (MGD) Engine.
Exploits fundamental phase inconsistencies, sub-band instantaneous frequency jitter,
and vocoder phase reconstruction artifacts typical of diffusion & neural speech synthesizers.
"""

import numpy as np


def compute_modified_group_delay(frame: np.ndarray, nfft: int = 512, alpha: float = 0.4, gamma: float = 0.9) -> np.ndarray:
    """
    Computes the Modified Group Delay (MGD) spectrum of a speech frame:
    tau(omega) = Re( X*(omega) * Y(omega) ) / |X(omega)|^(2 * gamma)
    where Y(omega) = FFT( n * x[n] )
    MGD provides high-resolution vocal tract formant peaks while exposing phase smearing.
    """
    N = len(frame)
    if N < 64:
        return np.zeros(nfft // 2 + 1)

    # Time-weighted signal n * x[n]
    n_seq = np.arange(N)
    time_weighted = n_seq * frame

    # FFTs of original and time-weighted signals
    X = np.fft.rfft(frame, nfft)
    Y = np.fft.rfft(time_weighted, nfft)

    # Cross-spectral product
    cross = np.real(X) * np.real(Y) + np.imag(X) * np.imag(Y)
    mag_X = np.abs(X) + 1e-10

    # Modified Group Delay calculation with non-linear scaling
    mgd = cross / (mag_X ** (2 * gamma))
    # Sign-preserving dynamic range compression
    mgd = np.sign(mgd) * (np.abs(mgd) ** alpha)

    return mgd


def analyze_phase_coherence(waveform: np.ndarray, sr: int = 16000, nfft: int = 512) -> dict:
    """
    Analyzes phase derivative continuity and vocoder group delay dispersion.
    Returns:
    - phase_incoherence_score: 0.0 (High continuity, authentic) to 1.0 (Phase artifact, synthetic)
    - mgd_variance: Group delay spread across frequency bins
    - high_freq_phase_jitter: Micro-jitter in upper 4kHz-8kHz phase bands
    """
    frame_len = 512
    step_len = 256

    if len(waveform) < frame_len:
        return {
            "phase_incoherence_score": 0.2,
            "mgd_variance": 0.05,
            "high_freq_phase_jitter": 0.02,
            "status": "AUTHENTIC_PHASE_CONTINUITY"
        }

    num_frames = (len(waveform) - frame_len) // step_len + 1
    mgd_profiles = []
    hf_phase_diffs = []

    win = np.hanning(frame_len)

    for i in range(min(num_frames, 60)):  # Analyze up to 60 representative frames
        start = i * step_len
        frame = waveform[start:start + frame_len] * win

        if np.sum(frame ** 2) < 1e-4:
            continue

        mgd = compute_modified_group_delay(frame, nfft=nfft)
        mgd_profiles.append(mgd)

        # High-frequency phase derivative analysis (> 4kHz)
        X = np.fft.rfft(frame, nfft)
        unwrapped_phase = np.unwrap(np.angle(X))
        hf_phase = unwrapped_phase[len(unwrapped_phase) // 2:]  # Upper half (>4kHz)
        if len(hf_phase) > 2:
            second_diff = np.diff(np.diff(hf_phase))
            hf_phase_diffs.append(np.std(second_diff))

    if not mgd_profiles:
        return {
            "phase_incoherence_score": 0.2,
            "mgd_variance": 0.05,
            "high_freq_phase_jitter": 0.02,
            "status": "AUTHENTIC_PHASE_CONTINUITY"
        }

    mgd_arr = np.array(mgd_profiles)
    mgd_var = float(np.mean(np.var(mgd_arr, axis=0)))
    hf_jitter = float(np.mean(hf_phase_diffs)) if hf_phase_diffs else 0.0

    # Neural vocoders (HiFi-GAN, WaveGlow, Diffusion) produce distinctive
    # high-frequency group delay spikes and phase derivative dispersion
    phase_incoherence = 0.0
    if hf_jitter > 3.2:
        phase_incoherence += 0.45
    elif hf_jitter > 1.8:
        phase_incoherence += 0.20

    if mgd_var > 0.35 or mgd_var < 0.001:
        phase_incoherence += 0.30

    phase_incoherence = min(1.0, phase_incoherence)

    return {
        "phase_incoherence_score": round(phase_incoherence, 4),
        "mgd_variance": round(mgd_var, 4),
        "high_freq_phase_jitter": round(hf_jitter, 4),
        "status": "AUTHENTIC_PHASE_CONTINUITY" if phase_incoherence < 0.40 else "VOCODER_PHASE_DISPERSION"
    }
