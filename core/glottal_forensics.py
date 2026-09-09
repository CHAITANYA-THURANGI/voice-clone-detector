"""
Biometric Glottal Inverse Filtering & Vocal Tract Residual Forensics.
Simulates physiological speech production physics using Levinson-Durbin
Linear Predictive Coding (LPC) inverse filtering to expose synthetic vocal tract violations.
"""

import numpy as np
from scipy.signal import lfilter


def levinson_durbin(r: np.ndarray, order: int = 16) -> np.ndarray:
    """
    Solves the Yule-Walker equations via Levinson-Durbin recursion
    to obtain the optimal all-pole vocal tract filter coefficients.
    """
    a = np.zeros(order + 1)
    e = r[0]
    a[0] = 1.0

    for i in range(1, order + 1):
        if e <= 1e-12:
            break
        # Compute reflection coefficient k_i
        k = -np.dot(a[:i], r[1:i + 1][::-1]) / e
        if np.abs(k) >= 1.0:
            k = np.sign(k) * 0.999

        a[i] = k
        a[1:i] = a[1:i] + k * a[1:i][::-1]
        e = e * (1.0 - k ** 2)

    return a


def compute_lpc_residual(signal: np.ndarray, order: int = 16) -> np.ndarray:
    """
    Applies inverse filtering to extract the Glottal Flow Derivative Residual e[n].
    e[n] represents the raw biological vocal fold excitation driving the vocal tract.
    """
    if len(signal) < order * 2:
        return np.zeros_like(signal)

    # Frame autocorrelation
    autocorr = np.correlate(signal, signal, mode="full")
    r = autocorr[len(signal) - 1: len(signal) + order]

    if r[0] < 1e-8:
        return np.zeros_like(signal)

    # Calculate LPC coefficients via Levinson-Durbin
    lpc_coeffs = levinson_durbin(r, order=order)

    # Inverse filter: e[n] = s[n] * A(z)
    residual = lfilter(lpc_coeffs, [1.0], signal)
    return residual


def analyze_glottal_biometrics(waveform: np.ndarray, sr: int = 16000, lpc_order: int = 16) -> dict:
    """
    Extracts higher-order glottal statistical moments:
    - Residual Kurtosis: measures peakedness of vocal fold closure impulses
    - Residual Skewness: measures glottal opening/closing pulse asymmetry
    - Normalized Residual Energy (NRE): ratio of unpredicted excitation energy
    - Glottal Anomaly Index: composite 0.0 to 1.0 spoof score
    """
    frame_size = int(sr * 0.030)  # 30 ms frame
    step_size = int(sr * 0.015)   # 15 ms step

    if len(waveform) < frame_size:
        return {
            "residual_kurtosis": 3.0,
            "residual_skewness": 0.0,
            "normalized_residual_energy": 0.1,
            "glottal_anomaly_score": 0.5,
            "waveform_preview": []
        }

    kurtosis_list = []
    skewness_list = []
    nre_list = []
    preview_samples = []

    num_frames = (len(waveform) - frame_size) // step_size + 1
    for i in range(num_frames):
        start = i * step_size
        frame = waveform[start:start + frame_size]

        frame_energy = np.sum(frame ** 2)
        if frame_energy < 1e-4:
            continue

        res = compute_lpc_residual(frame, order=lpc_order)
        res_energy = np.sum(res ** 2)

        # Statistical Moments of Residual
        mean_res = np.mean(res)
        std_res = np.std(res) + 1e-8
        normalized = (res - mean_res) / std_res

        kurt = np.mean(normalized ** 4)  # Normal Gaussian = 3.0
        skew = np.mean(normalized ** 3)
        nre = res_energy / (frame_energy + 1e-8)

        kurtosis_list.append(kurt)
        skewness_list.append(skew)
        nre_list.append(nre)

        if len(preview_samples) < 150:
            preview_samples.extend(res[:10].tolist())

    if not kurtosis_list:
        return {
            "residual_kurtosis": 3.0,
            "residual_skewness": 0.0,
            "normalized_residual_energy": 0.1,
            "glottal_anomaly_score": 0.5,
            "waveform_preview": []
        }

    mean_kurt = float(np.mean(kurtosis_list))
    mean_skew = float(np.mean(np.abs(skewness_list)))
    mean_nre = float(np.mean(nre_list))

    # Biological Evaluation:
    # Genuine Human Speech: high impulse peakedness (Kurtosis typically 5.5 - 18.0)
    # Neural TTS / Vocoders: dispersed or artificially smoothed (Kurtosis < 4.8 or > 35.0)
    glottal_anomaly = 0.0

    if mean_kurt < 4.2:
        glottal_anomaly += 0.45  # Typical of overly smoothed neural vocoder speech
    elif mean_kurt > 110.0:
        glottal_anomaly += 0.35  # Glitched vocoder boundaries

    if mean_nre > 0.50 or mean_nre < 0.005:
        glottal_anomaly += 0.30

    if mean_skew < 0.08:
        glottal_anomaly += 0.25  # Lack of natural biological opening/closing pulse asymmetry

    glottal_anomaly = min(1.0, glottal_anomaly)

    return {
        "residual_kurtosis": round(mean_kurt, 2),
        "residual_skewness": round(mean_skew, 3),
        "normalized_residual_energy": round(mean_nre, 4),
        "glottal_anomaly_score": round(glottal_anomaly, 4),
        "glottal_status": "AUTHENTIC_GLOTTAL_IMPULSE" if glottal_anomaly < 0.40 else "SYNTHETIC_VOCAL_TRACT_VIOLATION",
        "waveform_preview": preview_samples[:100]
    }
