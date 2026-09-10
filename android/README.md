# VoiceShield AI: Android Telephony & Truecaller-Style Call Blocker

This directory contains the complete, production-grade **Android Native Telephony Defense App** for VoiceShield AI.
It combines Truecaller-style pre-call screening, mid-call acoustic deepfake defense, and carrier-plan SIM SMS alert dispatching.

---

## 1. Project Directory Structure

```text
android/
├── build.gradle.kts                          # Top-level Gradle plugins
├── settings.gradle.kts                       # Repository management & project definition
├── gradlew.bat                               # Windows Gradle wrapper script
├── gradlew                                   # Unix/macOS Gradle wrapper script
├── build_apk.bat                             # 1-Click Windows APK build script
├── local.properties.example                  # SDK directory configuration template
├── gradle/wrapper/
│   └── gradle-wrapper.properties             # Gradle 8.5 distribution specification
├── app/
│   ├── build.gradle.kts                      # Target SDK 34, AndroidX, Coroutines
│   └── src/main/
│       ├── AndroidManifest.xml               # Telephony, SMS, and Screening permissions
│       ├── java/org/voiceshield/
│       │   ├── MainActivity.kt               # Permission onboarding & live SIM SMS testing UI
│       │   ├── VoiceShieldCallScreeningService.kt  # Truecaller pre-call blocker
│       │   ├── VoiceShieldInCallService.kt   # Mid-call deepfake audio streaming & auto-hangup
│       │   └── DeviceSmsSender.kt            # Native SmsManager carrier SIM dispatcher
│       └── res/
│           ├── values/
│           │   ├── strings.xml               # App titles & labels
│           │   ├── colors.xml                # Cyber-defense UI color palette
│           │   └── themes.xml                # Material theme styles
│           ├── drawable/
│           │   ├── ic_launcher_background.xml# Shield background vector
│           │   └── ic_launcher_foreground.xml# Cyber defense shield vector
│           └── mipmap-anydpi-v26/
│               ├── ic_launcher.xml           # Adaptive app icon
│               └── ic_launcher_round.xml     # Round adaptive app icon
└── README.md                                 # Full deployment guide
```

---

## 2. Core Architecture

```text
                                INCOMING PHONE CALL
                                         │
                                         ▼
                 [TRUECALLER-STYLE CALL SCREENING SERVICE]
                    (VoiceShieldCallScreeningService.kt)
                                         │
                   ┌─────────────────────┴─────────────────────┐
                   ▼                                           ▼
       KNOWN SCAMMER / SPOOF                       UNKNOWN / REGULAR CALL
       • setDisallowCall(true)                     • Allowed through
       • setRejectCall(true)                       • User answers phone
       • setSkipNotification(true)                             │
       • Silences ringtone before user sees it                 ▼
       • Auto-sends SIM SMS to family contact      [IN-CALL REAL-TIME DEFENSE]
                                                    (VoiceShieldInCallService.kt)
                                                               │
                                                               ▼
                                                   Sliding 16kHz PCM Buffer
                                                   Streams to VoiceShield AI Server
                                                               │
                                                               ▼
                                                   Deepfake / Extortion Detected?
                                                    ├── YES: call.disconnect() (Hangup)
                                                    │        Device SIM SMS Sent!
                                                    └── NO:  Call Continues Safely
```

---

## 3. Key Components

### A. Pre-Call Truecaller Screening (`VoiceShieldCallScreeningService.kt`)
* Implements Android's `CallScreeningService` (`android.telecom.CallScreeningService`).
* Android OS invokes `onScreenCall(callDetails)` **before ringing the handset**.
* Evaluates caller ID against:
  1. Local instant sub-millisecond blacklist.
  2. VoiceShield API caller reputation directory.
* If fraudulent, responds with:
  ```kotlin
  val response = CallResponse.Builder()
      .setDisallowCall(true)      // Refuses incoming call
      .setRejectCall(true)        // Declines automatically
      .setSkipNotification(true)  // Silences ringtone completely
      .setSkipCallLog(false)      // Preserves call record for forensics
      .build()
  respondToCall(callDetails, response)
  ```

### B. Device Carrier Plan SIM SMS (`DeviceSmsSender.kt`)
* Uses Android's native `SmsManager`:
  ```kotlin
  smsManager.sendMultipartTextMessage(recipient, null, parts, null, null)
  ```
* **Zero Extra Cost**: Uses the user's mobile SIM card SMS quota (e.g. 100 free SMS/day on Indian carriers or unlimited carrier text plans) directly from the device.
* Requires `android.permission.SEND_SMS`.

### C. Mid-Call Deepfake Audio Interceptor (`VoiceShieldInCallService.kt`)
* Implements `InCallService` to tap call audio in sliding 2-second windows.
* Streams to `POST /api/phone-call/stream-chunk`.
* When backend returns `auto_drop_executed: true` ($\text{Risk} \ge 75\%$), immediately triggers:
  ```kotlin
  activeCall?.disconnect()
  ```
* Immediately fires precaution SMS to secondary family emergency contacts.

---

## 4. How to Build & Install on Your Android Smartphone

### Method 1: Using Android Studio (Recommended / Turnkey)
1. Open **Android Studio**.
2. Click **Open an Existing Project** and select:
   ```text
   c:\SIH_2026\Voice Clone Detector\android
   ```
3. Android Studio will automatically download the required Android SDK components (SDK 34) and sync dependencies.
4. Connect your Android smartphone via USB cable:
   - Ensure **Developer Options** > **USB Debugging** is toggled **ON** on your phone.
5. In the top toolbar, select your connected device and click the green **▶ Run 'app'** button (or press `Shift + F10`).
6. Alternatively, to build an APK file to share:
   - Click **Build** > **Build Bundle(s) / APK(s)** > **Build APK(s)**.
   - The compiled file will be located at:
     ```text
     android/app/build/outputs/apk/debug/app-debug.apk
     ```

### Method 2: Command Line (Windows)
Run the included build script:
```cmd
cd android
build_apk.bat
```

---

## 5. Setting Up on Your Physical Phone

1. **Grant Permissions**:
   - On first launch, tap **Allow** for:
     - **Phone Calls**: `ANSWER_PHONE_CALLS`, `READ_PHONE_STATE`
     - **SMS**: `SEND_SMS` (allows VoiceShield to dispatch real alerts using your SIM card plan)
     - **Microphone**: `RECORD_AUDIO` (for in-call real-time deepfake audio analysis)
2. **Enable Default Call Screening (Truecaller Mode)**:
   - Tap the green button: **"📞 Set Default Call Screening App"**.
   - In the Android system dialog, choose **VoiceShield AI** and tap **Set as default**.
3. **Connect to VoiceShield Backend**:
   - In **Backend Server URL**, enter your computer's local Wi-Fi IP address (e.g., `http://192.168.1.15:8000`).
   - Enter your emergency contact's phone number.
   - Tap **💾 Save Telephony Settings**.
4. **Test Real SIM SMS**:
   - Tap **"✉️ Test Real SIM SMS from Device"** — VoiceShield will immediately dispatch a real text message from your phone's SIM card to confirm your carrier plan quota is active!
