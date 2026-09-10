package org.voiceshield

import android.Manifest
import android.app.role.RoleManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

class MainActivity : AppCompatActivity() {

    private val PERMISSION_REQUEST_CODE = 101
    private val ROLE_REQUEST_CODE = 102
    private val mainScope = CoroutineScope(Dispatchers.Main)

    private lateinit var statusText: TextView
    private lateinit var serverUrlInput: EditText
    private lateinit var emergencyPhoneInput: EditText
    private lateinit var btnSetCallScreening: Button
    private lateinit var btnTestSms: Button
    private lateinit var btnSaveSettings: Button
    private lateinit var btnViewHistory: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(createProgrammaticLayout())

        checkAndRequestPermissions()
        loadSavedPreferences()
    }

    private fun checkAndRequestPermissions() {
        val permissions = mutableListOf(
            Manifest.permission.READ_PHONE_STATE,
            Manifest.permission.RECORD_AUDIO,
            Manifest.permission.ANSWER_PHONE_CALLS
        )

        val missing = permissions.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }

        if (missing.isNotEmpty()) {
            ActivityCompat.requestPermissions(this, missing.toTypedArray(), PERMISSION_REQUEST_CODE)
        } else {
            statusText.text = "🟢 Core Permissions Granted (SIM SMS & Audio Recording Active)"
        }
    }

    private fun requestCallScreeningRole() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            val roleManager = getSystemService(Context.ROLE_SERVICE) as RoleManager
            val isHeld = roleManager.isRoleHeld(RoleManager.ROLE_CALL_SCREENING)
            if (!isHeld) {
                val intent = roleManager.createRequestRoleIntent(RoleManager.ROLE_CALL_SCREENING)
                startActivityForResult(intent, ROLE_REQUEST_CODE)
            } else {
                Toast.makeText(this, "✅ VoiceShield is already your Default Call Screening App!", Toast.LENGTH_SHORT).show()
            }
        } else {
            Toast.makeText(this, "Call screening active via system manifest.", Toast.LENGTH_SHORT).show()
        }
    }

    private fun testDeviceSimSms() {
        val targetNumber = emergencyPhoneInput.text.toString().trim()
        if (targetNumber.isEmpty()) {
            Toast.makeText(this, "Please enter a phone number to test.", Toast.LENGTH_SHORT).show()
            return
        }

        val success = DeviceSmsSender.sendDirectText(
            this,
            targetNumber,
            "✅ VoiceShield AI Mobile Verification: Your device SIM is configured to auto-dispatch real precaution SMS alerts on scam calls!"
        )

        if (success) {
            Toast.makeText(this, "✅ Test SMS sent via device SIM card!", Toast.LENGTH_LONG).show()
        } else {
            Toast.makeText(this, "❌ Failed to send SMS. Check SEND_SMS permission.", Toast.LENGTH_LONG).show()
        }
    }

    private fun saveSettings() {
        val server = serverUrlInput.text.toString().trim()
        val phone = emergencyPhoneInput.text.toString().trim()

        VoiceShieldCallScreeningService.backendServerUrl = server
        VoiceShieldCallScreeningService.emergencySmsRecipient = phone
        VoiceShieldInCallService.backendUrl = server
        VoiceShieldInCallService.emergencyPhone = phone

        val prefs = getSharedPreferences("voiceshield_prefs", Context.MODE_PRIVATE)
        prefs.edit()
            .putString("server_url", server)
            .putString("emergency_phone", phone)
            .apply()

        Toast.makeText(this, "✅ Settings Saved & Applied to Telephony Services", Toast.LENGTH_SHORT).show()
    }

    private fun loadSavedPreferences() {
        val prefs = getSharedPreferences("voiceshield_prefs", Context.MODE_PRIVATE)
        serverUrlInput.setText(prefs.getString("server_url", "http://10.0.2.2:8000"))
        emergencyPhoneInput.setText(prefs.getString("emergency_phone", "+91-99887-76655"))
    }

    private fun createProgrammaticLayout(): android.view.View {
        val scrollView = android.widget.ScrollView(this).apply {
            setBackgroundColor(android.graphics.Color.parseColor("#0B1120"))
            isFillViewport = true
        }

        val layout = android.widget.LinearLayout(this).apply {
            orientation = android.widget.LinearLayout.VERTICAL
            setPadding(40, 40, 40, 40)
        }

        val title = TextView(this).apply {
            text = "🛡️ VoiceShield AI Mobile Telephony Defense"
            textSize = 20f
            setTextColor(android.graphics.Color.WHITE)
            setTypeface(null, android.graphics.Typeface.BOLD)
            setPadding(0, 0, 0, 20)
        }
        layout.addView(title)

        statusText = TextView(this).apply {
            text = "Checking permissions..."
            textSize = 14f
            setTextColor(android.graphics.Color.parseColor("#34D399"))
            setPadding(0, 0, 0, 30)
        }
        layout.addView(statusText)

        val lbl1 = TextView(this).apply {
            text = "Backend Server URL (Host PC IP:8000):"
            setTextColor(android.graphics.Color.parseColor("#94A3B8"))
        }
        layout.addView(lbl1)

        serverUrlInput = EditText(this).apply {
            setTextColor(android.graphics.Color.WHITE)
            setBackgroundColor(android.graphics.Color.parseColor("#1E293B"))
            setPadding(20, 20, 20, 20)
        }
        layout.addView(serverUrlInput)

        val lbl2 = TextView(this).apply {
            text = "Emergency Contact Phone (for Precaution SMS):"
            setTextColor(android.graphics.Color.parseColor("#94A3B8"))
            setPadding(0, 20, 0, 0)
        }
        layout.addView(lbl2)

        emergencyPhoneInput = EditText(this).apply {
            setTextColor(android.graphics.Color.WHITE)
            setBackgroundColor(android.graphics.Color.parseColor("#1E293B"))
            setPadding(20, 20, 20, 20)
        }
        layout.addView(emergencyPhoneInput)

        val buttonParams = { topMargin: Int ->
            android.widget.LinearLayout.LayoutParams(
                android.widget.LinearLayout.LayoutParams.MATCH_PARENT,
                android.widget.LinearLayout.LayoutParams.WRAP_CONTENT
            ).apply { setMargins(0, topMargin, 0, 12) }
        }

        btnSaveSettings = Button(this).apply {
            text = "💾 Save Telephony Settings"
            setBackgroundColor(android.graphics.Color.parseColor("#2563EB"))
            setTextColor(android.graphics.Color.WHITE)
            setOnClickListener { saveSettings() }
        }
        layout.addView(btnSaveSettings, buttonParams(24))

        btnSetCallScreening = Button(this).apply {
            text = "📞 Set Default Call Screening App (Truecaller Mode)"
            setBackgroundColor(android.graphics.Color.parseColor("#059669"))
            setTextColor(android.graphics.Color.WHITE)
            setOnClickListener { requestCallScreeningRole() }
        }
        layout.addView(btnSetCallScreening, buttonParams(12))

        btnTestSms = Button(this).apply {
            text = "✉️ Test Real SMS Precaution Alert"
            setBackgroundColor(android.graphics.Color.parseColor("#D97706"))
            setTextColor(android.graphics.Color.WHITE)
            setOnClickListener { testDeviceSimSms() }
        }
        layout.addView(btnTestSms, buttonParams(12))

        btnViewHistory = Button(this).apply {
            text = "📜 View Deep Forensic Activity History"
            setBackgroundColor(android.graphics.Color.parseColor("#7C3AED"))
            setTextColor(android.graphics.Color.WHITE)
            setOnClickListener { fetchAndShowHistory() }
        }
        layout.addView(btnViewHistory, buttonParams(12))

        scrollView.addView(layout)
        return scrollView
    }

    private fun fetchAndShowHistory() {
        val serverUrl = serverUrlInput.text.toString().trim()
        Toast.makeText(this, "🔄 Fetching forensic audit history...", Toast.LENGTH_SHORT).show()

        mainScope.launch {
            val historyList = withContext(Dispatchers.IO) {
                try {
                    val url = URL("$serverUrl/api/history?limit=30")
                    val conn = url.openConnection() as HttpURLConnection
                    conn.requestMethod = "GET"
                    conn.connectTimeout = 3000
                    conn.readTimeout = 3000

                    if (conn.responseCode == 200) {
                        val resp = conn.inputStream.bufferedReader().readText()
                        val json = JSONObject(resp)
                        val arr = json.optJSONArray("history") ?: org.json.JSONArray()
                        val list = mutableListOf<JSONObject>()
                        for (i in 0 until arr.length()) {
                            list.add(arr.getJSONObject(i))
                        }
                        list
                    } else {
                        emptyList<JSONObject>()
                    }
                } catch (e: Exception) {
                    emptyList<JSONObject>()
                }
            }

            if (historyList.isEmpty()) {
                Toast.makeText(this@MainActivity, "⚠️ Could not connect to backend server or history is empty.", Toast.LENGTH_LONG).show()
                return@launch
            }

            // Build item titles
            val titles = historyList.map { item ->
                val id = item.optString("incident_id")
                val caller = item.optString("caller_or_file")
                val verdict = item.optString("verdict")
                val risk = item.optDouble("risk_percentage", 0.0)
                val icon = when (item.optString("event_type")) {
                    "PHONE_CALL_DEFENSE" -> "📞"
                    "CALL_SCREENING_INTERCEPT" -> "🛡️"
                    "AUDIO_FORENSIC_ANALYSIS" -> "🎙️"
                    else -> "✉️"
                }
                "$icon $id: $caller\n   Verdict: $verdict (${risk}%)"
            }.toTypedArray()

            AlertDialog.Builder(this@MainActivity)
                .setTitle("📜 Deep Forensic History (${historyList.size})")
                .setItems(titles) { _, which ->
                    val selected = historyList[which]
                    showIncidentDetailDialog(selected)
                }
                .setPositiveButton("Close", null)
                .show()
        }
    }

    private fun showIncidentDetailDialog(item: JSONObject) {
        val id = item.optString("incident_id")
        val timestamp = item.optString("timestamp")
        val eventType = item.optString("event_type")
        val caller = item.optString("caller_or_file")
        val claimed = item.optString("claimed_identity")
        val verdict = item.optString("verdict")
        val risk = item.optDouble("risk_percentage", 0.0)
        val action = item.optString("action_taken")

        val df = item.optJSONObject("deep_forensics") ?: JSONObject()
        val ac = df.optJSONObject("acoustic_vectors") ?: JSONObject()
        val conf = df.optJSONObject("conformer") ?: JSONObject()
        val vm = df.optJSONObject("voicemod") ?: JSONObject()
        val scam = df.optJSONObject("semantic_scam") ?: JSONObject()

        val msg = """
            🆔 Incident ID: $id
            📅 Timestamp: $timestamp
            🏷️ Event Type: $eventType
            📞 Target/Caller: $caller (Claim: $claimed)
            
            🚨 VERDICT: $verdict
            📊 Risk Percentage: ${risk}%
            ⚡ Action Taken: $action
            
            🔬 7-VECTOR ACOUSTIC METRICS:
            • Spectral Centroid: ${ac.optDouble("spectral_centroid_hz", 0.0)} Hz
            • Spectral Rolloff: ${ac.optDouble("spectral_rolloff_hz", 0.0)} Hz
            • Pitch Mean (F0): ${ac.optDouble("pitch_mean_hz", 0.0)} Hz
            • Micro-Jitter: ${ac.optDouble("jitter_pct", 0.0)}%
            • Micro-Shimmer: ${ac.optDouble("shimmer_pct", 0.0)}%
            • Harmonics-to-Noise: ${ac.optDouble("hnr_db", 0.0)} dB
            
            ⚡ NEURAL & VOICEMOD:
            • Conformer Pred: ${conf.optString("predicted_class", "N/A")} (${(conf.optDouble("raw_prob", 0.0) * 100).toInt()}%)
            • Voicemod Detected: ${if (vm.optBoolean("detected", false)) "YES" else "NO"}
            
            🧠 CONVERSATION INTENT:
            • Scam Category: ${scam.optString("category", "None")}
            • Coercion Level: ${scam.optDouble("coercion_urgency_pct", 0.0)}%
            • Transcript: "${scam.optString("transcript_snippet", df.optString("transcript_snippet", "N/A"))}"
            
            🔒 Privacy Standard: India DPDP Act 2023 (Zero-Retention)
        """.trimIndent()

        AlertDialog.Builder(this)
            .setTitle("🔬 Deep Forensic Profile: $id")
            .setMessage(msg)
            .setPositiveButton("OK", null)
            .show()
    }
}
