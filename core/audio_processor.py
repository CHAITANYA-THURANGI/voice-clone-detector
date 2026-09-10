"""
Audio Ingestion, Resampling, and Preprocessing Engine.
Ensures universal format compatibility (WAV, OGG, MP3, FLAC, M4A, WebM) via FFmpeg
and provides Voice Activity Detection (VAD) and sliding-window chunking.
"""

import os
import sys
import tempfile
import subprocess
import numpy as np
import soundfile as sf


import shutil

TARGET_SAMPLE_RATE = 16000


def get_ffmpeg_binary() -> str:
    """
    Returns the path to a working FFmpeg binary.
    Prioritizes system ffmpeg, with guaranteed zero-dependency fallback via imageio-ffmpeg.
    """
    sys_ffmpeg = shutil.which("ffmpeg")
    if sys_ffmpeg:
        return sys_ffmpeg
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        exe_dir = os.path.dirname(exe)
        if exe_dir not in os.environ.get("PATH", ""):
            os.environ["PATH"] = exe_dir + os.pathsep + os.environ.get("PATH", "")
        return exe
    except Exception:
        return "ffmpeg"


def convert_to_16k_mono(input_path: str, output_path: str = None) -> str:
    """
    Converts any audio file to 16kHz, mono, 16-bit PCM WAV using FFmpeg.
    If output_path is not specified, a temporary file is generated.
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input audio file not found: {input_path}")

    if output_path is None:
        fd, output_path = tempfile.mkstemp(suffix="_16k_mono.wav")
        os.close(fd)

    ffmpeg_bin = get_ffmpeg_binary()
    cmd = [
        ffmpeg_bin,
        "-y",
        "-i", input_path,
        "-vn",
        "-ar", str(TARGET_SAMPLE_RATE),
        "-ac", "1",
        "-c:a", "pcm_s16le",
        output_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        err_msg = result.stderr.strip() if result.stderr else "Unknown FFmpeg error"
        raise RuntimeError(f"FFmpeg conversion failed on {input_path}: {err_msg}")

    return output_path


def load_audio_from_bytes(audio_bytes: bytes, file_ext: str = "wav") -> np.ndarray:
    """
    Loads raw audio bytes (from HTTP upload or live microphone stream),
    converts to 16kHz mono float32 waveform, removes DC offset, and normalizes peaks.
    Fast-paths in-memory WAV without disk I/O when possible.
    """
    import io

    waveform = None
    # Fast path: Try direct in-memory decode if WAV
    if file_ext.lower() in ["wav", "wave"] or audio_bytes.startswith(b"RIFF"):
        try:
            with io.BytesIO(audio_bytes) as bio:
                data, sr = sf.read(bio, dtype="float32")
                if data.ndim > 1:
                    data = np.mean(data, axis=1)
                # Resample to 16000 if needed
                if sr == TARGET_SAMPLE_RATE:
                    waveform = data
                else:
                    # Use lightweight scipy.signal resample (zero extra dependencies)
                    import scipy.signal
                    num_samples = int(round(len(data) * float(TARGET_SAMPLE_RATE) / float(sr)))
                    waveform = scipy.signal.resample(data, num_samples).astype(np.float32)
        except Exception:
            waveform = None

    # Fallback to universal FFmpeg transcoding
    if waveform is None:
        ext = file_ext.lstrip(".") if file_ext else "wav"
        with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tf:
            tf.write(audio_bytes)
            temp_input = tf.name

        converted_wav = None
        try:
            converted_wav = convert_to_16k_mono(temp_input)
            waveform, sr = sf.read(converted_wav, dtype="float32")
            if waveform.ndim > 1:
                waveform = np.mean(waveform, axis=1)
        finally:
            if os.path.exists(temp_input):
                try:
                    os.remove(temp_input)
                except OSError:
                    pass
            if converted_wav and os.path.exists(converted_wav):
                try:
                    os.remove(converted_wav)
                except OSError:
                    pass

    # DC offset removal & peak normalization
    waveform = waveform - np.mean(waveform)
    max_val = np.max(np.abs(waveform))
    if max_val > 1e-6:
        waveform = waveform / max_val

    return waveform.astype(np.float32)



def load_audio(path: str) -> np.ndarray:
    """
    Loads an audio file into a 1D float32 NumPy array at 16000 Hz.
    Converts through FFmpeg to avoid codec issues (e.g. malformed OGG).
    """
    converted_wav = convert_to_16k_mono(path)
    try:
        waveform, sr = sf.read(converted_wav, dtype="float32")
        if waveform.ndim > 1:
            waveform = np.mean(waveform, axis=1)

        # DC offset removal & peak normalization
        waveform = waveform - np.mean(waveform)
        max_val = np.max(np.abs(waveform))
        if max_val > 1e-6:
            waveform = waveform / max_val

        return waveform.astype(np.float32)
    finally:
        if os.path.exists(converted_wav):
            os.remove(converted_wav)


def voice_activity_filter(
    waveform: np.ndarray,
    sr: int = TARGET_SAMPLE_RATE,
    frame_ms: int = 30,
    energy_threshold: float = 0.005
) -> np.ndarray:
    """
    Simple, fast energy-based Voice Activity Detection (VAD)
    to eliminate long silences without distorting active speech prosody.
    """
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
        return waveform  # Fallback if silence threshold was too strict

    return np.concatenate(active_frames)


def chunk_waveform(
    waveform: np.ndarray,
    sr: int = TARGET_SAMPLE_RATE,
    chunk_sec: float = 3.0,
    step_sec: float = 1.0
):
    """
    Yields overlapping chunks of speech for sliding-window stream detection.
    """
    chunk_len = int(sr * chunk_sec)
    step_len = int(sr * step_sec)

    if len(waveform) <= chunk_len:
        # Pad with repeat/zeros if shorter than 1 window
        if len(waveform) < chunk_len:
            repeats = int(np.ceil(chunk_len / len(waveform)))
            padded = np.tile(waveform, repeats)[:chunk_len]
            yield 0.0, chunk_sec, padded
        else:
            yield 0.0, chunk_sec, waveform
        return

    num_chunks = int((len(waveform) - chunk_len) // step_len) + 1
    for i in range(num_chunks):
        start_idx = i * step_len
        end_idx = start_idx + chunk_len
        start_time = start_idx / sr
        end_time = end_idx / sr
        yield start_time, end_time, waveform[start_idx:end_idx]
