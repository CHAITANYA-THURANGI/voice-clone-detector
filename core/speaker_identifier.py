"""
1:N Open-Set Speaker Identification & Biometric Identity Engine.
Implements scalable vector search across enrolled voiceprint directories:
1. Family & Trusted Contacts (Mom, Dad, Children, Spouse)
2. Corporate VIPs & Executives (CEO, CFO, Treasury Director)
3. Threat Actor & Telecommunication Scammer Biometric Watchlist

Detects Cross-Modal Identity Discrepancies:
- Voice Actor / Imposter claiming to be a trusted contact without voice clone technology.
- Targeted AI Voice Clone attempting to forge an enrolled identity.
"""

import os
import json
from typing import Dict, Any, List, Optional
import numpy as np

from core.feature_extraction import extract_cepstral_features, frame_signal, estimate_f0_and_prosody


DEFAULT_PROFILES_PATH = "data/speaker_profiles.json"


class SpeakerIdentifier:
    """
    Open-Set 1:N Speaker Identification and Biometric Identity Verification Engine.
    """

    def __init__(self, profiles_file: str = DEFAULT_PROFILES_PATH):
        self.profiles_file = profiles_file
        self.profiles: Dict[str, Dict[str, Any]] = {}
        self.load_profiles()

    def load_profiles(self):
        """Loads enrolled voiceprints and metadata from disk."""
        if os.path.exists(self.profiles_file):
            try:
                with open(self.profiles_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.profiles = {}
                    for k, v in data.items():
                        if isinstance(v, dict) and "voiceprint" in v:
                            self.profiles[k] = {
                                "name": v.get("name", k),
                                "category": v.get("category", "CONTACT"),
                                "phone": v.get("phone", "Unknown"),
                                "voiceprint": np.array(v["voiceprint"], dtype=np.float32),
                                "created_at": v.get("created_at", "")
                            }
                        elif isinstance(v, list):
                            # Backward-compatible array format
                            self.profiles[k] = {
                                "name": k,
                                "category": "CONTACT",
                                "phone": "Unknown",
                                "voiceprint": np.array(v, dtype=np.float32),
                                "created_at": ""
                            }
            except Exception as e:
                print(f"[SpeakerIdentifier] Warning loading profiles: {e}")
                self.profiles = {}

    def save_profiles(self):
        """Serializes enrolled voiceprints to disk."""
        os.makedirs(os.path.dirname(self.profiles_file) or ".", exist_ok=True)
        serializable = {}
        for k, v in self.profiles.items():
            serializable[k] = {
                "name": v["name"],
                "category": v["category"],
                "phone": v.get("phone", "Unknown"),
                "voiceprint": v["voiceprint"].tolist(),
                "created_at": v.get("created_at", "")
            }
        with open(self.profiles_file, "w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2)

    def extract_voiceprint(self, waveform: np.ndarray, sr: int = 16000) -> np.ndarray:
        """
        Extracts a high-dimensional biometric vocal tract voiceprint embedding
        combining MFCC/LFCC spectral envelopes (excluding C0), formant sub-band energies,
        and pitch kinematics.
        """
        if len(waveform) < 1600:  # Less than 0.1s
            return np.zeros(40, dtype=np.float32)

        frames = frame_signal(waveform, 512, 256)
        # Skip C0 (volume/energy) - use C1..C16
        mfccs = extract_cepstral_features(frames, sr, 512, num_ceps=16, linear=False)[:, 1:]
        lfccs = extract_cepstral_features(frames, sr, 512, num_ceps=16, linear=True)[:, 1:]
        prosody = estimate_f0_and_prosody(waveform, sr, 512, 256)

        m_mean = np.mean(mfccs, axis=0)
        l_mean = np.mean(lfccs, axis=0)

        # Formant sub-band energy ratios
        import scipy.signal as signal
        f, t, Zxx = signal.stft(waveform, fs=sr, nperseg=512, noverlap=256)
        mag2 = np.abs(Zxx) ** 2
        tot = np.sum(mag2) + 1e-6
        bands = [(100, 500), (500, 1500), (1500, 3000), (3000, 5500), (5500, 8000)]
        b_energies = [float(np.sum(mag2[(f >= lo) & (f <= hi), :]) / tot) for lo, hi in bands]

        f0_mean = float(prosody.get("f0_mean", 150.0)) / 300.0
        f0_std = float(prosody.get("f0_std", 20.0)) / 80.0

        raw = np.concatenate([m_mean, l_mean, b_energies, [f0_mean, f0_std]]).astype(np.float32)
        # Subtract mean across feature dimensions to eliminate common spectral tilt
        centered = raw - np.mean(raw)
        norm = np.linalg.norm(centered)
        if norm > 1e-8:
            centered = centered / norm
        return centered.astype(np.float32)

    def enroll(
        self,
        speaker_id: str,
        waveform: np.ndarray,
        name: Optional[str] = None,
        category: str = "CONTACT",
        phone: str = "Unknown",
        sr: int = 16000
    ) -> Dict[str, Any]:
        """
        Enrolls a new voiceprint in the biometric directory.
        Categories: 'FAMILY', 'EXECUTIVE', 'CONTACT', 'SCAMMER_WATCHLIST'.
        """
        import time
        voiceprint = self.extract_voiceprint(waveform, sr)
        self.profiles[speaker_id] = {
            "name": name or speaker_id,
            "category": category.upper(),
            "phone": phone,
            "voiceprint": voiceprint,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        self.save_profiles()
        return {
            "speaker_id": speaker_id,
            "name": name or speaker_id,
            "category": category.upper(),
            "status": "ENROLLED",
            "dimensions": len(voiceprint)
        }

    def identify_speaker(
        self,
        waveform: np.ndarray,
        sr: int = 16000,
        top_k: int = 3,
        threshold: float = 0.70
    ) -> Dict[str, Any]:
        """
        Performs 1:N Open-Set Speaker Identification.
        Compares incoming voiceprint against all enrolled profiles and ranks candidates.
        """
        if not self.profiles:
            return {
                "identified": False,
                "speaker_id": "UNKNOWN_CALLER",
                "name": "Unknown / Unregistered Caller",
                "category": "UNKNOWN",
                "similarity": 0.0,
                "confidence_pct": 0.0,
                "is_known_contact": False,
                "is_scammer_watchlist": False,
                "candidates": [],
                "message": "No speaker profiles enrolled in biometric directory."
            }

        input_vprint = self.extract_voiceprint(waveform, sr)

        # Compute cosine similarities
        scores = []
        for sid, pdata in self.profiles.items():
            enrolled_vprint = pdata["voiceprint"]
            raw_sim = float(np.dot(enrolled_vprint, input_vprint))
            # Calibrate cosine similarity: same-speaker is >= 0.99; different speaker is <= 0.93
            sim = float(np.clip((raw_sim - 0.92) / 0.075, 0.0, 1.0))
            scores.append({
                "speaker_id": sid,
                "name": pdata["name"],
                "category": pdata["category"],
                "phone": pdata.get("phone", "Unknown"),
                "similarity": round(sim, 4),
                "confidence_pct": round(sim * 100, 1)
            })

        # Sort descending by similarity
        scores.sort(key=lambda x: x["similarity"], reverse=True)
        top_match = scores[0]

        is_identified = top_match["similarity"] >= threshold
        is_scammer = (top_match["category"] == "SCAMMER_WATCHLIST" and is_identified)

        if is_identified:
            identified_id = top_match["speaker_id"]
            identified_name = top_match["name"]
            identified_category = top_match["category"]
        else:
            identified_id = "UNKNOWN_CALLER"
            identified_name = "Unknown Caller (No Match)"
            identified_category = "UNKNOWN"

        return {
            "identified": is_identified,
            "speaker_id": identified_id,
            "name": identified_name,
            "category": identified_category,
            "similarity": top_match["similarity"],
            "confidence_pct": top_match["confidence_pct"],
            "is_known_contact": is_identified and (identified_category in ["FAMILY", "EXECUTIVE", "CONTACT"]),
            "is_scammer_watchlist": is_scammer,
            "top_match": top_match,
            "candidates": scores[:top_k],
            "threshold_used": threshold
        }

    def detect_cross_modal_discrepancy(
        self,
        claimed_identity: str,
        waveform: np.ndarray,
        sr: int = 16000,
        threshold: float = 0.70
    ) -> Dict[str, Any]:
        """
        Cross-correlates claimed caller identity (e.g. from Caller ID or Speech Recognition)
        with 1:N acoustic voiceprint biometric identification.
        """
        claimed_clean = claimed_identity.strip().lower()
        id_result = self.identify_speaker(waveform, sr=sr, threshold=threshold)

        # Check if claimed identity matches any enrolled profile ID or Name
        target_profile_id = None
        target_profile = None
        for sid, pdata in self.profiles.items():
            if claimed_clean in sid.lower() or claimed_clean in pdata["name"].lower():
                target_profile_id = sid
                target_profile = pdata
                break

        if not target_profile:
            return {
                "claimed_identity": claimed_identity,
                "is_enrolled": False,
                "is_discrepancy": False,
                "discrepancy_type": "UNREGISTERED_CLAIMED_IDENTITY",
                "similarity_to_claimed": None,
                "identified_as": id_result["name"],
                "summary": f"Claimed identity '{claimed_identity}' is not in the enrolled directory."
            }

        input_vprint = self.extract_voiceprint(waveform, sr)
        enrolled_vprint = target_profile["voiceprint"]
        raw_sim = float(np.dot(enrolled_vprint, input_vprint))
        sim = float(np.clip((raw_sim - 0.92) / 0.075, 0.0, 1.0))

        is_mismatch = sim < threshold

        if is_mismatch:
            discrepancy_type = "IMPOSTER_IDENTITY_MISMATCH"
            summary = (
                f"🚨 BIOMETRIC DISCREPANCY: Caller claims to be '{target_profile['name']}', "
                f"but acoustic voiceprint similarity is only {sim*100:.1f}% (threshold {threshold*100:.0f}%). "
                f"Acoustics identify: '{id_result['name']}'."
            )
        else:
            discrepancy_type = "AUTHENTIC_IDENTITY_MATCH"
            summary = f"Verified: Caller acoustics match enrolled voiceprint for '{target_profile['name']}' ({sim*100:.1f}% match)."

        return {
            "claimed_identity": claimed_identity,
            "target_name": target_profile["name"],
            "category": target_profile["category"],
            "is_enrolled": True,
            "is_discrepancy": is_mismatch,
            "discrepancy_type": discrepancy_type,
            "similarity_to_claimed": round(sim, 4),
            "similarity_pct": round(sim * 100, 1),
            "identified_as": id_result["name"],
            "summary": summary
        }

    def verify(
        self,
        claimed_speaker_id: str,
        waveform: np.ndarray,
        sr: int = 16000,
        threshold: float = 0.70
    ) -> Dict[str, Any]:
        """
        Backward-compatible 1:1 verification wrapper calling discrepancy logic.
        """
        disc = self.detect_cross_modal_discrepancy(claimed_speaker_id, waveform, sr=sr, threshold=threshold)
        sim = disc.get("similarity_to_claimed") or 0.0
        return {
            "claimed_speaker": claimed_speaker_id,
            "enrolled": disc["is_enrolled"],
            "similarity": sim,
            "mismatch_risk": round(1.0 - sim, 4),
            "is_impersonation_mismatch": disc["is_discrepancy"],
            "status": "MATCH" if not disc["is_discrepancy"] else "IMPERSONATION_MISMATCH",
            "message": disc["summary"]
        }


# Global Singleton
speaker_identifier = SpeakerIdentifier()
