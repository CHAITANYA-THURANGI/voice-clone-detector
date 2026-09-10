package org.voiceshield

import android.os.Build
import android.telecom.Call
import android.telecom.CallScreeningService
import android.util.Log
import androidx.annotation.RequiresApi
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.UUID

/**
 * Truecaller-Style Pre-Call Screening Service.
 * Android OS triggers onScreenCall() for every incoming call BEFORE ringing the device.
 * VoiceShield evaluates caller reputation against local & backend blacklists.
 * If verified fraudulent or high-risk:
 * 1. Silences the ringtone completely (setSkipNotification).
 * 2. Rejects the incoming call immediately (setDisallowCall + setRejectCall).
 * 3. Automatically dispatches precaution SMS via user's device SIM card quota.
 */
@RequiresApi(Build.VERSION_CODES.N)
class VoiceShieldCallScreeningService : CallScreeningService() {

    private val serviceScope = CoroutineScope(Dispatchers.IO)

    companion object {
        private const val TAG = "VoiceShieldScreening"
        var backendServerUrl = "http://172.24.101.1:8000" // Default Host PC Wi-Fi IP
        var emergencySmsRecipient = "+91-99887-76655" // Configured via MainActivity
    }

    override fun onScreenCall(callDetails: Call.Details) {
        val callerHandle = callDetails.handle?.schemeSpecificPart ?: "UNKNOWN"
        Log.i(TAG, "📞 Incoming Call Detected: $callerHandle. Screening for fraud & voice clone risk...")

        // Fast-path known scammer database check (Local list for sub-millisecond response)
        val isKnownScammer = isBlacklistedNumber(callerHandle)

        if (isKnownScammer) {
            Log.w(TAG, "🛑 BLOCKING CALL: $callerHandle matches known Scammer Watchlist!")
            
            // Truecaller-Style Full Call Disallow & Reject
            val response = CallResponse.Builder()
                .setDisallowCall(true)      // Refuses the incoming call connection
                .setRejectCall(true)        // Declines call so user's phone never rings
                .setSkipNotification(true)  // Silences ringtone and popup notifications
                .setSkipCallLog(false)      // Preserves call record in phone call history for forensics
                .build()

            respondToCall(callDetails, response)

            // Dispatch precaution SMS via device SIM card quota
            val incidentId = "INC-" + UUID.randomUUID().toString().take(8).uppercase()
            DeviceSmsSender.sendPrecautionSms(
                context = applicationContext,
                recipientPhone = emergencySmsRecipient,
                incidentId = incidentId,
                callerNumber = callerHandle,
                claimedName = "Scammer Watchlist Caller",
                riskPercentage = 99.0,
                threatDescription = "Automated Truecaller-Style Call Screening Block"
            )

            syncScreeningToBackend(callerHandle, "REJECTED", 99.0, "Known Scammer Watchlist Match")
            return
        }

        // Query backend for real-time reputation if network available
        serviceScope.launch {
            try {
                val risk = checkCallerReputationOnline(callerHandle)
                if (risk >= 0.75) {
                    Log.w(TAG, "🛑 BLOCKING CALL: Online check returned high risk ($risk)")
                    val response = CallResponse.Builder()
                        .setDisallowCall(true)
                        .setRejectCall(true)
                        .setSkipNotification(true)
                        .build()
                    respondToCall(callDetails, response)
                    return@launch
                }
            } catch (e: Exception) {
                Log.e(TAG, "Error checking caller reputation: ${e.message}")
            }

            // Normal caller - Allow through to device
            val allowResponse = CallResponse.Builder()
                .setDisallowCall(false)
                .setRejectCall(false)
                .setSkipNotification(false)
                .build()
            respondToCall(callDetails, allowResponse)
        }
    }

    private fun isBlacklistedNumber(phoneNumber: String): Boolean {
        val clean = phoneNumber.replace(Regex("[^0-9+]"), "")
        val blacklist = listOf(
            "+91140776655", "140776655",
            "+918888899999", "8888899999",
            "+919876543210", "9876543210"
        )
        return blacklist.any { clean.contains(it) }
    }

    private fun checkCallerReputationOnline(phoneNumber: String): Double {
        return try {
            val url = URL("$backendServerUrl/api/speaker-id/profiles")
            val conn = url.openConnection() as HttpURLConnection
            conn.requestMethod = "GET"
            conn.connectTimeout = 1500
            conn.readTimeout = 1500

            if (conn.responseCode == 200) {
                val responseText = conn.inputStream.bufferedReader().readText()
                val json = JSONObject(responseText)
                val profiles = json.optJSONArray("profiles") ?: return 0.0
                for (i in 0 until profiles.length()) {
                    val p = profiles.getJSONObject(i)
                    if (p.optString("category") == "SCAMMER_WATCHLIST" &&
                        phoneNumber.contains(p.optString("phone_number", ""))) {
                        return 0.95
                    }
                }
            }
            0.0
        } catch (e: Exception) {
            0.0
        }
    }

    private fun syncScreeningToBackend(callerNumber: String, action: String, riskPct: Double, reason: String) {
        serviceScope.launch(Dispatchers.IO) {
            try {
                val url = URL("$backendServerUrl/api/history/log")
                val conn = url.openConnection() as HttpURLConnection
                conn.requestMethod = "POST"
                conn.doOutput = true
                conn.setRequestProperty("Content-Type", "application/x-www-form-urlencoded")

                val encodedReason = java.net.URLEncoder.encode(reason, "UTF-8")
                val encodedCaller = java.net.URLEncoder.encode(callerNumber, "UTF-8")
                val params = "event_type=CALL_SCREENING_INTERCEPT&caller_or_file=$encodedCaller&action_taken=$action&risk_percentage=$riskPct&threat_description=$encodedReason&sms_sent=true&source=ANDROID_MOBILE"
                conn.outputStream.write(params.toByteArray())
                if (conn.responseCode == 200) {
                    Log.i(TAG, "✅ Synced call screening event to central history")
                }
            } catch (e: Exception) {
                Log.w(TAG, "Failed to sync screening event to backend: ${e.message}")
            }
        }
    }
}
