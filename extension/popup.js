/**
 * VoiceShield AI - Extension Popup Logic
 * Coordinates live telemetry, backend API integration, and in-tab attack blocking.
 */

const API_BASE = 'http://localhost:8000';

let isMutedState = false;

document.addEventListener('DOMContentLoaded', async () => {
  // Elements
  const toggleShield = document.getElementById('toggle-shield');
  const chkAutoBlock = document.getElementById('chk-autoblock');
  const btnBlockThreat = document.getElementById('btn-block-threat');
  const btnRunScan = document.getElementById('btn-run-scan');
  const selectSample = document.getElementById('select-sample');

  const statusCard = document.getElementById('status-card');
  const statusPill = document.getElementById('status-pill');
  const statusCategory = document.getElementById('status-category');
  const riskValue = document.getElementById('risk-value');
  const riskLabel = document.getElementById('risk-label');
  const threatBanner = document.getElementById('threat-banner');
  const threatTag = document.getElementById('threat-tag');
  const threatInfo = document.getElementById('threat-info');
  const transcriptBox = document.getElementById('transcript-box');

  const backendDot = document.getElementById('backend-dot');
  const backendText = document.getElementById('backend-text');

  // 1. Load Stored Preferences
  chrome.storage.local.get(['shieldEnabled', 'autoBlockEnabled', 'lastScanResult'], (res) => {
    if (res.shieldEnabled !== undefined) {
      toggleShield.checked = res.shieldEnabled;
    }
    if (res.autoBlockEnabled !== undefined) {
      chkAutoBlock.checked = res.autoBlockEnabled;
    }
    if (res.lastScanResult) {
      applyScanResultToUI(res.lastScanResult);
    }
  });

  // 2. Healthcheck Backend API
  checkBackendHealth();

  async function checkBackendHealth() {
    try {
      const resp = await fetch(`${API_BASE}/api/system-status`, { cache: 'no-store' });
      if (resp.ok) {
        const data = await resp.json();
        backendDot.className = 'status-dot';
        backendText.textContent = `Engine: Online (${data.models.EnterpriseVoiceConformer.startsWith('LOADED') ? 'Conformer + Voicemod' : 'Active'})`;
      } else {
        throw new Error('Non-200');
      }
    } catch (err) {
      backendDot.className = 'status-dot offline';
      backendText.textContent = 'Engine: Offline (Start server)';
    }
  }

  // 3. Toggle Shield Listener
  toggleShield.addEventListener('change', async () => {
    const enabled = toggleShield.checked;
    await chrome.storage.local.set({ shieldEnabled: enabled });

    const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (activeTab?.id) {
      chrome.tabs.sendMessage(activeTab.id, { action: 'TOGGLE_SHIELD', enabled });
    }
  });

  // 4. Auto-block Preference Listener
  chkAutoBlock.addEventListener('change', async () => {
    await chrome.storage.local.set({ autoBlockEnabled: chkAutoBlock.checked });
  });

  // 5. Block / Mute Button Action
  btnBlockThreat.addEventListener('click', async () => {
    isMutedState = !isMutedState;
    const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });

    if (activeTab?.id) {
      chrome.tabs.sendMessage(
        activeTab.id,
        { action: isMutedState ? 'BLOCK_AUDIO' : 'UNBLOCK_AUDIO' },
        () => {
          updateBlockButtonUI(isMutedState);
        }
      );
    } else {
      updateBlockButtonUI(isMutedState);
    }
  });

  function updateBlockButtonUI(muted) {
    if (muted) {
      btnBlockThreat.textContent = '🔊 Unmute Audio Stream';
      btnBlockThreat.className = 'btn-block-threat unmute';
    } else {
      btnBlockThreat.textContent = '🛡️ Block & Mute Synthetic Audio';
      btnBlockThreat.className = 'btn-block-threat';
    }
  }

  // 6. Test Forensic Engine Scan
  btnRunScan.addEventListener('click', async () => {
    const sample = selectSample.value;
    btnRunScan.disabled = true;
    btnRunScan.textContent = 'Scanning...';
    transcriptBox.textContent = 'Transcribing and analyzing spectral & phase harmonics...';

    try {
      // 1. Fetch audio blob from server sample endpoint
      const audioUrl = `${API_BASE}/api/sample-audio/${sample}`;
      const audioResp = await fetch(audioUrl);
      if (!audioResp.ok) {
        throw new Error(`Failed to load sample: ${audioResp.statusText}`);
      }
      const audioBlob = await audioResp.blob();

      // 2. Send to extension scan endpoint
      const formData = new FormData();
      formData.append('file', audioBlob, sample);

      const scanResp = await fetch(`${API_BASE}/api/extension/scan`, {
        method: 'POST',
        body: formData
      });

      if (!scanResp.ok) {
        throw new Error(`Scan failed: ${scanResp.statusText}`);
      }

      const scanResult = await scanResp.json();
      applyScanResultToUI(scanResult);
      await chrome.storage.local.set({ lastScanResult: scanResult });

      // Notify active tab to display in-page HUD alert
      const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (activeTab?.id) {
        chrome.tabs.sendMessage(activeTab.id, {
          action: 'UPDATE_THREAT_STATUS',
          data: scanResult
        });

        // Auto-mute if threat detected and autoblock checked
        if (scanResult.is_threat && chkAutoBlock.checked) {
          isMutedState = true;
          updateBlockButtonUI(true);
          chrome.tabs.sendMessage(activeTab.id, { action: 'BLOCK_AUDIO' });
        }
      }
    } catch (err) {
      console.error('[VoiceShield AI] Scan error:', err);
      transcriptBox.textContent = `Error during scan: ${err.message}`;
    } finally {
      btnRunScan.disabled = false;
      btnRunScan.textContent = 'Test Scan';
    }
  });

  // 7. Render Scan Result to UI
  function applyScanResultToUI(data) {
    const isThreat = data.is_threat;
    const riskPct = data.risk_percentage || Math.round((data.risk_score || 0) * 100);

    if (isThreat) {
      statusCard.className = 'status-card threat';
      statusPill.className = 'status-pill status-danger';
      statusPill.textContent = '🔴 SYNTHETIC ATTACK';
      statusCategory.textContent = data.scam_category || data.fused_class;
      riskValue.className = 'risk-value high';
      riskValue.textContent = `${riskPct}%`;
      riskLabel.textContent = `Forensic Attack Risk: HIGH (${(data.confidence * 100).toFixed(0)}% confidence)`;

      threatBanner.className = 'threat-banner active';
      threatTag.textContent = data.scam_category ? `🚨 ${data.scam_category.toUpperCase()}` : '🚨 VOICE CLONING ATTACK';

      let details = `Attack vector identified. `;
      if (data.voicemod_detected) {
        details += `Voicemod pitch/comb filter ripple (${data.voicemod_comb_ripple}) detected. `;
      }
      if (data.is_micro_clip) {
        details += `Targeted 3-second few-shot micro-clip exploit. `;
      }
      threatInfo.textContent = details;
    } else {
      statusCard.className = 'status-card';
      statusPill.className = 'status-pill status-safe';
      statusPill.textContent = '🟢 AUTHENTIC HUMAN';
      statusCategory.textContent = 'Natural Human Speech';
      riskValue.className = 'risk-value';
      riskValue.textContent = `${riskPct}%`;
      riskLabel.textContent = 'Forensic Attack Risk: LOW (Authentic)';
      threatBanner.className = 'threat-banner';
    }

    transcriptBox.textContent = data.transcript ? `"${data.transcript}"` : 'No voice transcription detected.';
  }
});
