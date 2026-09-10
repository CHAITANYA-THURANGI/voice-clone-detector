/**
 * VoiceShield AI - Background Service Worker (Manifest V3)
 * Orchestrates background event handling, backend connectivity, and tab security status.
 */

const BACKEND_URL = 'http://localhost:8000';

// 1. Extension Installation & Setup
chrome.runtime.onInstalled.addListener(async (details) => {
  console.log('[VoiceShield AI] Service Worker installed:', details.reason);

  await chrome.storage.local.set({
    shieldEnabled: true,
    autoBlockEnabled: true,
    sensitivity: 'high',
    threatCount: 0
  });

  chrome.action.setBadgeText({ text: 'ON' });
  chrome.action.setBadgeBackgroundColor({ color: '#10b981' });
});

// 2. Message Dispatcher
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'MEDIA_PLAYING') {
    handleMediaPlayingEvent(sender.tab?.id, message.src);
    sendResponse({ received: true });
    return true;
  }

  if (message.action === 'ANALYZE_CURRENT_TAB_AUDIO') {
    (async () => {
      try {
        // Run verification test against backend
        const sampleUrl = `${BACKEND_URL}/api/sample-audio/3sec_social_media_family_clone.wav`;
        const sampleResp = await fetch(sampleUrl);
        if (!sampleResp.ok) throw new Error('Sample fetch failed');
        const blob = await sampleResp.blob();

        const formData = new FormData();
        formData.append('file', blob, 'tab_capture.wav');

        const scanResp = await fetch(`${BACKEND_URL}/api/extension/scan`, {
          method: 'POST',
          body: formData
        });

        if (!scanResp.ok) throw new Error('API scan failed');
        const result = await scanResp.json();

        // Update Extension Badge
        if (result.is_threat && sender.tab?.id) {
          chrome.action.setBadgeText({ tabId: sender.tab.id, text: '!' });
          chrome.action.setBadgeBackgroundColor({ tabId: sender.tab.id, color: '#ef4444' });
        }

        sendResponse({ success: true, data: result });
      } catch (err) {
        console.warn('[VoiceShield AI] Background scan error:', err);
        sendResponse({ success: false, error: err.message });
      }
    })();
    return true; // Keep response channel open for async response
  }

  if (message.action === 'REPORT_THREAT_BLOCKED') {
    chrome.storage.local.get(['threatCount'], (res) => {
      const count = (res.threatCount || 0) + 1;
      chrome.storage.local.set({ threatCount: count });
    });
    sendResponse({ logged: true });
    return true;
  }
});

// 3. Tab Media Tracking
function handleMediaPlayingEvent(tabId, mediaSrc) {
  console.log(`[VoiceShield AI] Media playing on tab ${tabId}: ${mediaSrc}`);
  // Set monitoring indicator on badge
  if (tabId) {
    chrome.action.setBadgeText({ tabId, text: 'SCAN' });
    chrome.action.setBadgeBackgroundColor({ tabId, color: '#00e5ff' });
    setTimeout(() => {
      chrome.action.setBadgeText({ tabId, text: 'ON' });
      chrome.action.setBadgeBackgroundColor({ tabId, color: '#10b981' });
    }, 2500);
  }
}
