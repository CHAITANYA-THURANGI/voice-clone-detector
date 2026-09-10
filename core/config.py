"""
VoiceShield AI - Real-World Gateway Configuration Manager
Loads settings from .env, environment variables, or dynamic runtime updates.
Handles SMTP Email, Twilio/Fast2SMS, and Android SIM SMS parameters.
"""

import os
from typing import Dict, Any, Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")


def load_dotenv(filepath: str = ENV_PATH) -> Dict[str, str]:
    """Lightweight custom .env parser without external dependencies."""
    loaded = {}
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, val = line.split("=", 1)
                        key = key.strip()
                        val = val.strip().strip("'\"")
                        loaded[key] = val
                        if key not in os.environ:
                            os.environ[key] = val
        except Exception as e:
            print(f"[Config] Warning loading {filepath}: {e}")
    return loaded


# Load initial .env file on module import
_INITIAL_LOADED = load_dotenv()


class GatewayConfig:
    """Central configuration for Real-World Alert Gateways."""

    def __init__(self):
        self.reload()

    def reload(self):
        """Reloads settings from environment and .env."""
        load_dotenv()
        
        # Email / SMTP
        self.smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        self.smtp_use_tls = os.environ.get("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes")
        self.smtp_user = os.environ.get("SMTP_USER", "").strip()
        self.smtp_password = os.environ.get("SMTP_PASSWORD", "").strip()
        self.smtp_sender_name = os.environ.get("SMTP_SENDER_NAME", "VoiceShield AI Cyber Defense")
        self.alert_recipient_email = os.environ.get("ALERT_RECIPIENT_EMAIL", "").strip()

        # SMS
        self.sms_gateway = os.environ.get("SMS_GATEWAY", "android_sim").lower().strip()
        self.alert_recipient_phone = os.environ.get("ALERT_RECIPIENT_PHONE", "").strip()
        
        # Twilio
        self.twilio_account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
        self.twilio_auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
        self.twilio_phone_number = os.environ.get("TWILIO_PHONE_NUMBER", "").strip()

        # Fast2SMS
        self.fast2sms_api_key = os.environ.get("FAST2SMS_API_KEY", "").strip()

        # Call Defense Settings
        self.auto_drop_threshold = float(os.environ.get("AUTO_DROP_RISK_THRESHOLD", "0.75"))
        self.max_chunks = int(os.environ.get("MAX_CHUNKS_PER_CALL", "120"))

    def is_email_configured(self) -> bool:
        """Returns True if minimum required SMTP credentials are present."""
        return bool(self.smtp_user and self.smtp_password and self.smtp_server)

    def is_sms_configured(self) -> bool:
        """Returns True if chosen SMS gateway has required credentials."""
        if self.sms_gateway == "android_sim":
            return True  # Android app dispatches via device SIM directly
        elif self.sms_gateway == "twilio":
            return bool(self.twilio_account_sid and self.twilio_auth_token and self.twilio_phone_number)
        elif self.sms_gateway == "fast2sms":
            return bool(self.fast2sms_api_key)
        return False

    def get_status(self) -> Dict[str, Any]:
        """Returns sanitized status object for UI dashboard."""
        return {
            "email": {
                "configured": self.is_email_configured(),
                "smtp_server": self.smtp_server,
                "smtp_port": self.smtp_port,
                "sender_email": self.smtp_user or "Not configured",
                "recipient_email": self.alert_recipient_email or "Not configured",
                "use_tls": self.smtp_use_tls
            },
            "sms": {
                "configured": self.is_sms_configured(),
                "gateway_mode": self.sms_gateway,
                "recipient_phone": self.alert_recipient_phone or "Not configured",
                "android_sim_ready": True,
                "twilio_ready": bool(self.twilio_account_sid and self.twilio_auth_token),
                "fast2sms_ready": bool(self.fast2sms_api_key)
            },
            "defense": {
                "auto_drop_threshold": self.auto_drop_threshold,
                "max_chunks": self.max_chunks
            }
        }

    def update_runtime(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Dynamically updates gateway settings in-memory and optionally writes to .env."""
        allowed_keys = [
            "SMTP_SERVER", "SMTP_PORT", "SMTP_USE_TLS", "SMTP_USER", "SMTP_PASSWORD",
            "SMTP_SENDER_NAME", "ALERT_RECIPIENT_EMAIL", "SMS_GATEWAY", "ALERT_RECIPIENT_PHONE",
            "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER", "FAST2SMS_API_KEY",
            "AUTO_DROP_RISK_THRESHOLD"
        ]

        for k, v in updates.items():
            key_upper = k.upper()
            if key_upper in allowed_keys and v is not None:
                os.environ[key_upper] = str(v)

        self.reload()
        return self.get_status()


# Global config singleton
config = GatewayConfig()
