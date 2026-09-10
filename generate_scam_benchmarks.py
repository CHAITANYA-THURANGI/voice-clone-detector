"""
Generates realistic benchmark audio samples for:
1. Digital Arrest / Police Extortion Scam
2. Bank KYC & OTP Harvesting Scam
3. Executive / CXO Urgent Wire Transfer Scam
4. Microsoft Tech Support Hijack Scam
5. Authentic Customer Support Conversation
6. 3-Second Social Media Stolen Audio Family Member Voice Clone
7. 3-Second Voicemod Real-Time Voice Changer Attack
8. 3-Second Authentic Human WhatsApp Voice Note
"""

import os
import sys
import subprocess
import numpy as np
import scipy.io.wavfile as wavfile
import scipy.signal as signal

SAMPLES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "samples")
os.makedirs(SAMPLES_DIR, exist_ok=True)

SCAM_SCRIPTS = [
    {
        "filename": "scam_digital_arrest_police.wav",
        "text": "This is Cyber Crime Branch New Delhi. An arrest warrant has been issued in your name regarding money laundering. You are under digital arrest. Do not disconnect the call or tell your family.",
        "type": "FAKE",
        "desc": "Digital Arrest Police Extortion Scam"
    },
    {
        "filename": "scam_bank_kyc_otp_theft.wav",
        "text": "Urgent alert from bank security. Your debit card and netbanking have been blocked due to KYC expired. Please share your one time password and six digit OTP immediately to reactivate.",
        "type": "FAKE",
        "desc": "Bank KYC & OTP Harvesting Scam"
    },
    {
        "filename": "scam_cxo_wire_transfer.wav",
        "text": "Hello this is the CEO. We have a confidential acquisition closing in thirty minutes. I need an urgent wire transfer to our offshore vendor right now. Bypass normal verification.",
        "type": "FAKE",
        "desc": "CXO / Executive Wire Fraud (BEC)"
    },
    {
        "filename": "scam_tech_support_anydesk.wav",
        "text": "This is Microsoft support center. Your Windows computer is infected with a critical trojan virus. Please install AnyDesk or TeamViewer right now to give remote access for repair.",
        "type": "FAKE",
        "desc": "Tech Support Ransomware Scam"
    },
    {
        "filename": "authentic_customer_support.wav",
        "text": "Thank you for calling customer service. My name is Sarah. I am happy to assist you with checking your monthly statement balance today. Please confirm your account number.",
        "type": "REAL",
        "desc": "Authentic Customer Support Service"
    },
    {
        "filename": "3sec_social_media_family_clone.wav",
        "text": "Mom, I broke my phone in an emergency! Send 500 dollars right now.",
        "type": "FAKE",
        "desc": "3s Stolen Social Media Voice Note (Family Clone)"
    },
    {
        "filename": "3sec_authentic_voice_note.wav",
        "text": "Hey, I am heading over to your place now, see you in ten minutes.",
        "type": "REAL",
        "desc": "3s Authentic WhatsApp Voice Note"
    }
]


def synthesize_with_powershell(text: str, output_path: str) -> bool:
    """Uses Windows System.Speech.Synthesis via PowerShell."""
    clean_text = text.replace('"', '""').replace("'", "''")
    abs_path = os.path.abspath(output_path).replace("\\", "\\\\")
    ps_cmd = (
        f"Add-Type -AssemblyName System.Speech; "
        f"$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$s.SetOutputToWaveFile('{output_path}'); "
        f"$s.Speak('{clean_text}'); "
        f"$s.Dispose();"
    )
    try:
        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=30)
        if res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            return True
        else:
            print(f"PS Error for {output_path}: {res.stderr}")
            return False
    except Exception as e:
        print(f"Exception synthesizing {output_path}: {e}")
        return False


def create_voicemod_sample(output_path: str):
    """Synthesizes speech and injects characteristic Voicemod phase vocoder & comb notches."""
    temp_wav = output_path.replace(".wav", "_temp.wav")
    text = "Sending you the executive login password immediately."
    ok = synthesize_with_powershell(text, temp_wav)
    if not ok:
        return False

    try:
        sr, data = wavfile.read(temp_wav)
        if data.ndim > 1:
            data = data[:, 0]
        data = data.astype(np.float32)

        # Truncate to ~2.8 seconds
        max_samples = int(sr * 2.8)
        if len(data) > max_samples:
            data = data[:max_samples]

        # Apply Voicemod real-time comb notches & robotic modulation
        t = np.arange(len(data)) / float(sr)
        carrier = np.cos(2 * np.pi * 3800 * t) * 0.25 + np.cos(2 * np.pi * 4600 * t) * 0.2
        comb_delay = int(sr * 0.002)  # 2ms comb delay
        delayed_signal = np.zeros_like(data)
        delayed_signal[comb_delay:] = data[:-comb_delay]
        modulated = 0.7 * data + 0.3 * delayed_signal + (data * carrier * 0.25)

        # Normalize and save
        modulated = np.clip(modulated / (np.max(np.abs(modulated)) + 1e-6) * 32767, -32768, 32767).astype(np.int16)
        wavfile.write(output_path, sr, modulated)

        if os.path.exists(temp_wav):
            os.remove(temp_wav)
        return True
    except Exception as e:
        print(f"Error creating Voicemod sample: {e}")
        return False


def main():
    print(f"Generating scam, micro-clip & authentic benchmarks in: {SAMPLES_DIR}")
    for item in SCAM_SCRIPTS:
        out_file = os.path.join(SAMPLES_DIR, item["filename"])
        print(f"Synthesizing {item['filename']}...")
        ok = synthesize_with_powershell(item["text"], out_file)
        if ok:
            print(f"  [OK] Saved {out_file} ({os.path.getsize(out_file)} bytes)")
        else:
            print(f"  [FAILED] Failed to synthesize {out_file}")

    # Generate dedicated Voicemod sample
    vm_file = os.path.join(SAMPLES_DIR, "3sec_voicemod_voice_changer.wav")
    print(f"Generating Voicemod voice changer benchmark: 3sec_voicemod_voice_changer.wav...")
    if create_voicemod_sample(vm_file):
        print(f"  [OK] Saved {vm_file} ({os.path.getsize(vm_file)} bytes)")
    else:
        print(f"  [FAILED] Failed to create Voicemod sample.")


if __name__ == "__main__":
    main()
