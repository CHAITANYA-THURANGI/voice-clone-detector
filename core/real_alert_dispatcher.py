"""
VoiceShield AI - Real-World Multi-Channel Alert Dispatcher
Executes REAL-WORLD email delivery via live SMTP (Gmail, Outlook, custom)
and REAL-WORLD SMS delivery via Android SIM (native device quota) or Cloud Gateways (Twilio, Fast2SMS).
"""

import os
import smtplib
import ssl
import time
import uuid
import urllib.parse
import urllib.request
import base64
import json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any, Optional, List

from core.config import config


class RealEmailDispatcher:
    """
    Direct Real-World SMTP Email Dispatcher.
    Uses standard library smtplib + ssl to transmit responsive HTML incident reports
    directly to user inboxes via Gmail App Passwords, Outlook, or corporate mail servers.
    """

    def __init__(self):
        pass

    def send_incident_email(
        self,
        incident_id: str,
        caller_number: str,
        caller_claimed_name: str,
        risk_pct: float,
        threats: List[str],
        transcript: str,
        html_content: str,
        recipient_email: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Sends an actual, live cyber incident email alert via configured SMTP server.
        """
        target_email = recipient_email or config.alert_recipient_email or config.smtp_user
        if not config.is_email_configured():
            return {
                "status": "CONFIG_REQUIRED",
                "channel": "EMAIL_SMTP",
                "message": (
                    "Live email sending requires SMTP credentials. Please configure your "
                    "Gmail/Outlook user and App Password in .env or via the dashboard."
                ),
                "recipient": target_email or "Not set",
                "incident_id": incident_id,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }

        if not target_email:
            return {
                "status": "ERROR_NO_RECIPIENT",
                "channel": "EMAIL_SMTP",
                "message": "No recipient email address provided.",
                "incident_id": incident_id
            }

        subject = f"🚨 [CRITICAL ALERT] VoiceShield Intercepted Cyber-Extortion Call ({incident_id})"
        sender = f"{config.smtp_sender_name} <{config.smtp_user}>"

        # Construct MIME message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = target_email
        msg["X-VoiceShield-Incident"] = incident_id
        msg["X-Priority"] = "1"  # High priority flag

        # Plain-text alternative
        threats_str = ", ".join(threats) if threats else "AI Voice Cloning / Scammer Attack"
        plain_text = (
            f"VOICESHIELD AI CYBER DEFENSE ALERT\n"
            f"Incident Reference: {incident_id}\n"
            f"Timestamp: {time.strftime('%d %b %Y, %H:%M:%S UTC', time.gmtime())}\n\n"
            f"ALERT: An incoming phone call was AUTOMATICALLY TERMINATED by VoiceShield AI.\n"
            f"Caller Number: {caller_number}\n"
            f"Claimed Identity: {caller_claimed_name}\n"
            f"Composite Threat Risk: {risk_pct}%\n"
            f"Detected Threat Factors: {threats_str}\n\n"
            f"Caller Transcript:\n\"{transcript}\"\n\n"
            f"MANDATORY SECURITY ACTIONS:\n"
            f"1. Do NOT transfer funds, share OTPs, or provide remote access.\n"
            f"2. Do NOT dial back this caller number.\n"
            f"3. Verify through secondary verified contacts.\n"
            f"4. Official reports can be lodged at cybercrime.gov.in."
        )

        part1 = MIMEText(plain_text, "plain", "utf-8")
        part2 = MIMEText(html_content, "html", "utf-8")
        msg.attach(part1)
        msg.attach(part2)

        # Transmit via SMTP
        return self._transmit(msg, config.smtp_user, target_email, incident_id)

    def test_connection(self, test_recipient: Optional[str] = None) -> Dict[str, Any]:
        """
        Sends a live test verification email to confirm SMTP connectivity and credentials.
        """
        if not config.is_email_configured():
            return {
                "success": False,
                "status": "CONFIG_REQUIRED",
                "error": "SMTP credentials are not configured in .env or settings."
            }

        target = test_recipient or config.alert_recipient_email or config.smtp_user
        test_id = f"TEST-{uuid.uuid4().hex[:6].upper()}"

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"✅ VoiceShield AI SMTP Gateway Verification ({test_id})"
        msg["From"] = f"{config.smtp_sender_name} <{config.smtp_user}>"
        msg["To"] = target

        html_body = f"""
        <div style="font-family: sans-serif; background: #0f172a; color: #f8fafc; padding: 24px; border-radius: 10px; max-width: 500px;">
          <h2 style="color: #10b981; margin-top: 0;">✅ Gateway Operational</h2>
          <p>This confirms that <strong>VoiceShield AI</strong> is successfully connected to your email account (<code>{config.smtp_user}</code>).</p>
          <p>Real cyber-extortion alerts and emergency precaution advisories will be delivered directly here whenever high-risk voice clones or phone fraud are detected.</p>
          <div style="background: rgba(255,255,255,0.05); padding: 12px; border-radius: 6px; font-size: 13px; color: #94a3b8;">
            <b>SMTP Host:</b> {config.smtp_server}:{config.smtp_port}<br>
            <b>Security:</b> {'STARTTLS' if config.smtp_use_tls else 'SSL'}<br>
            <b>Verified At:</b> {time.strftime('%d %b %Y, %H:%M:%S UTC', time.gmtime())}
          </div>
        </div>
        """
        msg.attach(MIMEText("VoiceShield AI SMTP Gateway is connected and operational.", "plain"))
        msg.attach(MIMEText(html_body, "html"))

        return self._transmit(msg, config.smtp_user, target, test_id)

    def _transmit(self, msg: MIMEMultipart, sender: str, recipient: str, ref_id: str) -> Dict[str, Any]:
        """Low-level socket execution of SMTP handshake and transmission."""
        try:
            context = ssl.create_default_context()
            
            if config.smtp_port == 465:
                # SSL Direct Connection
                with smtplib.SMTP_SSL(config.smtp_server, config.smtp_port, context=context, timeout=15) as server:
                    server.login(config.smtp_user, config.smtp_password)
                    server.send_message(msg)
            else:
                # Standard Port 587 STARTTLS
                with smtplib.SMTP(config.smtp_server, config.smtp_port, timeout=15) as server:
                    if config.smtp_use_tls:
                        server.starttls(context=context)
                    server.login(config.smtp_user, config.smtp_password)
                    server.send_message(msg)

            return {
                "success": True,
                "status": "DELIVERED_SUCCESSFULLY",
                "channel": "EMAIL_SMTP",
                "smtp_server": f"{config.smtp_server}:{config.smtp_port}",
                "sender": config.smtp_user,
                "recipient": recipient,
                "ref_id": ref_id,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }
        except smtplib.SMTPAuthenticationError as e:
            return {
                "success": False,
                "status": "AUTH_FAILED",
                "channel": "EMAIL_SMTP",
                "error": f"SMTP Authentication failed: {e}. Check your email and 16-digit App Password.",
                "ref_id": ref_id
            }
        except Exception as e:
            return {
                "success": False,
                "status": "CONNECTION_FAILED",
                "channel": "EMAIL_SMTP",
                "error": f"Failed to deliver via SMTP: {str(e)}",
                "ref_id": ref_id
            }


class RealSmsDispatcher:
    """
    Multi-Channel Real-World SMS Dispatcher.
    Supports:
    1. ANDROID_SIM: Formats native device SMS commands dispatched via Android SmsManager
       utilizing the user's mobile carrier plan limit with ZERO extra charges.
    2. TWILIO: Direct live HTTP POST to Twilio Cloud REST API.
    3. FAST2SMS: Direct live HTTP POST to Fast2SMS Indian gateway API.
    """

    def __init__(self):
        pass

    def send_precaution_sms(
        self,
        incident_id: str,
        caller_number: str,
        caller_name: str,
        risk_pct: float,
        threats_str: str,
        custom_recipient: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Dispatches real SMS warning to the target user/contacts.
        """
        recipient = custom_recipient or config.alert_recipient_phone or "+91-99887-76655"
        timestamp = time.strftime("%H:%M UTC", time.gmtime())

        # Compact GSM-7 compliant text
        sms_text = (
            f"🚨 VOICESHIELD AI ALERT [{incident_id}]:\n"
            f"Call from {caller_number} ({caller_name}) AUTO-TERMINATED ({timestamp}).\n"
            f"Threat: {threats_str} ({risk_pct}% risk).\n"
            f"DO NOT send money or OTPs. Verify directly with {caller_name} on primary number."
        )

        gateway = config.sms_gateway.lower()

        if gateway == "android_sim":
            return self._dispatch_via_android_sim(incident_id, recipient, sms_text)
        elif gateway == "twilio":
            return self._dispatch_via_twilio(incident_id, recipient, sms_text)
        elif gateway == "fast2sms":
            return self._dispatch_via_fast2sms(incident_id, recipient, sms_text)
        else:
            return self._dispatch_via_android_sim(incident_id, recipient, sms_text)

    def _dispatch_via_android_sim(self, incident_id: str, recipient: str, text: str) -> Dict[str, Any]:
        """
        Packages payload for Android App native SIM delivery.
        The Android InCallService / DeviceSmsSender receives this and calls SmsManager.
        """
        return {
            "success": True,
            "status": "QUEUED_FOR_DEVICE_SIM",
            "channel": "ANDROID_SIM_CARRIER",
            "gateway_description": "Android Native SIM Card (Carrier Plan SMS Quota)",
            "recipient": recipient,
            "incident_id": incident_id,
            "char_count": len(text),
            "sms_text": text,
            "instructions": "Android app executes SmsManager.getDefault().sendTextMessage(...) using SIM quota.",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }

    def _dispatch_via_twilio(self, incident_id: str, recipient: str, text: str) -> Dict[str, Any]:
        """Makes real HTTP POST to Twilio Messages endpoint using standard library urllib."""
        if not (config.twilio_account_sid and config.twilio_auth_token and config.twilio_phone_number):
            return {
                "success": False,
                "status": "CONFIG_REQUIRED",
                "channel": "TWILIO_REST_API",
                "error": "Twilio Account SID, Auth Token, or Twilio Phone Number not configured in .env."
            }

        url = f"https://api.twilio.com/2010-04-01/Accounts/{config.twilio_account_sid}/Messages.json"
        data = urllib.parse.urlencode({
            "To": recipient,
            "From": config.twilio_phone_number,
            "Body": text
        }).encode("utf-8")

        req = urllib.request.Request(url, data=data, method="POST")
        auth_str = f"{config.twilio_account_sid}:{config.twilio_auth_token}"
        auth_bytes = base64.b64encode(auth_str.encode("utf-8")).decode("ascii")
        req.add_header("Authorization", f"Basic {auth_bytes}")

        try:
            with urllib.request.urlopen(req, timeout=12) as response:
                body = response.read().decode("utf-8")
                res_json = json.loads(body)
                return {
                    "success": True,
                    "status": "DELIVERED_SUCCESSFULLY",
                    "channel": "TWILIO_REST_API",
                    "sid": res_json.get("sid"),
                    "recipient": recipient,
                    "incident_id": incident_id,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                }
        except Exception as e:
            return {
                "success": False,
                "status": "TWILIO_API_ERROR",
                "channel": "TWILIO_REST_API",
                "error": f"Twilio API request failed: {str(e)}",
                "incident_id": incident_id
            }

    def _dispatch_via_fast2sms(self, incident_id: str, recipient: str, text: str) -> Dict[str, Any]:
        """Makes real HTTP POST to Fast2SMS Quick Transactional endpoint."""
        if not config.fast2sms_api_key:
            return {
                "success": False,
                "status": "CONFIG_REQUIRED",
                "channel": "FAST2SMS_API",
                "error": "Fast2SMS API Key not configured in .env."
            }

        url = "https://www.fast2sms.com/dev/bulkV2"
        # Extract digits only for Indian 10-digit mobile
        clean_num = "".join([c for c in recipient if c.isdigit()])
        if clean_num.startswith("91") and len(clean_num) > 10:
            clean_num = clean_num[2:]

        headers = {
            "authorization": config.fast2sms_api_key,
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = urllib.parse.urlencode({
            "message": text,
            "language": "english",
            "route": "q",
            "numbers": clean_num
        }).encode("utf-8")

        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=12) as response:
                body = response.read().decode("utf-8")
                res_json = json.loads(body)
                return {
                    "success": res_json.get("return", False),
                    "status": "DELIVERED_SUCCESSFULLY" if res_json.get("return") else "FAST2SMS_REJECTED",
                    "channel": "FAST2SMS_API",
                    "recipient": clean_num,
                    "incident_id": incident_id,
                    "raw_response": res_json,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                }
        except Exception as e:
            return {
                "success": False,
                "status": "FAST2SMS_API_ERROR",
                "channel": "FAST2SMS_API",
                "error": f"Fast2SMS API request failed: {str(e)}",
                "incident_id": incident_id
            }


# Global dispatchers singleton
real_email_dispatcher = RealEmailDispatcher()
real_sms_dispatcher = RealSmsDispatcher()
