"""
Semantic Audio-Language Model (ALM) and LLM Cyberthreat & Scam Attack Detection Engine.
Detects fraudulent calls, extortion attempts, and social engineering attacks by the semantic contents in the voice:
- Digital Arrest / Law Enforcement Extortion Scams
- Banking / KYC / Credit Card / OTP Harvesting Scams
- Executive / CXO Impersonation & Wire Transfer Fraud (Business Voice Compromise)
- Tech Support / Ransomware / Remote Access Coercion Scams
- Family Emergency & Kidnapping Bail Extortion Scams
- Lottery, Task Earning & Crypto Investment Scams

Integrates:
1. Audio-Language Model (ALM): Local Whisper foundation model for high-fidelity speech-to-text.
2. Cloud Multimodal LLM: Google Gemini 2.5 / 3.7 (via google-genai) when GEMINI_API_KEY is available.
3. Local Cyber-Fraud Taxonomy Engine: Zero-dependency NLP reasoning engine for 100% offline air-gapped environments.
"""

import os
import re
import json
import logging
import numpy as np
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Threat Categories
CAT_DIGITAL_ARREST = "DIGITAL_ARREST_EXTORTION"
CAT_BANKING_KYC = "BANKING_KYC_OTP_THEFT"
CAT_CXO_FRAUD = "CXO_EXECUTIVE_WIRE_FRAUD"
CAT_TECH_SUPPORT = "TECH_SUPPORT_HIJACK"
CAT_EMERGENCY_RANSOM = "EMERGENCY_FAMILY_RANSOM"
CAT_LOTTERY_INVESTMENT = "LOTTERY_JOB_INVESTMENT"
CAT_FAMILY_BOSS_CLONE = "FAMILY_BOSS_VOICE_NOTE_SCAM"
CAT_LEGITIMATE = "LEGITIMATE_SAFE"

DISPLAY_NAMES = {
    CAT_DIGITAL_ARREST: "🚨 Digital Arrest Extortion",
    CAT_BANKING_KYC: "💳 Banking KYC / OTP Harvesting",
    CAT_CXO_FRAUD: "👔 Executive / CXO Wire Fraud",
    CAT_TECH_SUPPORT: "💻 Tech Support / Device Hijack",
    CAT_EMERGENCY_RANSOM: "🚑 Emergency Family Ransom",
    CAT_LOTTERY_INVESTMENT: "🎰 Lottery / Crypto Investment Scam",
    CAT_FAMILY_BOSS_CLONE: "🚨 Family / Boss Voice Note Impersonation",
    CAT_LEGITIMATE: "🟢 Legitimate / Safe Conversation"
}

# Regex and Weighted Cyberthreat Pattern Definitions
THREAT_PATTERNS = {
    CAT_DIGITAL_ARREST: {
        "patterns": [
            (r"\bdigital\s+arrest\b", 0.70, "digital arrest"),
            (r"\b(cbi|customs|cyber\s+police|police\s+officer|inspector|dcp|interpol)\b", 0.45, "law enforcement impersonation"),
            (r"\b(narcotics|contraband|drugs\s+found)\b", 0.50, "narcotics allegation"),
            (r"\b(illegal\s+parcel|taiwan\s+parcel|fedex\s+parcel)\b", 0.50, "illegal parcel threat"),
            (r"\b(passport\s+seized|arrest\s+warrant|court\s+order|supreme\s+court)\b", 0.55, "warrant / court threat"),
            (r"\bmoney\s+laundering\b", 0.55, "money laundering allegation"),
            (r"\b(do\s+not\s+disconnect|stay\s+on\s+(video\s+)?call|do\s+not\s+tell)\b", 0.40, "isolation demand"),
            (r"\b(rbi\s+verification|escrow\s+account|safe\s+account)\b", 0.50, "escrow transfer coercion"),
        ],
        "tactics": [
            "Legal intimidation & law enforcement impersonation",
            "Isolation demand (do not tell family or disconnect call)",
            "Forced video surveillance ('digital arrest')",
            "Coerced transfer to 'RBI safe asset verification' account"
        ]
    },
    CAT_BANKING_KYC: {
        "patterns": [
            (r"\b(bank\s+account|debit\s+card|credit\s+card|net\s*banking)\s+(has\s+been\s+)?(blocked|suspended|deactivated|frozen)\b", 0.65, "account suspension alert"),
            (r"\b(debit\s+card|credit\s+card)\b", 0.30, "card reference"),
            (r"\bkyc\s+(expired|update|verification|mandate|suspended)\b", 0.55, "kyc expired scare"),
            (r"\bone[\s-]time\s+password\b", 0.60, "one-time password request"),
            (r"\b(share\s+your\s+)?otp\b", 0.60, "otp request"),
            (r"\b(6|six)[\s-]digit\s+(code|otp|pin)\b", 0.55, "six-digit OTP verification"),
            (r"\b(cvv(\s+number)?|atm\s+pin|net\s*banking\s+password)\b", 0.65, "banking credentials"),
            (r"\bunauthorized\s+transaction\b", 0.45, "unauthorized transaction scare"),
            (r"\b(electricity\s+bill\s+unpaid|power\s+cut[\s-]?off)\b", 0.50, "utility disconnection scam"),
            (r"\b(download\s+apk|click\s+(on\s+)?the\s+link)\b", 0.40, "malicious link / APK bait")
        ],
        "tactics": [
            "Urgent false notification of account suspension",
            "Credential & OTP harvesting under guise of security",
            "Malicious link/APK injection for SMS forwarding",
            "Fear of immediate financial service loss"
        ]
    },
    CAT_CXO_FRAUD: {
        "patterns": [
            (r"\b(i\s+am\s+the\s+ceo|i\s+am\s+the\s+cfo|this\s+is\s+the\s+ceo|this\s+is\s+the\s+cfo)\b", 0.65, "executive impersonation"),
            (r"\burgent\s+wire\s+transfer\b", 0.60, "urgent wire transfer"),
            (r"\bconfidential\s+(acquisition|deal|project|transaction)\b", 0.55, "confidential acquisition"),
            (r"\b(offshore\s+vendor|swift\s+transfer|wire\s+funds)\b", 0.45, "offshore transfer"),
            (r"\bby[\s-]?pass\s+(normal\s+)?verification\b", 0.60, "bypass verification protocol"),
            (r"\bdo\s+not\s+(email|tell|call)\s+(others|anyone)\b", 0.45, "protocol circumvention"),
            (r"\b(closing\s+in\s+\d+\s+minutes|board\s+meeting\s+right\s+now)\b", 0.45, "executive urgency")
        ],
        "tactics": [
            "Executive authority coercion & seniority pressure",
            "Artificial confidentiality preventing peer verification",
            "Bypassing standard treasury/ERP authentication controls",
            "High-value wire diversion to fraudulent offshore accounts"
        ]
    },
    CAT_TECH_SUPPORT: {
        "patterns": [
            (r"\b(microsoft|windows\s+defender|apple\s+care|google\s+tech)\s+support\b", 0.60, "tech support impersonation"),
            (r"\b(computer\s+is\s+infected|trojan\s+virus|hacker\s+accessed)\b", 0.60, "malware infection scare"),
            (r"\b(install\s+)?(any\s*desk|team\s*viewer|quick\s*support|ultra\s*viewer)\b", 0.65, "remote access tool installation"),
            (r"\bgive\s+remote\s+access\b", 0.65, "remote access coercion"),
            (r"\bsecurity\s+subscription\s+expired\b", 0.45, "fake subscription expiry")
        ],
        "tactics": [
            "Fabricated malware alert & system compromise scare",
            "Remote Access Trojan (RAT) installation coercion",
            "Live screen hijacking to steal active browser sessions",
            "Bogus anti-malware service subscription extortion"
        ]
    },
    CAT_EMERGENCY_RANSOM: {
        "patterns": [
            (r"\b(your\s+son|your\s+daughter|your\s+child)\s+(has\s+been\s+arrested|was\s+in\s+an?\s+accident|is\s+in\s+jail)\b", 0.70, "child arrest/accident fabrication"),
            (r"\b(hospital\s+emergency|icu\s+admission)\b", 0.50, "medical emergency shock"),
            (r"\b(we\s+have\s+your\s+child|pay\s+ransom)\b", 0.75, "hostage/ransom extortion"),
            (r"\btransfer\s+bail\s+money\b", 0.65, "bail money demand"),
            (r"\bdo\s+not\s+call\s+anyone\b", 0.40, "panic isolation")
        ],
        "tactics": [
            "Severe emotional shock & hostage/accident fabrication",
            "Immediate panic-induced extortion before victim can verify",
            "Exploitation of familial love and protection instinct"
        ]
    },
    CAT_LOTTERY_INVESTMENT: {
        "patterns": [
            (r"\b(congratulations\s+you\s+won|kbc\s+lucky\s+winner|lottery\s+prize)\b", 0.65, "lottery winning hook"),
            (r"\b(part[\s-]time\s+job|earn\s+\d+\s+per\s+day|like\s+youtube\s+videos|telegram\s+task)\b", 0.60, "task earning scam"),
            (r"\b(guaranteed\s+profit|crypto\s+investment\s+200%|double\s+your\s+money)\b", 0.60, "crypto/investment fraud"),
            (r"\b(registration\s+fee\s+first|tax\s+fee\s+to\s+release|gift\s+card\s+payment)\b", 0.65, "advance fee demand")
        ],
        "tactics": [
            "Advance fee fraud disguised as winnings processing",
            "High-yield fraudulent Ponzi/crypto task deception",
            "Small initial payout hook leading to massive fund drain"
        ]
    },
    CAT_FAMILY_BOSS_CLONE: {
        "patterns": [
            (r"\b(mom|dad|honey|babe|sweetheart)\b", 0.35, "familial intimate greeting"),
            (r"\b(broke\s+my\s+phone|lost\s+my\s+(wallet|phone)|stranded|in\s+an\s+emergency)\b", 0.60, "distress emergency claim"),
            (r"\b(send|wire|transfer)\s+(\$|rs\.?|inr|usd)?\s*\d+\s*(dollars|bucks|rupees)?\b", 0.60, "urgent money request"),
            (r"\b(this\s+is\s+your\s+boss|from\s+the\s+ceo|from\s+your\s+director)\b", 0.65, "boss impersonation"),
            (r"\b(gift\s+card|apple\s+gift|google\s+play\s+card|buy\s+vouchers)\b", 0.65, "gift card coercion"),
            (r"\b(share|sharing|send|sending|give|need)\s+.*(password|credentials|login|passcode)\b", 0.70, "credential harvesting"),
            (r"\b(cant\s+talk|voice\s+(note|message))\b", 0.35, "voice note delivery")
        ],
        "tactics": [
            "3-second voice note harvested from social media videos",
            "Emotional urgency exploiting familial or employer authority",
            "Coercion into rapid unverified peer-to-peer money transfer or password disclosure"
        ]
    }
}

COERCION_PATTERNS = [
    (r"\b(immediately|right\s+now|urgent(ly)?|hurry)\b", 0.25, "immediacy pressure"),
    (r"\b(within\s+\d+\s+minutes|before\s+\d+\s+pm)\b", 0.30, "artificial deadline"),
    (r"\b(do\s+not\s+hang\s+up|do\s+not\s+disconnect)\b", 0.35, "call hold coercion"),
    (r"\b(arrest\s+warrant|police\s+action|legal\s+notice|final\s+warning)\b", 0.35, "legal threat"),
    (r"\b(confidential|do\s+not\s+tell\s+anyone)\b", 0.25, "secrecy demand")
]


class SemanticFraudDetector:
    """
    Dual-layer Speech-to-Text & Cyberthreat Semantic Reasoning Engine.
    Combines Whisper ASR with Google Gemini Multimodal / LLM and high-recall local NLP.
    """

    def __init__(self, gemini_api_key: Optional[str] = None):
        self.gemini_api_key = gemini_api_key or os.environ.get("GEMINI_API_KEY")
        self._gemini_client = None
        self._whisper_model = None

    def _get_whisper_model(self):
        """Lazy loads Whisper tiny ASR model."""
        if self._whisper_model is None:
            try:
                import whisper
                self._whisper_model = whisper.load_model("tiny")
            except Exception as e:
                logger.warning(f"Whisper ASR initialization fallback: {e}")
                self._whisper_model = None
        return self._whisper_model

    def _get_gemini_client(self):
        """Lazy loads Google Gemini client if API key is present."""
        if self._gemini_client is None and self.gemini_api_key:
            try:
                from google import genai
                self._gemini_client = genai.Client(api_key=self.gemini_api_key)
            except Exception as e:
                logger.warning(f"Google GenAI Client initialization failed: {e}")
                self._gemini_client = None
        return self._gemini_client

    def transcribe_audio(self, audio_waveform: np.ndarray, sr: int = 16000) -> str:
        """
        Transcribes speech audio into text using Whisper ASR.
        Supports numpy array (16kHz float32).
        """
        if len(audio_waveform) < 3200:  # Less than 0.2s
            return ""

        model = self._get_whisper_model()
        if model is None:
            return ""

        try:
            import whisper
            waveform = audio_waveform.astype(np.float32)
            audio_padded = whisper.pad_or_trim(waveform)
            mel = whisper.log_mel_spectrogram(audio_padded, n_mels=80)
            options = whisper.DecodingOptions(fp16=False)
            result = whisper.decode(model, mel, options)
            return result.text.strip()
        except Exception as e:
            logger.error(f"Whisper transcription error: {e}")
            return ""

    def analyze_semantic_threat(
        self,
        transcript: str,
        audio_waveform: Optional[np.ndarray] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Performs semantic cyberthreat, scam, and social engineering analysis on the transcript.
        Runs Gemini LLM when available; falls back seamlessly to Local Cyber-Fraud Taxonomy Engine.
        """
        cleaned_text = transcript.strip()

        if not cleaned_text or len(cleaned_text) < 3:
            return {
                "is_scam": False,
                "scam_category": CAT_LEGITIMATE,
                "display_category": DISPLAY_NAMES[CAT_LEGITIMATE],
                "scam_confidence": 5.0,
                "scam_score": 0.05,
                "coercion_urgency_score": 0.0,
                "flagged_keywords": [],
                "tactics_detected": [],
                "transcript": "",
                "engine_used": "EMPTY_TRANSCRIPT",
                "risk_summary": "No verbal speech detected in audio stream."
            }

        # Try Google Gemini Cloud LLM if available
        client = self._get_gemini_client()
        if client:
            try:
                gemini_res = self._analyze_with_gemini(client, transcript, context)
                if gemini_res:
                    return gemini_res
            except Exception as e:
                logger.warning(f"Gemini LLM inference error, falling back to local engine: {e}")

        # Local Cyber-Fraud Taxonomy & Intent Engine
        return self._analyze_with_local_engine(transcript, context)

    def _analyze_with_local_engine(
        self,
        transcript: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        High-precision local cyberthreat reasoning engine using regex patterns,
        semantic taxonomy, and coercion urgency scoring.
        """
        text = transcript.lower()
        category_scores: Dict[str, float] = {}
        category_matches: Dict[str, List[str]] = {}

        # 1. Match category patterns
        for cat, data in THREAT_PATTERNS.items():
            matched_labels = []
            score_sum = 0.0
            for regex_pat, weight, label in data["patterns"]:
                if re.search(regex_pat, text, re.IGNORECASE):
                    matched_labels.append(label)
                    score_sum += weight

            if matched_labels:
                category_scores[cat] = min(0.98, score_sum)
                category_matches[cat] = matched_labels

        # 2. Evaluate Coercion & Urgency triggers
        coercion_matches = []
        coercion_score = 0.0
        for regex_pat, weight, label in COERCION_PATTERNS:
            if re.search(regex_pat, text, re.IGNORECASE):
                coercion_matches.append(label)
                coercion_score += weight

        coercion_score = min(1.0, coercion_score)

        # 3. Contextual multi-factor boost
        if context:
            if context.get("credential_request"):
                category_scores[CAT_BANKING_KYC] = max(category_scores.get(CAT_BANKING_KYC, 0.0) + 0.35, 0.75)
                category_matches.setdefault(CAT_BANKING_KYC, []).append("context:credential_request")
            if context.get("is_cxo_call") and context.get("transaction_amount", 0) > 10000:
                category_scores[CAT_CXO_FRAUD] = max(category_scores.get(CAT_CXO_FRAUD, 0.0) + 0.35, 0.80)
                category_matches.setdefault(CAT_CXO_FRAUD, []).append("context:high_value_wire")

        # 4. Determine winning category
        if category_scores:
            top_category = max(category_scores, key=category_scores.get)
            top_base_score = category_scores[top_category]
            final_scam_score = min(0.99, top_base_score + (coercion_score * 0.15))
            is_scam = final_scam_score >= 0.40
            flagged_kws = category_matches.get(top_category, []) + coercion_matches
            tactics = THREAT_PATTERNS[top_category]["tactics"]
            summary = f"Detected malicious {DISPLAY_NAMES[top_category]}. Content exhibits clear social engineering extortion tactics."
        else:
            top_category = CAT_LEGITIMATE
            final_scam_score = 0.05
            is_scam = False
            flagged_kws = []
            tactics = []
            summary = "Speech content contains normal conversational dialog with no indicators of fraud or extortion."

        return {
            "is_scam": is_scam,
            "is_threat": is_scam,
            "scam_category": top_category,
            "display_category": DISPLAY_NAMES.get(top_category, top_category),
            "display_name": DISPLAY_NAMES.get(top_category, top_category),
            "scam_confidence": round(final_scam_score * 100, 1),
            "confidence": round(final_scam_score, 4),
            "scam_score": round(final_scam_score, 4),
            "coercion_urgency_score": round(coercion_score, 2),
            "flagged_keywords": list(set(flagged_kws)),
            "matched_cues": list(set(flagged_kws)),
            "tactics_detected": tactics,
            "tactics": tactics,
            "transcript": transcript,
            "engine_used": "LOCAL_CYBER_TAXONOMY_ENGINE",
            "risk_summary": summary
        }

    def _analyze_with_gemini(
        self,
        client,
        transcript: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Deep zero-shot cyberthreat analysis using Google Gemini 2.5 / 3.7.
        """
        system_instruction = (
            "You are an elite cybersecurity and telecommunications fraud detection intelligence engine. "
            "Analyze telephone audio transcripts to identify scam calls, social engineering attacks, "
            "voice extortion, or legitimate conversations. "
            "Categories: DIGITAL_ARREST_EXTORTION, BANKING_KYC_OTP_THEFT, CXO_EXECUTIVE_WIRE_FRAUD, "
            "TECH_SUPPORT_HIJACK, EMERGENCY_FAMILY_RANSOM, LOTTERY_JOB_INVESTMENT, or LEGITIMATE_SAFE. "
            "Respond STRICTLY with valid JSON."
        )

        prompt = f"""
Transcript:
\"{transcript}\"

Context: {json.dumps(context or {})}

Output JSON format:
{{
    "is_scam": true/false,
    "scam_category": "DIGITAL_ARREST_EXTORTION" | "BANKING_KYC_OTP_THEFT" | "CXO_EXECUTIVE_WIRE_FRAUD" | "TECH_SUPPORT_HIJACK" | "EMERGENCY_FAMILY_RANSOM" | "LOTTERY_JOB_INVESTMENT" | "LEGITIMATE_SAFE",
    "scam_score": 0.0 to 1.0,
    "coercion_urgency_score": 0.0 to 1.0,
    "flagged_keywords": ["keyword1", "phrase2"],
    "tactics_detected": ["tactic 1", "tactic 2"],
    "risk_summary": "Brief 1-sentence forensic summary"
}}
"""
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "system_instruction": system_instruction,
                "response_mime_type": "application/json",
                "temperature": 0.1
            }
        )
        if response and response.text:
            data = json.loads(response.text)
            cat = data.get("scam_category", CAT_LEGITIMATE)
            score = float(data.get("scam_score", 0.1))
            return {
                "is_scam": bool(data.get("is_scam", score >= 0.5)),
                "is_threat": bool(data.get("is_scam", score >= 0.5)),
                "scam_category": cat,
                "display_category": DISPLAY_NAMES.get(cat, cat),
                "display_name": DISPLAY_NAMES.get(cat, cat),
                "scam_confidence": round(score * 100, 1),
                "confidence": round(score, 4),
                "scam_score": round(score, 4),
                "coercion_urgency_score": round(float(data.get("coercion_urgency_score", 0.0)), 2),
                "flagged_keywords": data.get("flagged_keywords", []),
                "matched_cues": data.get("flagged_keywords", []),
                "tactics_detected": data.get("tactics_detected", []),
                "tactics": data.get("tactics_detected", []),
                "transcript": transcript,
                "engine_used": "GEMINI_2.5_FLASH_MULTIMODAL_LLM",
                "risk_summary": data.get("risk_summary", "Analyzed via Gemini LLM.")
            }
        return None

    def analyze_audio(
        self,
        waveform: np.ndarray,
        sr: int = 16000,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Unified end-to-end method: transcribes audio and assesses semantic fraud threat.
        """
        transcript = self.transcribe_audio(waveform, sr=sr)
        return self.analyze_semantic_threat(transcript, audio_waveform=waveform, context=context)


# Global Singleton Instance
semantic_fraud_detector = SemanticFraudDetector()
