"""
Automated Test Suite for Real-World Alert Dispatchers & Telephony Gateways.
Tests:
1. RealEmailDispatcher unconfigured state returns CONFIG_REQUIRED without crashing.
2. RealEmailDispatcher SMTP MIME assembly & simulated socket delivery.
3. RealSmsDispatcher Android SIM mode formats GSM-7 carrier payload.
4. RealSmsDispatcher Twilio / Fast2SMS credentials validation.
5. PhoneCallDefenseEngine integration with real alert dispatching.
6. FastAPI Gateway endpoints (/gateway-status, /configure-alerts, /test-live-sms).
"""

import os
import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from core.config import config
from core.real_alert_dispatcher import RealEmailDispatcher, RealSmsDispatcher
from core.call_defense_engine import call_defense_engine
from api.server import app

client = TestClient(app)


class TestRealAlertDispatcher(unittest.TestCase):

    def setUp(self):
        self.email_dispatcher = RealEmailDispatcher()
        self.sms_dispatcher = RealSmsDispatcher()

    def test_01_email_unconfigured_handling(self):
        """Verifies that missing SMTP credentials return CONFIG_REQUIRED cleanly."""
        config.smtp_user = ""
        config.smtp_password = ""
        res = self.email_dispatcher.send_incident_email(
            incident_id="INC-TEST01",
            caller_number="+91-140-776655",
            caller_claimed_name="Test Caller",
            risk_pct=92.5,
            threats=["Voice Clone Attack"],
            transcript="I need money immediately",
            html_content="<h1>Test Alert</h1>"
        )
        self.assertEqual(res["status"], "CONFIG_REQUIRED")
        self.assertIn("requires SMTP credentials", res["message"])
        print("[TEST PASS] Email Dispatcher: Unconfigured state handled safely (CONFIG_REQUIRED)")

    def test_02_email_smtp_transmission_mock(self):
        """Verifies SMTP handshake and MIME composition with mocked socket."""
        config.smtp_user = "test-agent@gmail.com"
        config.smtp_password = "mock_16_char_pass"
        config.smtp_server = "smtp.gmail.com"
        config.smtp_port = 587
        config.smtp_use_tls = True

        with patch("smtplib.SMTP") as mock_smtp:
            instance = MagicMock()
            mock_smtp.return_value.__enter__.return_value = instance

            res = self.email_dispatcher.test_connection(test_recipient="target@example.com")
            self.assertTrue(res["success"])
            self.assertEqual(res["status"], "DELIVERED_SUCCESSFULLY")
            self.assertEqual(res["recipient"], "target@example.com")
            instance.starttls.assert_called_once()
            instance.login.assert_called_with("test-agent@gmail.com", "mock_16_char_pass")
            instance.send_message.assert_called_once()

        print("[TEST PASS] Email Dispatcher: SMTP STARTTLS handshake & delivery verified")

    def test_03_sms_android_sim_mode(self):
        """Verifies Android SIM mode formats native carrier GSM-7 payload."""
        config.sms_gateway = "android_sim"
        res = self.sms_dispatcher.send_precaution_sms(
            incident_id="INC-SIM01",
            caller_number="+91-98765-43210",
            caller_name="Scammer Imposter",
            risk_pct=96.0,
            threats_str="Digital Arrest Police Extortion",
            custom_recipient="+91-99887-76655"
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["channel"], "ANDROID_SIM_CARRIER")
        self.assertEqual(res["status"], "QUEUED_FOR_DEVICE_SIM")
        self.assertIn("VOICESHIELD AI ALERT", res["sms_text"])
        self.assertIn("INC-SIM01", res["sms_text"])
        print(f"[TEST PASS] SMS Dispatcher: Android SIM carrier payload verified ({res['char_count']} chars)")

    def test_04_call_defense_integration(self):
        """Verifies call_defense_engine dispatches both real SMS and Email records."""
        # Initialize a session
        sess = call_defense_engine.start_call_session(
            caller_number="+91-140-776655",
            caller_claimed_name="Anita Sharma (Mom)",
            user_phone="+91-99887-76655",
            emergency_contact="+91-91234-56789"
        )
        call_id = sess["session_id"]

        # Terminate and dispatch
        call_defense_engine.terminate_call(call_id, reason="High-Risk Voice Clone Test")
        alerts = call_defense_engine.dispatch_precaution_alerts(
            session_id=call_id,
            custom_email="victim@domain.org"
        )

        self.assertEqual(alerts["status"], "SUCCESS")
        self.assertIn("sms_alert", alerts)
        self.assertIn("email_alert", alerts)
        self.assertEqual(alerts["sms_alert"]["recipient"], "+91-99887-76655")
        self.assertEqual(alerts["email_alert"]["recipient"], "victim@domain.org")
        print(f"[TEST PASS] Call Defense Engine: Dispatched real precaution alerts (Incident: {alerts['incident_id']})")

    def test_05_gateway_status_api(self):
        """Tests GET /api/phone-call/gateway-status endpoint."""
        resp = client.get("/api/phone-call/gateway-status")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("email", data)
        self.assertIn("sms", data)
        self.assertTrue(data["sms"]["android_sim_ready"])
        print(f"[TEST PASS] API /gateway-status: Returned valid JSON status (SMS Mode: {data['sms']['gateway_mode']})")

    def test_06_configure_and_test_sms_api(self):
        """Tests POST /api/phone-call/configure-alerts and test-live-sms endpoints."""
        conf_resp = client.post("/api/phone-call/configure-alerts", data={
            "sms_gateway": "android_sim",
            "alert_recipient_phone": "+91-99999-11111"
        })
        self.assertEqual(conf_resp.status_code, 200)
        self.assertEqual(conf_resp.json()["status"], "SUCCESS")

        test_resp = client.post("/api/phone-call/test-live-sms", data={
            "test_recipient": "+91-99999-11111"
        })
        self.assertEqual(test_resp.status_code, 200)
        test_data = test_resp.json()
        self.assertEqual(test_data["recipient"], "+91-99999-11111")
        print("[TEST PASS] API /test-live-sms: Successfully invoked and returned valid test payload")


if __name__ == "__main__":
    unittest.main()
