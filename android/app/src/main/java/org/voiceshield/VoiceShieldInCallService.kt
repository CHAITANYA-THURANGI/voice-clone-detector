package org.voiceshield

import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Build
import android.telecom.Call
import android.telecom.InCallService
import android.util.Log
import androidx.annotation.RequiresApi
import kotlinx.coroutines.*
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.DataOutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.UUID

/**
 * Mid-Call AI Defense InCallService.
 * Intercepts ongoing calls, samples sliding audio frames, streams to VoiceShield AI backend,
 * and executes call.disconnect() immediately when high-risk voice cloning or social engineering is detected.
 * Also dispatches emergency precaution SMS via device SIM.
 */
@RequiresApi(Build.VERSION_CODES.M)
class VoiceShieldInCallService : InCallService() {

    private val serviceScope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private var activeCall: Call? = null
    private var activeSessionId: String? = null
    private var isAnalyzing = false
    private var audioRecord: AudioRecord? = null

    companion object {
        private const val TAG = "VoiceShieldInCall"
        private const val SAMPLE_RATE = 16000
        private const val CHUNK_DURATION_SEC = 2
        private const val BUFFER_SIZE = SAMPLE_RATE * CHUNK_DURATION_SEC * 2 // 16-bit PCM
        var backendUrl = "http://172.24.101.1:8000"
        var emergencyPhone = "+91-99887-76655"
    }

    override fun onCallAdded(call: Call) {
        super.onCallAdded(call)
        activeCall = call
        val callerNumber = call.details.handle?.schemeSpecificPart ?: "Unknown Number"
        val callerName = call.details.callerDisplayName ?: "Unknown Caller"

        Log.i(TAG, "🟢 Call Started: $callerNumber ($callerName). Registering AI defense session...")

        serviceScope.launch {
            initBackendSession(callerNumber, callerName)
            startSlidingAudioCapture()
        }
    }

    override fun onCallRemoved(call: Call) {
        super.onCallRemoved(call)
        Log.i(TAG, "🔴 Call Ended. Releasing audio buffers and closing session.")
        stopSlidingAudioCapture()
        activeCall = null
        activeSessionId = null
    }

    private suspend fun initBackendSession(callerNumber: String, callerName: String) {
        withContext(Dispatchers.IO) {
            try {
                val url = URL("$backendUrl/api/phone-call/start")
                val conn = url.openConnection() as HttpURLConnection
                conn.requestMethod = "POST"
                conn.doOutput = true
                conn.setRequestProperty("Content-Type", "application/x-www-form-urlencoded")

                val params = "caller_number=$callerNumber&caller_claimed_name=$callerName&user_id=mobile_user_01"
                conn.outputStream.write(params.toByteArray())

                if (conn.responseCode == 200) {
                    val resp = conn.inputStream.bufferedReader().readText()
                    val json = JSONObject(resp)
                    activeSessionId = json.optString("session_id")
                    Log.i(TAG, "✅ Active defense session registered: $activeSessionId")
                } else {
                    Log.w(TAG, "Backend returned HTTP ${conn.responseCode}")
                }
            } catch (e: Exception) {
                Log.e(TAG, "Failed to initialize defense session: ${e.message}")
            }
            Unit
        }
    }

    private fun startSlidingAudioCapture() {
        if (isAnalyzing) return
        isAnalyzing = true

        serviceScope.launch(Dispatchers.IO) {
            try {
                val minBuf = AudioRecord.getMinBufferSize(
                    SAMPLE_RATE,
                    AudioFormat.CHANNEL_IN_MONO,
                    AudioFormat.ENCODING_PCM_16BIT
                )
                audioRecord = AudioRecord(
                    MediaRecorder.AudioSource.VOICE_COMMUNICATION,
                    SAMPLE_RATE,
                    AudioFormat.CHANNEL_IN_MONO,
                    AudioFormat.ENCODING_PCM_16BIT,
                    maxOf(minBuf, BUFFER_SIZE)
                )

                audioRecord?.startRecording()
                val audioBuffer = ShortArray(SAMPLE_RATE * CHUNK_DURATION_SEC)

                while (isAnalyzing && activeCall != null) {
                    val readSamples = audioRecord?.read(audioBuffer, 0, audioBuffer.size) ?: 0
                    if (readSamples > 0) {
                        val wavBytes = convertShortsToWav(audioBuffer, readSamples, SAMPLE_RATE)
                        processAudioChunkOnBackend(wavBytes)
                    }
                    delay(1500) // 1.5s sliding window overlap
                }
            } catch (e: Exception) {
                Log.e(TAG, "Audio capture error: ${e.message}")
            }
        }
    }

    private suspend fun processAudioChunkOnBackend(wavBytes: ByteArray) {
        withContext(Dispatchers.IO) {
            val sessionId = activeSessionId ?: return@withContext
            try {
                val url = URL("$backendUrl/api/phone-call/stream-chunk")
                val boundary = "==VoiceShieldBoundary${UUID.randomUUID()}=="
                val conn = url.openConnection() as HttpURLConnection
                conn.requestMethod = "POST"
                conn.doOutput = true
                conn.setRequestProperty("Content-Type", "multipart/form-data; boundary=$boundary")

                val out = DataOutputStream(conn.outputStream)
                // Form field: session_id
                out.writeBytes("--$boundary\r\n")
                out.writeBytes("Content-Disposition: form-data; name=\"session_id\"\r\n\r\n")
                out.writeBytes("$sessionId\r\n")

                // File field: audio_chunk
                out.writeBytes("--$boundary\r\n")
                out.writeBytes("Content-Disposition: form-data; name=\"audio_chunk\"; filename=\"chunk.wav\"\r\n")
                out.writeBytes("Content-Type: audio/wav\r\n\r\n")
                out.write(wavBytes)
                out.writeBytes("\r\n--$boundary--\r\n")
                out.flush()

                if (conn.responseCode == 200) {
                    val resp = conn.inputStream.bufferedReader().readText()
                    val json = JSONObject(resp)

                    val riskPct = json.optDouble("effective_risk_percentage", 0.0)
                    val autoDrop = json.optBoolean("auto_drop_executed", false)

                    Log.i(TAG, "Telemetry: Risk=$riskPct%, AutoDrop=$autoDrop")

                    if (autoDrop) {
                        executeEmergencyCallDrop(riskPct, json.optString("termination_reason"))
                    }
                } else {
                    Log.w(TAG, "Backend stream returned HTTP ${conn.responseCode}")
                }
            } catch (e: Exception) {
                Log.e(TAG, "Backend chunk streaming error: ${e.message}")
            }
            Unit
        }
    }

    private fun executeEmergencyCallDrop(riskPercentage: Double, reason: String) {
        Log.w(TAG, "🛑 EMERGENCY THREAT DETECTED ($riskPercentage%). Disconnecting phone call immediately!")
        
        // 1. Android Telecom Disconnect
        activeCall?.disconnect()

        // 2. Real Native SIM SMS Dispatch
        val incidentId = "INC-" + UUID.randomUUID().toString().take(8).uppercase()
        val callerNumber = activeCall?.details?.handle?.schemeSpecificPart ?: "Suspicious Caller"
        val callerName = activeCall?.details?.callerDisplayName ?: "Unknown Caller"

        DeviceSmsSender.sendPrecautionSms(
            context = applicationContext,
            recipientPhone = emergencyPhone,
            incidentId = incidentId,
            callerNumber = callerNumber,
            claimedName = callerName,
            riskPercentage = riskPercentage,
            threatDescription = "Mid-Call Voice Clone / Coercive Fraud ($reason)"
        )

        // 3. Sync to Centralized Deep Audit History
        serviceScope.launch(Dispatchers.IO) {
            try {
                val url = URL("$backendUrl/api/history/log")
                val conn = url.openConnection() as HttpURLConnection
                conn.requestMethod = "POST"
                conn.doOutput = true
                conn.setRequestProperty("Content-Type", "application/x-www-form-urlencoded")

                val encodedReason = java.net.URLEncoder.encode("Mid-Call Voice Clone / Coercive Fraud ($reason)", "UTF-8")
                val encodedCaller = java.net.URLEncoder.encode(callerNumber, "UTF-8")
                val encodedName = java.net.URLEncoder.encode(callerName, "UTF-8")
                val params = "event_type=PHONE_CALL_DEFENSE&caller_or_file=$encodedCaller&claimed_identity=$encodedName&action_taken=AUTO_CALL_DROP_AND_PRECAUTION_DISPATCH&risk_percentage=$riskPercentage&threat_description=$encodedReason&sms_sent=true&source=ANDROID_MOBILE"
                conn.outputStream.write(params.toByteArray())
                if (conn.responseCode == 200) {
                    Log.i(TAG, "✅ Synced emergency call drop to central history")
                }
            } catch (e: Exception) {
                Log.w(TAG, "Failed to sync call drop to backend: ${e.message}")
            }
        }
    }

    private fun stopSlidingAudioCapture() {
        isAnalyzing = false
        try {
            audioRecord?.stop()
            audioRecord?.release()
            audioRecord = null
        } catch (e: Exception) {
            Log.e(TAG, "Error stopping audio recorder: ${e.message}")
        }
    }

    private fun convertShortsToWav(shorts: ShortArray, readSamples: Int, sampleRate: Int): ByteArray {
        val pcmBytes = ByteArray(readSamples * 2)
        ByteBuffer.wrap(pcmBytes).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer().put(shorts, 0, readSamples)

        val totalDataLen = pcmBytes.size + 36
        val totalAudioLen = pcmBytes.size
        val byteRate = sampleRate * 2 // 16-bit mono

        val header = ByteArray(44)
        header[0] = 'R'.code.toByte(); header[1] = 'I'.code.toByte(); header[2] = 'F'.code.toByte(); header[3] = 'F'.code.toByte()
        header[4] = (totalDataLen and 0xff).toByte()
        header[5] = ((totalDataLen shr 8) and 0xff).toByte()
        header[6] = ((totalDataLen shr 16) and 0xff).toByte()
        header[7] = ((totalDataLen shr 24) and 0xff).toByte()
        header[8] = 'W'.code.toByte(); header[9] = 'A'.code.toByte(); header[10] = 'V'.code.toByte(); header[11] = 'E'.code.toByte()
        header[12] = 'f'.code.toByte(); header[13] = 'm'.code.toByte(); header[14] = 't'.code.toByte(); header[15] = ' '.code.toByte()
        header[16] = 16; header[17] = 0; header[18] = 0; header[19] = 0 // subchunk 1 size
        header[20] = 1; header[21] = 0 // PCM
        header[22] = 1; header[23] = 0 // Mono
        header[24] = (sampleRate and 0xff).toByte()
        header[25] = ((sampleRate shr 8) and 0xff).toByte()
        header[26] = ((sampleRate shr 16) and 0xff).toByte()
        header[27] = ((sampleRate shr 24) and 0xff).toByte()
        header[28] = (byteRate and 0xff).toByte()
        header[29] = ((byteRate shr 8) and 0xff).toByte()
        header[30] = ((byteRate shr 16) and 0xff).toByte()
        header[31] = ((byteRate shr 24) and 0xff).toByte()
        header[32] = 2; header[33] = 0 // block align
        header[34] = 16; header[35] = 0 // bits per sample
        header[36] = 'd'.code.toByte(); header[37] = 'a'.code.toByte(); header[38] = 't'.code.toByte(); header[39] = 'a'.code.toByte()
        header[40] = (totalAudioLen and 0xff).toByte()
        header[41] = ((totalAudioLen shr 8) and 0xff).toByte()
        header[42] = ((totalAudioLen shr 16) and 0xff).toByte()
        header[43] = ((totalAudioLen shr 24) and 0xff).toByte()

        val output = ByteArrayOutputStream()
        output.write(header)
        output.write(pcmBytes)
        return output.toByteArray()
    }
}
