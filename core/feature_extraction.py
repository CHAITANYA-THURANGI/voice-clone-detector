"""
Multi-Layer Voice Authenticity Feature Extraction Engine.
Extracts:
1. Spectral & Acoustic Forensic Signatures (MFCCs, LFCCs, High-Freq Rolloff, Spectral Flatness, Flux)
2. Prosody & Biometric Microvariations (F0 Pitch Contour, Jitter, Shimmer, Pause/Voiced Ratio)
3. Speaker Acoustic Identity Signatures (Acoustic Centroid / Voiceprint)
"""

import numpy as np
from scipy.signal import get_window
from scipy.fftpack import dct


def frame_signal(signal: np.ndarray, frame_len: int, frame_step: int, winfunc=np.hamming) -> np.ndarray:
    """Splits 1D signal into overlapping windowed frames."""
    sig_len = len(signal)
    if sig_len < frame_len:
        signal = np.pad(signal, (0, frame_len - sig_len), mode="constant")
        sig_len = frame_len

    num_frames = 1 + int(np.floor((sig_len - frame_len) / frame_step))
    indices = (
        np.tile(np.arange(0, frame_len), (num_frames, 1))
        + np.tile(np.arange(0, num_frames * frame_step, frame_step), (frame_len, 1)).T
    )
    frames = signal[indices]
    win = winfunc(frame_len)
    return frames * win


def get_filterbanks(nfilt: int = 26, nfft: int = 512, sr: int = 16000, linear: bool = False) -> np.ndarray:
    """Constructs Mel or Linear triangular filterbanks for spectral analysis."""
    low_freq = 0
    high_freq = sr / 2

    if linear:
        hz_pts = np.linspace(low_freq, high_freq, nfilt + 2)
    else:
        # Mel scale conversion
        def hz_to_mel(hz):
            return 2595 * np.log10(1 + hz / 700.0)

        def mel_to_hz(mel):
            return 700 * (10 ** (mel / 2595.0) - 1)

        low_mel = hz_to_mel(low_freq)
        high_mel = hz_to_mel(high_freq)
        mel_pts = np.linspace(low_mel, high_mel, nfilt + 2)
        hz_pts = mel_to_hz(mel_pts)

    bin_pts = np.floor((nfft + 1) * hz_pts / sr).astype(int)
    bin_pts = np.clip(bin_pts, 0, nfft // 2)

    fbank = np.zeros((nfilt, nfft // 2 + 1))
    for m in range(1, nfilt + 1):
        f_m_minus = bin_pts[m - 1]
        f_m = bin_pts[m]
        f_m_plus = bin_pts[m + 1]

        if f_m > f_m_minus:
            fbank[m - 1, f_m_minus:f_m] = (np.arange(f_m_minus, f_m) - f_m_minus) / (f_m - f_m_minus)
        if f_m_plus > f_m:
            fbank[m - 1, f_m:f_m_plus] = (f_m_plus - np.arange(f_m, f_m_plus)) / (f_m_plus - f_m)

    return fbank


def extract_cepstral_features(frames: np.ndarray, sr: int = 16000, nfft: int = 512, num_ceps: int = 13, linear: bool = False) -> np.ndarray:
    """Computes MFCCs (linear=False) or LFCCs (linear=True) across frames."""
    mag_frames = np.abs(np.fft.rfft(frames, nfft))
    pow_frames = (1.0 / nfft) * (mag_frames ** 2)

    nfilt = 26
    fbanks = get_filterbanks(nfilt=nfilt, nfft=nfft, sr=sr, linear=linear)
    energy = np.dot(pow_frames, fbanks.T)
    energy = np.where(energy == 0, np.finfo(float).eps, energy)
    log_energy = np.log(energy)

    ceps = dct(log_energy, type=2, axis=1, norm="ortho")[:, :num_ceps]
    return ceps


def extract_spectral_descriptors(frames: np.ndarray, sr: int = 16000, nfft: int = 512) -> dict:
    """
    Extracts physical spectral descriptors sensitive to vocoder artifacts:
    - Spectral Centroid (brightness / center of mass)
    - Spectral Rolloff (85% and 95%)
    - Spectral Flatness (measure of noisiness vs tonality)
    - High-Frequency Energy Ratio (>4kHz)
    - Spectral Flux
    """
    mag = np.abs(np.fft.rfft(frames, nfft))  # shape: (frames, nfft//2 + 1)
    freqs = np.fft.rfftfreq(nfft, 1.0 / sr)

    eps = 1e-10
    total_power = np.sum(mag, axis=1, keepdims=True) + eps

    # 1. Spectral Centroid
    centroid = np.sum(mag * freqs, axis=1) / (total_power.squeeze() + eps)

    # 2. Spectral Rolloff (85% and 95%)
    cum_power = np.cumsum(mag, axis=1)
    rolloff_85 = np.zeros(len(frames))
    rolloff_95 = np.zeros(len(frames))
    for i in range(len(frames)):
        t85 = 0.85 * cum_power[i, -1]
        t95 = 0.95 * cum_power[i, -1]
        idx85 = np.where(cum_power[i] >= t85)[0]
        idx95 = np.where(cum_power[i] >= t95)[0]
        rolloff_85[i] = freqs[idx85[0]] if len(idx85) > 0 else freqs[-1]
        rolloff_95[i] = freqs[idx95[0]] if len(idx95) > 0 else freqs[-1]

    # 3. Spectral Flatness (Geometric Mean / Arithmetic Mean)
    geom_mean = np.exp(np.mean(np.log(mag + eps), axis=1))
    arith_mean = np.mean(mag, axis=1) + eps
    flatness = geom_mean / arith_mean

    # 4. High-Frequency Energy Ratio (> 4000 Hz)
    high_freq_mask = freqs >= 4000.0
    hf_energy = np.sum(mag[:, high_freq_mask] ** 2, axis=1)
    total_energy = np.sum(mag ** 2, axis=1) + eps
    hf_ratio = hf_energy / total_energy

    # 5. Spectral Flux
    flux = np.zeros(len(frames))
    if len(frames) > 1:
        diff = np.diff(mag, axis=0)
        flux[1:] = np.sqrt(np.mean(diff ** 2, axis=1))

    return {
        "centroid": centroid,
        "rolloff_85": rolloff_85,
        "rolloff_95": rolloff_95,
        "flatness": flatness,
        "hf_ratio": hf_ratio,
        "flux": flux
    }


def estimate_f0_and_prosody(waveform: np.ndarray, sr: int = 16000, frame_len: int = 512, frame_step: int = 256) -> dict:
    """
    Estimates Fundamental Frequency (F0) using Autocorrelation Method
    and computes biometric micro-perturbations:
    - Jitter (pitch perturbation)
    - Shimmer (amplitude perturbation)
    - Pitch dynamics (Mean, Std, Range)
    - Voiced / Unvoiced ratio
    """
    frames = frame_signal(waveform, frame_len, frame_step, winfunc=np.hamming)
    min_lag = int(sr / 450)  # 450 Hz max human pitch
    max_lag = int(sr / 65)   # 65 Hz min human pitch

    f0_list = []
    energy_list = []
    voiced_flags = []

    for frame in frames:
        energy = np.sqrt(np.mean(frame ** 2))
        energy_list.append(energy)

        # Autocorrelation
        corr = np.correlate(frame, frame, mode="full")
        corr = corr[len(corr) // 2:]

        if energy > 0.01 and max_lag < len(corr):
            sub_corr = corr[min_lag:max_lag]
            peak_idx = np.argmax(sub_corr) + min_lag
            peak_val = corr[peak_idx]
            r0 = corr[0] + 1e-8

            if (peak_val / r0) > 0.35:  # Voiced frame threshold
                pitch = sr / peak_idx
                f0_list.append(pitch)
                voiced_flags.append(True)
            else:
                f0_list.append(0.0)
                voiced_flags.append(False)
        else:
            f0_list.append(0.0)
            voiced_flags.append(False)

    f0_arr = np.array(f0_list)
    voiced_f0 = f0_arr[f0_arr > 0]

    # Pitch statistics
    f0_mean = float(np.mean(voiced_f0)) if len(voiced_f0) > 0 else 0.0
    f0_std = float(np.std(voiced_f0)) if len(voiced_f0) > 0 else 0.0
    f0_min = float(np.min(voiced_f0)) if len(voiced_f0) > 0 else 0.0
    f0_max = float(np.max(voiced_f0)) if len(voiced_f0) > 0 else 0.0
    f0_range = f0_max - f0_min

    # Voiced frame ratio
    voiced_ratio = float(np.mean(voiced_flags)) if len(voiced_flags) > 0 else 0.0

    # Jitter: Relative cycle-to-cycle F0 perturbation
    if len(voiced_f0) > 3:
        periods = 1.0 / voiced_f0
        diff_periods = np.abs(np.diff(periods))
        jitter_local = float(np.mean(diff_periods) / (np.mean(periods) + 1e-8))
    else:
        jitter_local = 0.0

    # Shimmer: Relative cycle-to-cycle amplitude perturbation
    voiced_energies = np.array(energy_list)[np.array(voiced_flags)]
    if len(voiced_energies) > 3:
        diff_energies = np.abs(np.diff(voiced_energies))
        shimmer_local = float(np.mean(diff_energies) / (np.mean(voiced_energies) + 1e-8))
    else:
        shimmer_local = 0.0

    return {
        "f0_contour": f0_arr,
        "f0_mean": f0_mean,
        "f0_std": f0_std,
        "f0_range": f0_range,
        "voiced_ratio": voiced_ratio,
        "jitter": jitter_local,
        "shimmer": shimmer_local
    }


def extract_temporal_feature_matrix(waveform: np.ndarray, sr: int = 16000, target_frames: int = 100) -> np.ndarray:
    """
    Extracts time-series feature matrix of shape (target_frames, feature_dim)
    for sequence-based Deep Neural Network input.
    Each frame contains:
    - 13 MFCCs
    - 13 LFCCs
    - 6 Spectral Descriptors (Centroid, Rolloff85, Rolloff95, Flatness, HF-Ratio, Flux)
    Total feature dimension per frame = 32.
    """
    frame_len = 512
    frame_step = 256
    frames = frame_signal(waveform, frame_len, frame_step)

    mfccs = extract_cepstral_features(frames, sr, frame_len, num_ceps=13, linear=False)
    lfccs = extract_cepstral_features(frames, sr, frame_len, num_ceps=13, linear=True)
    spectral = extract_spectral_descriptors(frames, sr, frame_len)

    spec_matrix = np.column_stack([
        spectral["centroid"] / 8000.0,
        spectral["rolloff_85"] / 8000.0,
        spectral["rolloff_95"] / 8000.0,
        spectral["flatness"],
        spectral["hf_ratio"],
        spectral["flux"]
    ])

    combined = np.hstack([mfccs, lfccs, spec_matrix])  # shape: (num_frames, 32)

    # Normalize or interpolate to fixed sequence length (target_frames)
    current_frames = len(combined)
    if current_frames == 0:
        return np.zeros((target_frames, 32), dtype=np.float32)

    if current_frames < target_frames:
        pad_width = target_frames - current_frames
        combined = np.pad(combined, ((0, pad_width), (0, 0)), mode="edge")
    elif current_frames > target_frames:
        indices = np.linspace(0, current_frames - 1, target_frames).astype(int)
        combined = combined[indices]

    return combined.astype(np.float32)


def extract_forensic_summary(waveform: np.ndarray, sr: int = 16000) -> dict:
    """
    Extracts comprehensive forensic metrics and a 78-dimensional summary vector
    used by the fusion risk engine and baseline classifiers.
    """
    frame_len = 512
    frame_step = 256
    frames = frame_signal(waveform, frame_len, frame_step)

    mfccs = extract_cepstral_features(frames, sr, frame_len, num_ceps=13, linear=False)
    lfccs = extract_cepstral_features(frames, sr, frame_len, num_ceps=13, linear=True)
    spec = extract_spectral_descriptors(frames, sr, frame_len)
    prosody = estimate_f0_and_prosody(waveform, sr, frame_len, frame_step)

    # Mean and standard deviation across frames
    mfcc_mean, mfcc_std = np.mean(mfccs, axis=0), np.std(mfccs, axis=0)
    lfcc_mean, lfcc_std = np.mean(lfccs, axis=0), np.std(lfccs, axis=0)

    centroid_mean, centroid_std = float(np.mean(spec["centroid"])), float(np.std(spec["centroid"]))
    rolloff_mean = float(np.mean(spec["rolloff_85"]))
    flatness_mean, flatness_std = float(np.mean(spec["flatness"])), float(np.std(spec["flatness"]))
    hf_mean, hf_std = float(np.mean(spec["hf_ratio"])), float(np.std(spec["hf_ratio"]))
    flux_mean = float(np.mean(spec["flux"]))

    # 78-dimensional feature vector:
    # 26 (MFCC mean+std) + 26 (LFCC mean+std) + 12 (Spectral stats) + 7 (Prosody stats) + 7 padding/extra
    vector = np.concatenate([
        mfcc_mean, mfcc_std,
        lfcc_mean, lfcc_std,
        [centroid_mean / 8000.0, centroid_std / 8000.0,
         rolloff_mean / 8000.0,
         flatness_mean, flatness_std,
         hf_mean, hf_std,
         flux_mean],
        [prosody["f0_mean"] / 400.0,
         prosody["f0_std"] / 200.0,
         prosody["f0_range"] / 400.0,
         prosody["voiced_ratio"],
         prosody["jitter"],
         prosody["shimmer"]],
        np.zeros(12)  # Reserved for speaker embeddings / future extensions
    ])[:78].astype(np.float32)

    return {
        "vector": vector,
        "metrics": {
            "f0_mean_hz": round(prosody["f0_mean"], 2),
            "f0_std_hz": round(prosody["f0_std"], 2),
            "f0_range_hz": round(prosody["f0_range"], 2),
            "jitter": round(prosody["jitter"] * 100, 3),      # in percent
            "shimmer": round(prosody["shimmer"] * 100, 3),    # in percent
            "voiced_ratio": round(prosody["voiced_ratio"], 3),
            "spectral_centroid_hz": round(centroid_mean, 1),
            "spectral_rolloff_hz": round(rolloff_mean, 1),
            "spectral_flatness": round(flatness_mean, 5),
            "hf_energy_ratio": round(hf_mean, 4),
            "spectral_flux": round(flux_mean, 4)
        }
    }
