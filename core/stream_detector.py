"""
Real-Time Sliding Window Stream Processing Engine.
Performs chunk-by-chunk voice integrity analysis on live telephony/VoIP audio streams
with temporal risk tracking, consecutive anomaly thresholds, and exponential decay.
"""

from typing import Dict, Any, List, Optional
import numpy as np
from core.feature_extraction import extract_temporal_feature_matrix, extract_forensic_summary
from core.model import AcousticProsodicNet
from core.risk_engine import RiskEngine
from core.prevention import PreventionEngine
from core.speaker_verifier import SpeakerVerifier
from core.privacy import PrivacyComplianceGuard


from core.glottal_forensics import analyze_glottal_biometrics
from core.spectral_phase import analyze_phase_coherence
from core.enterprise_telemetry import EnterpriseTelemetryEngine


class RealTimeStreamDetector:
    """
    Manages state for an active streaming call session.
    """

    def __init__(
        self,
        call_id: str,
        model: AcousticProsodicNet,
        risk_engine: Optional[RiskEngine] = None,
        speaker_verifier: Optional[SpeakerVerifier] = None,
        claimed_speaker_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        self.call_id = call_id
        self.model = model
        self.risk_engine = risk_engine or RiskEngine()
        self.speaker_verifier = speaker_verifier or SpeakerVerifier()
        self.claimed_speaker_id = claimed_speaker_id
        self.context = context or {}

        # Streaming session history
        self.chunk_history: List[Dict[str, Any]] = []
        self.consecutive_suspicious_count: int = 0
        self.max_observed_risk: float = 0.0
        self.current_rolling_risk: float = 0.0
        self.alpha_ema: float = 0.45  # Exponential moving average factor

    def process_chunk(self, chunk_waveform: np.ndarray, timestamp_sec: float) -> Dict[str, Any]:
        """
        Analyzes a single 2-5 second audio chunk from the incoming live stream using all 5 forensic vectors.
        """
        # 1. Extract forensic features
        feature_matrix = extract_temporal_feature_matrix(chunk_waveform)
        forensic = extract_forensic_summary(chunk_waveform)

        # 2. Vector 1: Deep Conformer Neural Network Inference
        neural_res = self.model.predict_sample(feature_matrix)
        neural_fake_prob = neural_res["fake_probability"]

        # 3. Vector 2: Biometric LPC Glottal Flow Inverse Residual Analysis
        glottal_res = analyze_glottal_biometrics(chunk_waveform, sr=16000)

        # 4. Vector 3: Phase-Aware Modified Group Delay (MGD) Analysis
        phase_res = analyze_phase_coherence(chunk_waveform, sr=16000)

        # 5. Vector 5: Optional speaker identity verification
        spk_res = None
        if self.claimed_speaker_id:
            spk_res = self.speaker_verifier.verify(self.claimed_speaker_id, chunk_waveform)

        # 6. Dynamic 5-Vector Risk Engine Evaluation
        risk_eval = self.risk_engine.evaluate_risk(
            neural_fake_prob=neural_fake_prob,
            forensic_metrics=forensic["metrics"],
            speaker_verification=spk_res,
            glottal_assessment=glottal_res,
            phase_assessment=phase_res,
            context=self.context
        )

        chunk_risk = risk_eval["risk_score"]

        # 7. Temporal aggregation heuristics
        self.max_observed_risk = max(self.max_observed_risk, chunk_risk)

        if not self.chunk_history:
            self.current_rolling_risk = chunk_risk
        else:
            self.current_rolling_risk = (self.alpha_ema * chunk_risk) + ((1.0 - self.alpha_ema) * self.current_rolling_risk)

        # Track consecutive anomalies
        if chunk_risk >= 0.40:
            self.consecutive_suspicious_count += 1
        else:
            self.consecutive_suspicious_count = max(0, self.consecutive_suspicious_count - 1)

        # Elevate overall session risk if consecutive anomalies detected
        session_risk = max(self.current_rolling_risk, self.max_observed_risk * 0.85)
        if self.consecutive_suspicious_count >= 2:
            session_risk = max(session_risk, 0.78)  # Elevate to HIGH RISK

        # Categorize session level
        if session_risk < 0.35:
            session_level = "LOW"
            session_badge = "🟢 LOW RISK"
        elif session_risk < 0.70:
            session_level = "SUSPICIOUS"
            session_badge = "🟡 SUSPICIOUS - VERIFY"
        else:
            session_level = "HIGH"
            session_badge = "🔴 HIGH RISK (ATTACK)"

        session_assessment = {
            "risk_score": round(session_risk, 4),
            "risk_percentage": round(session_risk * 100, 1),
            "risk_level": session_level,
            "badge": session_badge,
            "summary": risk_eval["summary"],
            "context_flags": risk_eval.get("context_flags", [])
        }

        # Prevention plan for this point in time
        prevention_plan = PreventionEngine.generate_prevention_plan(session_assessment, call_id=self.call_id)

        # SHA-256 fingerprint for compliance (purge raw array immediately)
        audio_fingerprint = PrivacyComplianceGuard.generate_audio_fingerprint(chunk_waveform)
        PrivacyComplianceGuard.purge_raw_audio(chunk_waveform)

        chunk_record = {
            "chunk_index": len(self.chunk_history) + 1,
            "timestamp_sec": round(timestamp_sec, 2),
            "chunk_risk_score": round(chunk_risk, 4),
            "chunk_risk_level": risk_eval["risk_level"],
            "session_risk_score": round(session_risk, 4),
            "session_risk_level": session_level,
            "neural_prob": neural_fake_prob,
            "consecutive_suspicious": self.consecutive_suspicious_count,
            "metrics": forensic["metrics"],
            "glottal": glottal_res,
            "phase": phase_res,
            "sha256": audio_fingerprint[:16] + "..."
        }
        self.chunk_history.append(chunk_record)

        cef_event = EnterpriseTelemetryEngine.generate_cef_event(
            session_assessment,
            prevention_plan,
            {"duration_sec": 3.0, "sha256": audio_fingerprint[:20] + "..."}
        )

        return {
            "call_id": self.call_id,
            "chunk_record": chunk_record,
            "session_assessment": session_assessment,
            "risk_assessment": risk_eval,
            "neural_detector": neural_res,
            "forensic_metrics": forensic["metrics"],
            "glottal_biometrics": glottal_res,
            "phase_forensics": phase_res,
            "prevention_plan": prevention_plan,
            "enterprise_telemetry": {
                "mitre_attack": EnterpriseTelemetryEngine.MITRE_MAPPING,
                "cef_event": cef_event
            },
            "timeline_length": len(self.chunk_history)
        }

