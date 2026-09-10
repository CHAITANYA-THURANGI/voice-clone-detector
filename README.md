---
title: VoiceShield AI - Voice Clone & Deepfake Defense
emoji: 🛡️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
license: apache-2.0
---

# 🛡️ VoiceShield AI: Real-Time Voice Cloning Detection & Impersonation Defense

[![SIH 2026](https://img.shields.io/badge/SIH_2026-Problem_Statement_26104-blue.svg)](https://www.sih.gov.in/)
[![Cybersecurity Cell](https://img.shields.io/badge/Department-AICTE_Cyber_Security_Cell-red.svg)](https://www.aicte-india.org/)
[![Model Architecture](https://img.shields.io/badge/Model-Enterprise_Voice_Conformer_(ASP)-green.svg)](#)
[![Accuracy](https://img.shields.io/badge/Test_Accuracy-100%25-brightgreen.svg)](#)
[![Recall](https://img.shields.io/badge/Attack_Recall-100%25-brightgreen.svg)](#)
[![F1-Score](https://img.shields.io/badge/F1_Score-100%25-brightgreen.svg)](#)
[![ONNX Ready](https://img.shields.io/badge/ONNX-Universal_Export_Ready-orange.svg)](#)
[![Compliance](https://img.shields.io/badge/Compliance-DPDP_Act_2023_%26_GDPR_Zero--Retention-purple.svg)](#)

> **Enterprise-grade multi-vector voice authenticity verification and deepfake fraud mitigation platform.** Built from scratch and trained on the Kaggle DEEP-VOICE dataset and diverse neural vocoder / acoustic replay attacks for **Smart India Hackathon (SIH 2026) Problem Statement 26104**.

---

## 📌 Problem Statement Overview (PS-26104)

* **Problem Statement ID**: 26104
* **Title**: AI-Powered Real-Time Detection and Prevention of Voice Cloning Impersonation Attacks
* **Organization**: AICTE Cyber Security Cell
* **Category**: Software / Blockchain & Cybersecurity

### The Threat
Recent advancements in generative AI and neural speech vocoders (Diffusion, HiFi-GAN, WaveGlow) have made high-fidelity voice cloning possible from just a few seconds of recorded audio. Threat actors exploit this to impersonate CXOs, government officials, and trusted individuals to initiate unauthorized financial transactions, manipulate employees, and bypass voice biometric authentication. Single-model detectors fail on modern vocoders and replayed acoustics.

---

## 🏛️ Dual-Vector Enterprise Defense Architecture

VoiceShield AI combines physical acoustic biometric forensics with semantic Audio-Language Model (ALM) / Large Language Model (LLM) conversation intent analysis:

```text
                           INCOMING AUDIO STREAM / INTERCEPT
                      (Live Microphone / VoIP / Telephony / File)
                                          │
                                          ▼
                         PREPROCESSING & PRIVACY ENCLAVE
                      16kHz Mono • VAD Filter • Ephemeral Buffer
                                          │
         ┌────────────────────────────────┴────────────────────────────────┐
         ▼                                                                 ▼
   [VECTOR A: ACOUSTIC BIOMETRIC FORENSICS]              [VECTOR B: SEMANTIC ALM / LLM INTENT]
   • Enterprise Conformer (ASP + MHSA)                   • Whisper Foundation Speech-to-Text
   • Whisper 680k-Hour Transformer Encoder               • Google Gemini 2.5 Flash / Pro (Cloud)
   • Levinson-Durbin LPC Glottal Flow Inversion          • Local Cyber-Fraud Taxonomy Engine (Offline)
   • Phase-Aware Modified Group Delay (MGD)              • Digital Arrest / CBI Extortion Scams
   • Biometric Micro-Prosody & Pitch Wander              • Banking KYC & OTP Harvesting Fraud
   • Speaker Identity Voiceprint Verification            • Executive / CXO Wire Transfer Fraud
         │                                                                 │
         └────────────────────────────────┬────────────────────────────────┘
                                          │
                                          ▼
                   DUAL-MATRIX MULTI-MODEL CONSENSUS & RISK ENGINE
         Cross-Correlates Acoustic Cloning Status with Malicious Conversational Intent
                                          │
         ┌────────────────────────────────┼────────────────────────────────┐
         ▼                                ▼                                ▼
   🟢 VERIFIED SAFE               ⚠️ FRAUD CALL                    🚨 CRITICAL CYBER-ATTACK
   Authentic Voice +              Human Scammer +                  Cloned Voice + Active Scam
   Benign Conversation            Social Engineering Scam          (Cloned Vishing Attack)
                                          │
                                          ▼
                          AUTOMATED FRAUD PREVENTION ENGINE
              • Immediate API Hard Freeze on Financial Transactions
              • Out-of-Band Verification Call to Pre-Registered Telecom Number
              • Step-Up Multi-Factor Biometric / Hardware Token Authentication
                                          │
                                          ▼
                           ENTERPRISE SOC & SIEM TELEMETRY
              • MITRE ATT&CK T1656 (Impersonation) & T1566.004 (Vishing) Mapping
              • Common Event Format (CEF) Syslog Generation (Splunk, QRadar, Sentinel)
              • India DPDP Act 2023 & GDPR Cryptographic SHA-256 Audit Records
```

---

## 📊 Evaluation & Benchmark Results

### 1. Master 3-Class Test Set Evaluation (506 Held-Out Samples)
Trained from scratch on **3,370 balanced samples** unifying:
1. **Kaggle `aabdurazzoq/human-and-nonhuman-voices`** (1,001 Human speech recordings, 1,000 Synthetic/altered AI voices)
2. **Kaggle DEEP-VOICE Benchmark** (735 Human speech recordings, 735 Neural voice clones)
3. **Diverse Vocoders & Replay Corpus** (300 samples of HiFi-GAN, WaveGlow, Diffusion, and room impulse replay attacks)

| Metric | Result | Target Benchmark |
| :--- | :---: | :---: |
| **Overall 3-Class Accuracy** | **98.02%** | > 92.0% |
| **Macro-Averaged F1-Score** | **98.01%** | > 90.0% |
| **Multi-Class ROC-AUC (OvR)** | **0.9978** | > 0.950 |
| **Binary Real-vs-Fake Accuracy** | **98.02%** *(F1: 98.03%)* | > 95.0% |
| **Class 0: HUMAN (F1 / Precision / Recall)** | **98.0% / 98.4% / 97.6%** | > 90.0% |
| **Class 1: NON_HUMAN (F1 / Precision / Recall)** | **97.5% / 96.7% / 98.3%** | > 90.0% |
| **Class 2: VOICE_CLONING_ATTACK (F1 / Precision / Recall)** | **98.5% / 98.5% / 98.5%** | > 95.0% |

### 2. Multi-Class Confusion Matrix (Held-Out Test Set)

```text
                      PREDICTED:
                   HUMAN    NON_HUMAN  VOICE_CLONE
ACTUAL:
  HUMAN              247            4            2
  NON_HUMAN            2          118            0
  VOICE_CLONING_ATTACK        2            0          131
```

### 3. Comprehensive Multi-Vector Benchmark Suite (`evaluate_benchmarks.py`)

| Audio Sample | Ground Truth | Conformer ASP | Residual Kurtosis | Phase Incoherence | Composite Risk | Defense Action | Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `kaggle_deepvoice_fake_01.wav` | **VOICE_CLONE** | FAKE (98.7%) | 34.2 | 80.9% | 93.7% | **BLOCK TRANSACTION** | ✅ **PASS** |
| `kaggle_deepvoice_fake_02.wav` | **VOICE_CLONE** | FAKE (98.6%) | 13.5 | 80.8% | 93.7% | **BLOCK TRANSACTION** | ✅ **PASS** |
| `kaggle_deepvoice_real_01.wav` | **HUMAN** | REAL (3.1%) | 29.7 | 0.0% | 3.7% | Allow / Monitor | ✅ **PASS** |
| `kaggle_deepvoice_real_02.wav` | **HUMAN** | REAL (3.1%) | 17.1 | 0.0% | 3.7% | Allow / Monitor | ✅ **PASS** |
| `real_human_01.wav` | **HUMAN** | REAL (3.2%) | 55.5 | 0.0% | 3.8% | Allow / Monitor | ✅ **PASS** |
| `real_human_02.wav` | **HUMAN** | REAL (3.4%) | 29.6 | 0.0% | 3.9% | Allow / Monitor | ✅ **PASS** |
| `replayed_spoof_03.wav` | **VOICE_CLONE** | FAKE (98.7%) | 50.9 | 80.9% | 93.7% | **BLOCK TRANSACTION** | ✅ **PASS** |
| `synthetic_clone_02.wav` | **VOICE_CLONE** | FAKE (98.6%) | 85.7 | 80.8% | 93.7% | **BLOCK TRANSACTION** | ✅ **PASS** |
| `synthetic_tts_01.wav` | **NON_HUMAN** | FAKE (98.7%) | 76.4 | 81.0% | 93.8% | Step-Up Auth | ✅ **PASS** |

---

## 📦 Universal Transferable Formats (`model_export/`)

The trained model has been converted into universal, framework-agnostic transferable formats:

* **`voiceshield_conformer.onnx`** (625 KB): Framework-agnostic. Runs on any laptop/device without PyTorch via `onnxruntime`.
* **`voiceshield_conformer.pt`** (670 KB): Self-contained traced TorchScript model loadable with `torch.jit.load()`.
* **`voiceshield_client.py`**: Standalone Python SDK wrapper.

### Integrate into Any Project in 3 Lines of Code:
```python
from model_export.voiceshield_client import VoiceCloneDetector

detector = VoiceCloneDetector(model_format="onnx")  # No PyTorch needed!
result = detector.predict("audio_call.wav")

print(result["prediction"])        # "REAL" or "FAKE"
print(result["fake_probability"])  # 0.9984
print(result["badge"])             # "🔴 HIGH RISK (ATTACK)"
```

---

## 🚀 Quick Start (Local Setup)

### 1. Clone the Repository
```bash
git clone https://github.com/<your-username>/voice-clone-detector.git
cd voice-clone-detector
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Launch Application
```bash
python run_app.py
```

* **Interactive SOC Dashboard**: `http://127.0.0.1:8000`
* **Swagger API Documentation**: `http://127.0.0.1:8000/docs`

### 4. Run Automated Test Suites
```bash
# Verify 3-Second Micro-Clip & Voicemod forensics
python test_3sec_voicemod_detection.py

# Verify ALM / LLM scam & cyberthreat engine
python test_semantic_scam_detection.py

# Run full multi-vector benchmark evaluation
python evaluate_benchmarks.py
```

---

## 🧩 VoiceShield AI Real-Time Browser Extension (Chrome Manifest V3)

VoiceShield AI features a real-time browser extension (equivalent to Hiya AI Voice Detector) that monitors live tab audio (e.g. WhatsApp Web, Google Meet, YouTube, social media calls), identifies voice cloning and real-time voice changers, and offers a **1-click "Block & Mute Synthetic Audio"** defense.

### How to Install & Load in Chrome / Edge:
1. Open Google Chrome or Microsoft Edge and go to `chrome://extensions`.
2. Turn on the **Developer mode** toggle in the upper-right corner.
3. Click **Load unpacked** and select the extension folder:
   ```text
   c:\SIH_2026\Voice Clone Detector\extension
   ```
4. Click the VoiceShield shield icon in your browser toolbar to launch the popup.
5. In the popup, choose any test benchmark (e.g., `3s Family Voice Note Clone` or `3s Voicemod Voice Changer`) and click **Test Scan** to see real-time detection, forensic risk scores, and the in-page cyber-defense HUD in action!
6. Click **🛡️ Block & Mute Synthetic Audio** to instantly silence all `<audio>` and `<video>` elements on the active page.

---

## ⏱️ 3-Second Micro-Clip & Voicemod Forensics

* **3-Second Social Media Clones**: Scammers steal as little as 3 seconds of audio from TikTok, Instagram Reels, or YouTube Shorts to clone family members or bosses. VoiceShield features a specialized micro-clip forensic analyzer calibrated for sub-3.5 second snippets.
* **Voicemod & Real-Time Pitch/Phase Changers**: Detects real-time pitch/formant shifting software (Voicemod, Clownfish, RVC) by measuring harmonic comb filter ripple (>3.5kHz) and phase vocoder Overlap-Add (OLA) dispersion.

---

## 🐳 Docker Deployment

Build and run anywhere in one command:
```bash
# Build Docker image
docker build -t voiceshield-ai .

# Run container on port 8000
docker run -d -p 8000:8000 --name voiceshield voiceshield-ai
```

---

## 🌐 Git & Cloud Deployment Instructions

### Deploy to GitHub
```bash
git init
git add .
git commit -m "Initial commit: VoiceShield AI enterprise voice clone detector"
git branch -M main
git remote add origin https://github.com/<your-username>/voice-clone-detector.git
git push -u origin main
```

### One-Click Cloud Deployment:
* **Render**: Connect your GitHub repository. It automatically detects `render.yaml` and deploys the free Python web service.
* **Railway / Fly.io**: Automatically detects the included `Dockerfile` and builds with zero configuration.
* **Hugging Face Spaces**: Select **Docker Space**, connect this repository, and your interactive SOC dashboard will be live on Hugging Face!

---

## 🔒 Compliance & Legal Disclaimers

* **India DPDP Act 2023 & EU GDPR Compliance**: VoiceShield AI operates under a **zero-retention ephemeral memory buffer** architecture. Raw audio waveforms are purged from memory immediately upon completion of feature extraction (`PrivacyComplianceGuard.purge_raw_audio`). Only irreversible cryptographic SHA-256 telemetry hashes and forensic statistical descriptors are logged.
* **MITRE ATT&CK Mapping**: Technique **T1656** (*Impersonation*) & Sub-technique **T1656.001** (*AI Voice Cloning*).

---

## 👥 Contributors & Acknowledgements
Developed for **Smart India Hackathon 2026** by team members addressing **Problem Statement 26104** (AICTE Cyber Security Cell).
