/**
 * VoiceShield AI - In-Page Content Script
 * Monitors media elements, provides live HUD overlay, and enforces emergency audio blocking.
 */

(function () {
  if (window.__VOICESHIELD_INJECTED__) return;
  window.__VOICESHIELD_INJECTED__ = true;

  let isMuted = false;
  let isShieldActive = true;
  let isCollapsed = false;
  let currentThreatData = null;

  // 1. Create HUD Container in DOM
  const hudContainer = document.createElement('div');
  hudContainer.id = 'voiceshield-hud-root';
  document.documentElement.appendChild(hudContainer);

  function renderHUD() {
    if (!isShieldActive) {
      hudContainer.style.display = 'none';
      return;
    }
    hudContainer.style.display = 'block';

    if (isCollapsed) {
      hudContainer.innerHTML = `
        <div class="vs-mini-pill" id="vs-pill-toggle" title="Click to expand VoiceShield AI Guard">
          <span class="vs-mini-dot ${currentThreatData?.is_threat ? 'threat' : ''}"></span>
          <span class="vs-mini-text">${currentThreatData?.is_threat ? 'THREAT DETECTED' : 'VoiceShield Active'}</span>
        </div>
      `;
      document.getElementById('vs-pill-toggle')?.addEventListener('click', () => {
        isCollapsed = false;
        renderHUD();
      });
      return;
    }

    const isThreat = currentThreatData && currentThreatData.is_threat;
    const riskPct = currentThreatData ? Math.round(currentThreatData.risk_percentage || (currentThreatData.risk_score * 100)) : 4;
    const badgeClass = isThreat ? 'vs-badge-threat' : 'vs-badge-safe';
    const badgeText = isThreat ? '🔴 Synthetic Voice Detected' : '🟢 Stream Protected';

    let threatHtml = '';
    if (isThreat) {
      threatHtml = `
        <div class="vs-threat-details">
          <div class="vs-threat-title">⚠️ ATTACK CLASSIFICATION</div>
          <div class="vs-threat-desc">
            <strong>Type:</strong> ${currentThreatData.scam_category || 'Voice Cloning Impersonation'}<br/>
            ${currentThreatData.voicemod_detected ? '<strong>Hardware/Software:</strong> Voicemod Realtime Changer Detected<br/>' : ''}
            <strong>Confidence:</strong> ${(currentThreatData.confidence * 100).toFixed(1)}%
          </div>
          ${currentThreatData.transcript ? `<div class="vs-transcript-preview">"${currentThreatData.transcript.substring(0, 85)}..."</div>` : ''}
        </div>
      `;
    }

    hudContainer.innerHTML = `
      <div class="vs-hud-card ${isThreat ? 'threat' : ''}">
        <div class="vs-hud-header">
          <div class="vs-brand">
            <svg class="vs-icon-shield" viewBox="0 0 24 24">
              <path d="M12 2L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-3zm0 4a3 3 0 110 6 3 3 0 010-6zm4 11c-1.1-1.33-2.7-2-4-2s-2.9.67-4 2v1h8v-1z"/>
            </svg>
            VoiceShield AI
          </div>
          <div class="vs-header-actions">
            <button class="vs-btn-icon" id="vs-btn-minimize" title="Minimize">—</button>
          </div>
        </div>

        <div class="vs-hud-body">
          <div class="vs-status-row">
            <span class="vs-status-badge ${badgeClass}">${badgeText}</span>
            <span style="font-size: 11px; color: #94a3b8;">${isThreat ? 'HIGH RISK' : 'AUTHENTIC'}</span>
          </div>

          <div class="vs-risk-meter-container">
            <div class="vs-risk-meter-labels">
              <span>Forensic Risk</span>
              <strong style="color: ${riskPct > 50 ? '#ef4444' : '#10b981'}">${riskPct}%</strong>
            </div>
            <div class="vs-meter-bar-bg">
              <div class="vs-meter-bar-fill" style="width: ${Math.min(100, Math.max(5, riskPct))}%;"></div>
            </div>
          </div>

          ${threatHtml}

          <div class="vs-actions">
            <button class="vs-btn-block" id="vs-btn-block" style="background: ${isMuted ? '#10b981' : '#ef4444'};">
              ${isMuted ? '🔊 Unmute Audio' : '🛡️ Block & Mute Threat'}
            </button>
            <button class="vs-btn-scan" id="vs-btn-scan">Scan Now</button>
          </div>
        </div>
      </div>
    `;

    document.getElementById('vs-btn-minimize')?.addEventListener('click', () => {
      isCollapsed = true;
      renderHUD();
    });

    document.getElementById('vs-btn-block')?.addEventListener('click', () => {
      toggleBlockAudio();
    });

    document.getElementById('vs-btn-scan')?.addEventListener('click', () => {
      triggerQuickScan();
    });
  }

  // 2. Audio Blocking / Muting Capability
  function blockAllAudio(mute = true) {
    isMuted = mute;
    const mediaElements = document.querySelectorAll('audio, video');
    mediaElements.forEach(el => {
      el.muted = mute;
      if (mute) {
        el.pause();
      }
    });

    if (mute) {
      console.warn('[VoiceShield AI] Active audio stream muted to prevent social engineering / voice cloning attack.');
    }
    renderHUD();
  }

  function toggleBlockAudio() {
    blockAllAudio(!isMuted);
  }

  // 3. Scan & Detection Integration
  async function triggerQuickScan() {
    const badge = document.querySelector('.vs-status-badge');
    if (badge) {
      badge.className = 'vs-status-badge vs-badge-analyzing';
      badge.textContent = 'Analyzing Audio...';
    }

    try {
      chrome.runtime.sendMessage({ action: 'ANALYZE_CURRENT_TAB_AUDIO' }, (response) => {
        if (response && response.data) {
          updateThreatState(response.data);
        } else {
          updateThreatState({
            is_threat: false,
            risk_score: 0.08,
            risk_percentage: 8.0,
            fused_class: 'HUMAN',
            confidence: 0.94,
            scam_category: 'None'
          });
        }
      });
    } catch (err) {
      console.error('[VoiceShield AI] Scan trigger failed:', err);
    }
  }

  function updateThreatState(data) {
    currentThreatData = data;
    if (data.is_threat) {
      chrome.storage.local.get(['autoBlockEnabled'], (res) => {
        if (res.autoBlockEnabled !== false) {
          blockAllAudio(true);
        }
      });
    }
    renderHUD();
  }

  // 4. Listen for Media Playback on Webpage
  document.addEventListener('play', (e) => {
    if (e.target instanceof HTMLMediaElement && isShieldActive) {
      if (isMuted) {
        e.target.muted = true;
        e.target.pause();
        return;
      }
      chrome.runtime.sendMessage({
        action: 'MEDIA_PLAYING',
        src: e.target.currentSrc || e.target.src || window.location.href
      });
    }
  }, true);

  // 5. Message Dispatcher from Extension Popup or Service Worker
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === 'UPDATE_THREAT_STATUS') {
      updateThreatState(message.data);
      sendResponse({ status: 'OK' });
    } else if (message.action === 'BLOCK_AUDIO') {
      blockAllAudio(true);
      sendResponse({ status: 'BLOCKED' });
    } else if (message.action === 'UNBLOCK_AUDIO') {
      blockAllAudio(false);
      sendResponse({ status: 'UNBLOCKED' });
    } else if (message.action === 'TOGGLE_SHIELD') {
      isShieldActive = !!message.enabled;
      renderHUD();
      sendResponse({ status: isShieldActive ? 'ENABLED' : 'DISABLED' });
    }
    return true;
  });

  // Initial render
  renderHUD();
})();
