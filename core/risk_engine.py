"""
Real-Time Dynamic Risk Scoring Engine.
Synthesizes Multi-Layer Authenticity Signals:
1. Deep Neural Network Prediction (AcousticProsodicNet)
2. DSP Vocoder Spectral Artifact Index
3. Biometric Prosody & Micro-variation Naturalness Index
4. Speaker Identity Cosine Distance (if claimed ID provided)
5. Contextual Enterprise Risk Multipliers (e.g. Wire Transfer, CXO, Credential Requests)
"""

from typing import Dict, Any, Optional


class RiskEngine:
    """
    Computes a calibrated 0.0-1.0 risk score and actionable classification:
    - 🟢 LOW RISK
    - 🟡 SUSPICIOUS - VERIFY
    - 🔴 HIGH RISK (CRITICAL ATTACK)
    """

    def __init__(
        self,
        weight_neural: float = 0.50,
        weight_foundation: float = 0.18,
        weight_spectral: float = 0.08,
        weight_prosody: float = 0.08,
        weight_glottal: float = 0.08,
        weight_phase: float = 0.08,
        weight_speaker: float = 0.10
    ):
        self.w_neural = weight_neural
        self.w_foundation = weight_foundation
        self.w_spectral = weight_spectral
        self.w_prosody = weight_prosody
        self.w_glottal = weight_glottal
        self.w_phase = weight_phase
        self.w_speaker = weight_speaker

    def compute_spectral_anomaly_score(self, metrics: Dict[str, float]) -> float:
        """
        Calculates vocoder/synthesis artifact score based on:
        - High-frequency cutoff / energy anomalies (>4kHz)
        - Spectral flatness abnormalities
        - High-frequency spectral rolloff
        """
        score = 0.0
        hf_ratio = metrics.get("hf_energy_ratio", 0.05)
        flatness = metrics.get("spectral_flatness", 0.005)
        rolloff = metrics.get("spectral_rolloff_hz", 3500.0)

        # Vocoders (e.g. Diffusion, HiFi-GAN, WaveGlow) exhibit abnormal high-frequency noise floor
        # or extreme energy concentrations in upper bands (>4kHz)
        if hf_ratio > 0.35:
            score += 0.35
        elif hf_ratio > 0.20:
            score += 0.20

        # Spectral flatness anomaly:
        # Neural TTS vocoders often introduce excessive noise floor (flatness > 0.30)
        # or pure synthetic harmonics with extreme pitch periodicity (flatness < 0.0001)
        if flatness > 0.32:
            score += 0.35
        elif flatness < 0.0001:
            score += 0.25

        # Extreme cutoff anomaly (below 600 Hz is unnatural even for telephony speech)
        if rolloff < 600:
            score += 0.25

        return min(1.0, score)

    def compute_prosody_anomaly_score(self, metrics: Dict[str, float]) -> float:
        """
        Calculates prosodic unnaturalness score:
        - Robotic pitch invariance (extremely low F0 standard deviation)
        - Unnatural micro-jitter / shimmer
        """
        score = 0.0
        f0_std = metrics.get("f0_std_hz", 30.0)
        f0_range = metrics.get("f0_range_hz", 100.0)
        jitter = metrics.get("jitter", 1.2)      # in percent
        shimmer = metrics.get("shimmer", 3.5)    # in percent

        # Unnatural pitch flatness (typical in robotic or early neural TTS)
        if f0_std < 8.0 and f0_range < 25.0:
            score += 0.40
        elif f0_std < 12.0:
            score += 0.15

        # Micro-variation anomalies:
        # Human jitter is typically 0.4% - 3.0%.
        # Overly clean synthetic voices have < 0.2% jitter.
        # Poor synthesis or glitchy neural TTS has > 4.5% jitter.
        if jitter < 0.25:
            score += 0.35  # Unnaturally perfect periodicity
        elif jitter > 4.5:
            score += 0.30  # Synthesis boundary glitching

        # Shimmer anomalies
        if shimmer < 0.8 or shimmer > 12.0:
            score += 0.20

        return min(1.0, score)

    def evaluate_risk(
        self,
        neural_fake_prob: float,
        forensic_metrics: Dict[str, float],
        speaker_verification: Optional[Dict[str, Any]] = None,
        glottal_assessment: Optional[Dict[str, Any]] = None,
        phase_assessment: Optional[Dict[str, Any]] = None,
        foundation_assessment: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        ensemble_fusion: Optional[Dict[str, Any]] = None,
        semantic_assessment: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Fuses multi-vector signals, ensemble fusion, contextual factors, and semantic cyberthreats into a unified enterprise risk assessment.
        """
        # 1. Forensic sub-scores
        spectral_score = self.compute_spectral_anomaly_score(forensic_metrics)
        prosody_score = self.compute_prosody_anomaly_score(forensic_metrics)

        # 2. Enterprise Glottal & Phase Forensic vectors
        glottal_score = glottal_assessment.get("glottal_anomaly_score", 0.0) if glottal_assessment else 0.0
        phase_score = phase_assessment.get("phase_incoherence_score", 0.0) if phase_assessment else 0.0

        # 3. Pretrained Whisper Foundation Vector
        if foundation_assessment and foundation_assessment.get("is_available", False):
            foundation_score = foundation_assessment.get("pretrained_fake_prob", 0.5)
            w_found = self.w_foundation
        else:
            foundation_score = 0.0
            w_found = 0.0

        # 4. Speaker verification score
        if speaker_verification and speaker_verification.get("enrolled"):
            speaker_risk = speaker_verification.get("mismatch_risk", 0.5)
            w_spk = self.w_speaker
        else:
            speaker_risk = 0.0
            w_spk = 0.0

        # Renormalize active weights
        total_weight = self.w_neural + w_found + self.w_spectral + self.w_prosody + self.w_glottal + self.w_phase + w_spk
        norm_w_neural = self.w_neural / total_weight
        norm_w_found = w_found / total_weight
        norm_w_spectral = self.w_spectral / total_weight
        norm_w_prosody = self.w_prosody / total_weight
        norm_w_glottal = self.w_glottal / total_weight
        norm_w_phase = self.w_phase / total_weight
        norm_w_speaker = w_spk / total_weight

        # 5. Multi-Vector Composite Base Score
        base_score = (
            (norm_w_neural * neural_fake_prob) +
            (norm_w_found * foundation_score) +
            (norm_w_spectral * spectral_score) +
            (norm_w_prosody * prosody_score) +
            (norm_w_glottal * glottal_score) +
            (norm_w_phase * phase_score) +
            (norm_w_speaker * speaker_risk)
        )

        # 6. Contextual Risk Factor
        context_multiplier = 1.0
        context_flags = []
        if context:
            tx_amount = context.get("transaction_amount", 0)
            if tx_amount > 50000:
                context_multiplier = 1.25
                context_flags.append(f"High-Value Financial Transaction ($/₹{tx_amount:,})")
            elif tx_amount > 10000:
                context_multiplier = 1.15
                context_flags.append(f"Elevated Financial Transaction ($/₹{tx_amount:,})")

            if context.get("is_cxo_call", False):
                context_multiplier *= 1.20
                context_flags.append("Executive / CXO Impersonation High-Target Scenario")

            if context.get("credential_request", False):
                context_multiplier *= 1.30
                context_flags.append("Sensitive Credential / OTP Request Initiated")

        final_score = min(1.0, base_score * context_multiplier)

        # 7. Multi-Class & Cybersecurity Threat Intelligence
        predicted_class = "UNKNOWN"
        fusion_probabilities = {}
        if ensemble_fusion:
            predicted_class = ensemble_fusion.get("predicted_class", "UNKNOWN")
            fusion_probabilities = ensemble_fusion.get("probabilities", {})

        p_attack = fusion_probabilities.get("voice_cloning_attack", 0.0)
        is_voice_cloning_attack = (predicted_class == "VOICE_CLONING_ATTACK" or p_attack >= 0.50)
        is_non_human = (predicted_class == "NON_HUMAN")

        # 8. Semantic Cyberthreat Cross-Correlation
        is_scam = False
        scam_cat_display = ""
        scam_score = 0.0
        if semantic_assessment and semantic_assessment.get("is_scam"):
            is_scam = True
            scam_cat_display = semantic_assessment.get("display_category", "Scam Attack")
            scam_score = semantic_assessment.get("scam_score", 0.75)

        if is_voice_cloning_attack and is_scam:
            risk_level = "HIGH"
            badge = "🚨 CRITICAL: CLONED VISHING ATTACK"
            summary = f"CRITICAL DUAL-VECTOR ATTACK: Generative AI voice cloning impersonation combined with active {scam_cat_display}. Coercive financial fraud/extortion in progress."
            final_score = max(final_score, 0.96)
        elif is_voice_cloning_attack:
            risk_level = "HIGH"
            badge = "🔴 HIGH RISK (VOICE CLONING ATTACK)"
            summary = "Targeted generative AI voice cloning attack detected. Acoustic biometric violation & vocoder phase dispersion confirm impersonation."
            final_score = max(final_score, min(0.99, max(0.85, neural_fake_prob * 0.95)))
        elif is_scam:
            risk_level = "HIGH"
            badge = f"⚠️ HIGH RISK ({scam_cat_display.upper()})"
            summary = f"FRAUD CALL DETECTED: Active {scam_cat_display}. Conversational speech contains coercive social engineering threats, credential harvesting, or extortion."
            final_score = max(final_score, max(0.85, scam_score * 0.92))
        elif is_non_human:
            risk_level = "SUSPICIOUS"
            badge = "🤖 NON-HUMAN SYNTHETIC AUDIO"
            summary = "Synthetic audio / robotic speech detected. Lacks organic human prosody and natural glottal variation."
            final_score = max(final_score, 0.55)
        elif final_score >= 0.65 or neural_fake_prob >= 0.75:
            risk_level = "HIGH"
            badge = "🔴 HIGH RISK (SYNTHETIC ATTACK)"
            summary = "Strong synthetic speech signatures detected. Potential active social engineering attack."
            final_score = max(final_score, min(0.99, neural_fake_prob * 0.95))
        elif final_score >= 0.38 or neural_fake_prob >= 0.50:
            risk_level = "SUSPICIOUS"
            badge = "🟡 SUSPICIOUS - VERIFY"
            summary = "Borderline or conflicting acoustic/prosodic indicators. Secondary out-of-band verification required."
        else:
            risk_level = "LOW"
            badge = "🟢 LOW RISK (AUTHENTIC HUMAN)"
            summary = "Bona fide human speech verified. No significant cloning or synthetic indicators detected."

        return {
            "risk_score": round(final_score, 4),
            "risk_percentage": round(final_score * 100, 1),
            "risk_level": risk_level,
            "badge": badge,
            "summary": summary,
            "predicted_class": predicted_class,
            "fusion_probabilities": fusion_probabilities,
            "is_voice_cloning_attack": is_voice_cloning_attack,
            "is_semantic_scam": is_scam,
            "sub_scores": {
                "neural_spoof_prob": round(neural_fake_prob, 4),
                "spectral_artifact_score": round(spectral_score, 4),
                "prosody_unnatural_score": round(prosody_score, 4),
                "glottal_anomaly_score": round(glottal_score, 4),
                "phase_incoherence_score": round(phase_score, 4),
                "speaker_mismatch_score": round(speaker_risk, 4) if w_spk > 0 else None,
                "semantic_scam_score": round(scam_score, 4) if semantic_assessment else None
            },
            "context_flags": context_flags,
            "context_multiplier": round(context_multiplier, 2),
            "semantic_assessment": semantic_assessment
        }
