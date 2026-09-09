"""
VoiceShield AI - Portable Client & Model Integration Wrapper.
Designed for zero-friction integration into external systems, pipelines, or partner models.

Supports TWO backends:
1. 'onnx' (RECOMMENDED): Requires only `pip install onnxruntime soundfile numpy scipy` (No PyTorch needed!)
2. 'torch': Requires `pip install torch soundfile numpy scipy`

Usage Example:
--------------
    from voiceshield_client import VoiceCloneDetector

    detector = VoiceCloneDetector(model_format='onnx')
    result = detector.predict("incoming_call.wav")

    print(result["prediction"])         # "REAL" or "FAKE"
    print(result["fake_probability"])   # e.g. 0.998
    print(result["risk_level"])         # "LOW", "SUSPICIOUS", or "HIGH"
"""

import os
import numpy as np
import soundfile as sf
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
    """Extracts physical spectral descriptors: Centroid, Rolloff, Flatness, HF Energy Ratio, Flux."""
    mag = np.abs(np.fft.rfft(frames, nfft))
    freqs = np.fft.rfftfreq(nfft, 1.0 / sr)

    eps = 1e-10
    total_power = np.sum(mag, axis=1, keepdims=True) + eps

    centroid = np.sum(mag * freqs, axis=1) / (total_power.squeeze() + eps)

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

    log_mag = np.log(mag + eps)
    geom_mean = np.exp(np.mean(log_mag, axis=1))
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


def extract_temporal_feature_matrix(waveform: np.ndarray, sr: int = 16000, target_frames: int = 100) -> np.ndarray:
    """
    Extracts the exact standardized 32-dimensional feature matrix across 100 time frames
    matching the trained Enterprise Voice Conformer model.
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

    combined = np.hstack([mfccs, lfccs, spec_matrix])

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


def voice_activity_filter(waveform: np.ndarray, sr: int = 16000, frame_ms: int = 30, energy_threshold: float = 0.005) -> np.ndarray:
    """Fast energy-based Voice Activity Detection (VAD) to eliminate silence."""
    frame_len = int(sr * (frame_ms / 1000.0))
    if len(waveform) < frame_len:
        return waveform

    num_frames = len(waveform) // frame_len
    active_frames = []
    for i in range(num_frames):
        chunk = waveform[i * frame_len : (i + 1) * frame_len]
        energy = np.sqrt(np.mean(chunk ** 2))
        if energy > energy_threshold:
            active_frames.append(chunk)

    if not active_frames:
        return waveform
    return np.concatenate(active_frames)


class VoiceCloneDetector:
    """
    Portable Voice Deepfake & Clone Detector.
    Wraps feature extraction and inference into a single clean Python interface.
    """

    def __init__(self, model_format: str = "onnx", model_path: str = None):
        """
        Args:
            model_format: 'onnx' (default, lightweight) or 'torch' (uses TorchScript .pt).
            model_path: Optional custom path to model file. If None, auto-locates in current directory.
        """
        self.format = model_format.lower()
        base_dir = os.path.dirname(os.path.abspath(__file__))

        if self.format == "onnx":
            import onnxruntime as ort
            self.model_path = model_path or os.path.join(base_dir, "voiceshield_conformer.onnx")
            if not os.path.exists(self.model_path):
                raise FileNotFoundError(f"ONNX model file not found at: {self.model_path}")
            self.session = ort.InferenceSession(self.model_path, providers=["CPUExecutionProvider"])
            self.input_name = self.session.get_inputs()[0].name
        elif self.format == "torch":
            import torch
            self.torch = torch
            self.model_path = model_path or os.path.join(base_dir, "voiceshield_conformer.pt")
            if not os.path.exists(self.model_path):
                raise FileNotFoundError(f"TorchScript model file not found at: {self.model_path}")
            self.model = torch.jit.load(self.model_path)
            self.model.eval()
        else:
            raise ValueError("model_format must be either 'onnx' or 'torch'")

    @staticmethod
    def load_and_preprocess_audio(audio_input, target_sr: int = 16000) -> np.ndarray:
        """
        Accepts file path (str) or raw 1D numpy array.
        Normalizes, resamples to 16kHz mono float32, and runs VAD filter.
        """
        if isinstance(audio_input, str):
            try:
                data, sr = sf.read(audio_input, dtype="float32")
            except Exception:
                # Universal fallback for MPEG, MPG, MP4, AAC via FFmpeg
                import subprocess
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_out:
                    tmp_wav = tmp_out.name
                try:
                    cmd = ["ffmpeg", "-y", "-i", str(audio_input), "-vn", "-ar", str(target_sr), "-ac", "1", "-c:a", "pcm_s16le", tmp_wav]
                    subprocess.run(cmd, capture_output=True, check=True)
                    data, sr = sf.read(tmp_wav, dtype="float32")
                finally:
                    if os.path.exists(tmp_wav):
                        os.remove(tmp_wav)
        elif isinstance(audio_input, np.ndarray):
            data = audio_input.astype(np.float32)
            sr = target_sr
        else:
            raise TypeError("audio_input must be a file path string or numpy array.")

        if data.ndim > 1:
            data = np.mean(data, axis=1)

        # Simple linear resample if sample rate does not match 16kHz
        if sr != target_sr:
            ratio = float(target_sr) / sr
            new_len = int(round(len(data) * ratio))
            data = np.interp(np.linspace(0, len(data), new_len, endpoint=False), np.arange(len(data)), data)

        # DC offset removal & peak normalization
        data = data - np.mean(data)
        max_val = np.max(np.abs(data))
        if max_val > 1e-6:
            data = data / max_val

        # Run standard Voice Activity Detection filter
        data = voice_activity_filter(data, sr=target_sr)

        return data.astype(np.float32)

    def predict(self, audio_input) -> dict:
        """
        Executes end-to-end voice authenticity prediction on audio.
        Args:
            audio_input: Audio file path (.wav, .flac, .ogg, etc.) or 1D numpy array.
        Returns:
            dict containing prediction ('REAL' or 'FAKE'), fake_probability, confidence, and risk_level.
        """
        waveform = self.load_and_preprocess_audio(audio_input)
        feat_matrix = extract_temporal_feature_matrix(waveform)  # (100, 32)
        batch_input = np.expand_dims(feat_matrix, axis=0)        # (1, 100, 32)

        if self.format == "onnx":
            probs = self.session.run(None, {self.input_name: batch_input})[0][0]
        else:
            with self.torch.no_grad():
                tensor = self.torch.from_numpy(batch_input).float()
                probs = self.model(tensor).cpu().numpy()[0]

        real_prob = float(probs[0])
        fake_prob = float(probs[1])

        prediction = "FAKE" if fake_prob >= 0.50 else "REAL"
        conf = max(real_prob, fake_prob) * 100.0

        if fake_prob < 0.35:
            risk_level = "LOW"
            badge = "🟢 LOW RISK (AUTHENTIC)"
        elif fake_prob < 0.70:
            risk_level = "SUSPICIOUS"
            badge = "🟡 SUSPICIOUS - VERIFY"
        else:
            risk_level = "HIGH"
            badge = "🔴 HIGH RISK (ATTACK)"

        return {
            "prediction": prediction,
            "fake_probability": round(fake_prob, 4),
            "real_probability": round(real_prob, 4),
            "confidence_pct": round(conf, 2),
            "risk_level": risk_level,
            "badge": badge
        }
