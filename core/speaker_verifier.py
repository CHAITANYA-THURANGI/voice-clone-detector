"""
Cross-Session Speaker Identity & Biometric Consistency Engine.
Satisfies SIH PS-26104 requirement for detecting CXO / executive impersonation
by comparing call voiceprints against enrolled reference profiles.
"""

import os
import json
import numpy as np
from core.feature_extraction import extract_cepstral_features, frame_signal, estimate_f0_and_prosody


DEFAULT_PROFILES_PATH = "data/speaker_profiles.json"


class SpeakerVerifier:
    def __init__(self, profiles_file: str = DEFAULT_PROFILES_PATH):
        self.profiles_file = profiles_file
        self.profiles = {}
        self.load_profiles()

    def load_profiles(self):
        if os.path.exists(self.profiles_file):
            try:
                with open(self.profiles_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.profiles = {k: np.array(v) for k, v in data.items()}
            except Exception:
                self.profiles = {}

    def save_profiles(self):
        os.makedirs(os.path.dirname(self.profiles_file) or ".", exist_ok=True)
        serializable = {k: v.tolist() for k, v in self.profiles.items()}
        with open(self.profiles_file, "w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2)

    def extract_voiceprint(self, waveform: np.ndarray, sr: int = 16000) -> np.ndarray:
        """
        Extracts a compact, high-dimensional speaker acoustic voiceprint
        combining MFCCs, LFCCs, pitch harmonics, and energy distribution.
        """
        frames = frame_signal(waveform, 512, 256)
        mfccs = extract_cepstral_features(frames, sr, 512, num_ceps=16, linear=False)
        lfccs = extract_cepstral_features(frames, sr, 512, num_ceps=16, linear=True)
        prosody = estimate_f0_and_prosody(waveform, sr, 512, 256)

        mfcc_mean = np.mean(mfccs, axis=0)
        mfcc_std = np.std(mfccs, axis=0)
        lfcc_mean = np.mean(lfccs, axis=0)
        lfcc_std = np.std(lfccs, axis=0)

        f0_stats = np.array([
            prosody["f0_mean"] / 400.0,
            prosody["f0_std"] / 100.0,
            prosody["voiced_ratio"]
        ])

        voiceprint = np.concatenate([mfcc_mean, mfcc_std, lfcc_mean, lfcc_std, f0_stats])
        # L2-normalize
        norm = np.linalg.norm(voiceprint)
        if norm > 1e-8:
            voiceprint = voiceprint / norm
        return voiceprint.astype(np.float32)

    def enroll(self, speaker_id: str, waveform: np.ndarray, sr: int = 16000) -> dict:
        """Enrolls a known speaker (e.g. CEO, CFO, Banking Executive)."""
        voiceprint = self.extract_voiceprint(waveform, sr)
        self.profiles[speaker_id] = voiceprint
        self.save_profiles()
        return {
            "speaker_id": speaker_id,
            "status": "ENROLLED",
            "dimensions": len(voiceprint)
        }

    def verify(self, claimed_speaker_id: str, waveform: np.ndarray, sr: int = 16000, threshold: float = 0.75) -> dict:
        """
        Compares caller voiceprint against enrolled profile.
        Returns similarity, mismatch risk, and anomaly flag.
        """
        if claimed_speaker_id not in self.profiles:
            return {
                "claimed_speaker": claimed_speaker_id,
                "enrolled": False,
                "similarity": None,
                "impersonation_risk": 0.50,
                "message": f"Speaker '{claimed_speaker_id}' not enrolled; neutral fallback applied."
            }

        enrolled_vprint = self.profiles[claimed_speaker_id]
        current_vprint = self.extract_voiceprint(waveform, sr)

        # Cosine similarity
        similarity = float(np.dot(enrolled_vprint, current_vprint))
        similarity = max(0.0, min(1.0, (similarity + 1.0) / 2.0))  # Scale to [0, 1]

        mismatch_risk = 1.0 - similarity
        is_mismatch = similarity < threshold

        return {
            "claimed_speaker": claimed_speaker_id,
            "enrolled": True,
            "similarity": round(similarity, 4),
            "mismatch_risk": round(mismatch_risk, 4),
            "is_impersonation_mismatch": is_mismatch,
            "status": "MATCH" if not is_mismatch else "IMPERSONATION_MISMATCH"
        }
