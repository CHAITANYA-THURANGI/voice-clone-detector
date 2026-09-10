let selectedAudioSource = null; // { type: 'benchmark'|'upload'|'mic', data: ... }
let currentTab = 'benchmarks';
let mediaRecorder = null;
let audioChunks = [];
let recordInterval = null;
let recordSeconds = 0;
let timelineChart = null;
let streamCallId = null;
let streamChunkIndex = 0;
let isStreaming = false;

// Audio Context for Mic Visualizer
let audioContext = null;
let analyser = null;
let dataArray = null;
let animationId = null;

document.addEventListener('DOMContentLoaded', () => {
  initTimelineChart();
  loadBenchmarks();
  setupDropZone();
  fetchGatewayStatus();
  loadHistoryData();
});

// Switch Tabs
function switchTab(tabId, ev) {
  currentTab = tabId;
  document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

  const targetBtn = (ev && ev.currentTarget) || (window.event && window.event.currentTarget) || document.querySelector(`button[onclick*="'${tabId}'"]`);
  if (targetBtn) {
    targetBtn.classList.add('active');
  }
  const targetContent = document.getElementById(`tab-${tabId}`);
  if (targetContent) {
    targetContent.classList.add('active');
  }
}

// Update Transaction Display
function updateTxDisplay(val) {
  const display = document.getElementById('tx-amount-display');
  const num = parseInt(val, 10);
  if (num === 0) {
    display.textContent = "$0 (Standard Call)";
  } else {
    display.textContent = `$${num.toLocaleString()} (High Risk)`;
  }
}

// Initialize Chart.js Timeline
function initTimelineChart() {
  const ctx = document.getElementById('timeline-chart').getContext('2d');
  timelineChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: ['0s'],
      datasets: [
        {
          label: 'Call Risk (%)',
          data: [0],
          borderColor: '#38BDF8',
          backgroundColor: 'rgba(56, 189, 248, 0.15)',
          fill: true,
          tension: 0.35,
          borderWidth: 2,
          pointRadius: 4,
          pointBackgroundColor: '#38BDF8'
        },
        {
          label: 'Threshold (Suspicious)',
          data: [40],
          borderColor: '#F59E0B',
          borderDash: [5, 5],
          borderWidth: 1.5,
          fill: false,
          pointRadius: 0
        },
        {
          label: 'Threshold (High Risk)',
          data: [70],
          borderColor: '#EF4444',
          borderDash: [5, 5],
          borderWidth: 1.5,
          fill: false,
          pointRadius: 0
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: {
          min: 0,
          max: 100,
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#94A3B8', font: { size: 10 } }
        },
        x: {
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#94A3B8', font: { size: 10 } }
        }
      },
      plugins: {
        legend: {
          display: true,
          labels: { color: '#94A3B8', boxWidth: 12, font: { size: 10 } }
        }
      }
    }
  });
}

// Load Benchmark Audio Files
async function loadBenchmarks() {
  const listContainer = document.getElementById('benchmark-list');
  try {
    const res = await fetch('/api/benchmark-samples');
    const data = await res.json();
    listContainer.innerHTML = '';

    data.samples.forEach((sample, idx) => {
      const card = document.createElement('div');
      card.className = `benchmark-card ${idx === 0 ? 'selected' : ''}`;
      card.onclick = () => selectBenchmark(sample, card);

      const tagClass = sample.type === 'REAL' ? 'tag-real' : (sample.type === 'SCAM' ? 'tag-scam' : 'tag-fake');
      card.innerHTML = `
        <div>
          <span class="b-title">${sample.filename}</span>
          <span class="b-desc">${sample.description}</span>
        </div>
        <span class="tag ${tagClass}">${sample.type}</span>
      `;
      listContainer.appendChild(card);

      if (idx === 0) {
        selectBenchmark(sample, card);
      }
    });
  } catch (err) {
    listContainer.innerHTML = `<div style="color:#EF4444; font-size:0.85rem">Could not load benchmarks: ${err.message}</div>`;
  }
}

function selectBenchmark(sample, cardElement) {
  document.querySelectorAll('.benchmark-card').forEach(c => c.classList.remove('selected'));
  if (cardElement) cardElement.classList.add('selected');
  selectedAudioSource = { type: 'benchmark', sample: sample };
}

// File Upload Dropzone
function setupDropZone() {
  const dropZone = document.getElementById('drop-zone');
  const fileInput = document.getElementById('audio-file-input');

  dropZone.onclick = () => fileInput.click();

  dropZone.ondragover = (e) => {
    e.preventDefault();
    dropZone.style.borderColor = '#38BDF8';
  };
  dropZone.ondragleave = () => {
    dropZone.style.borderColor = '#1E293B';
  };
  dropZone.ondrop = (e) => {
    e.preventDefault();
    dropZone.style.borderColor = '#1E293B';
    if (e.dataTransfer.files.length > 0) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  };

  fileInput.onchange = (e) => {
    if (e.target.files.length > 0) {
      handleFileSelected(e.target.files[0]);
    }
  };
}

function handleFileSelected(file) {
  selectedAudioSource = { type: 'upload', file: file };
  document.getElementById('file-name-display').textContent = `${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
  document.getElementById('selected-file-info').style.display = 'flex';
  document.getElementById('drop-zone').style.display = 'none';
}

function clearSelectedFile() {
  selectedAudioSource = null;
  document.getElementById('audio-file-input').value = '';
  document.getElementById('selected-file-info').style.display = 'none';
  document.getElementById('drop-zone').style.display = 'block';
}

// Live Microphone Capture & Real-Time Oscilloscope
let liveRecordedBlob = null;

async function toggleMicrophone() {
  const btn = document.getElementById('record-btn');
  const timerDisp = document.getElementById('record-timer');

  if (!isStreaming) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioContext = new (window.AudioContext || window.webkitAudioContext)();
      const source = audioContext.createMediaStreamSource(stream);
      analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);

      const bufferLength = analyser.frequencyBinCount;
      dataArray = new Uint8Array(bufferLength);
      drawWaveform();

      streamCallId = `LIVE-${Math.random().toString(36).substr(2, 8).toUpperCase()}`;
      streamChunkIndex = 0;
      audioChunks = [];
      liveRecordedBlob = null;

      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : (MediaRecorder.isTypeSupported('audio/ogg;codecs=opus') ? 'audio/ogg;codecs=opus' : 'audio/webm');
      mediaRecorder = new MediaRecorder(stream, { mimeType });

      mediaRecorder.ondataavailable = async (e) => {
        if (e.data && e.data.size > 0) {
          audioChunks.push(e.data);
          // Send 3-second streaming chunk to server
          await sendLiveChunk(e.data);
        }
      };

      mediaRecorder.onstop = () => {
        if (audioChunks.length > 0) {
          liveRecordedBlob = new Blob(audioChunks, { type: audioChunks[0].type || 'audio/webm' });
          selectedAudioSource = { type: 'record', blob: liveRecordedBlob, filename: 'live_mic_recording.webm' };
          const hint = document.querySelector('.mic-hint');
          if (hint) {
            hint.innerHTML = `✅ <strong>Recorded ${recordSeconds}s of live speech.</strong> Click <em>"Run Voice Authenticity Analysis"</em> below to inspect complete 5-vector forensic report.`;
          }
        }
      };

      mediaRecorder.start();
      isStreaming = true;
      btn.classList.add('recording');
      btn.innerHTML = `<span class="rec-dot"></span> Stop Live Intercept`;

      recordSeconds = 0;
      let chunkTimer = 0;
      recordInterval = setInterval(() => {
        recordSeconds++;
        chunkTimer++;
        const mins = String(Math.floor(recordSeconds / 60)).padStart(2, '0');
        const secs = String(recordSeconds % 60).padStart(2, '0');
        timerDisp.textContent = `${mins}:${secs}`;

        // Cycle MediaRecorder every 3 seconds to emit fully encapsulated valid audio chunk
        if (chunkTimer >= 3 && mediaRecorder && mediaRecorder.state === 'recording') {
          chunkTimer = 0;
          mediaRecorder.stop();
          if (isStreaming) {
            mediaRecorder.start();
          }
        }
      }, 1000);

      selectedAudioSource = { type: 'record', callId: streamCallId };
    } catch (err) {
      alert(`Microphone access error: ${err.message}`);
    }
  } else {
    // Stop recording
    isStreaming = false;
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop();
      mediaRecorder.stream.getTracks().forEach(t => t.stop());
    }
    clearInterval(recordInterval);
    cancelAnimationFrame(animationId);
    btn.classList.remove('recording');
    btn.innerHTML = `<span class="rec-dot"></span> Start Live Intercept`;
  }
}

function drawWaveform() {
  const canvas = document.getElementById('waveform-canvas');
  const ctx = canvas.getContext('2d');
  animationId = requestAnimationFrame(drawWaveform);

  analyser.getByteTimeDomainData(dataArray);
  ctx.fillStyle = '#0F172A';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  ctx.lineWidth = 2;
  ctx.strokeStyle = '#38BDF8';
  ctx.beginPath();

  const sliceWidth = canvas.width * 1.0 / dataArray.length;
  let x = 0;

  for (let i = 0; i < dataArray.length; i++) {
    const v = dataArray[i] / 128.0;
    const y = v * (canvas.height / 2);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
    x += sliceWidth;
  }

  ctx.lineTo(canvas.width, canvas.height / 2);
  ctx.stroke();
}

async function sendLiveChunk(blob) {
  const formData = new FormData();
  const ext = (blob.type && blob.type.includes('ogg')) ? 'ogg' : 'webm';
  formData.append('file', blob, `chunk_${streamChunkIndex++}.${ext}`);
  formData.append('call_id', streamCallId);
  formData.append('timestamp_sec', recordSeconds);
  formData.append('transaction_amount', document.getElementById('tx-amount').value);
  formData.append('is_cxo_call', document.getElementById('is-cxo').checked);
  formData.append('is_cxo', document.getElementById('is-cxo').checked);

  try {
    const res = await fetch('/api/stream-chunk', { method: 'POST', body: formData });
    if (!res.ok) return;
    const data = await res.json();
    renderStreamChunkResult(data);
  } catch (err) {
    console.error('Error streaming chunk:', err);
  }
}

function renderStreamChunkResult(data) {
  const session = data.session_assessment || data.risk_assessment;
  const chunk = data.chunk_record;
  const plan = data.prevention_plan;

  updateRiskDisplay(session.risk_level, session.risk_percentage, session.summary, plan);

  // Update timeline chart
  const timeLabel = `${chunk.timestamp_sec}s`;
  timelineChart.data.labels.push(timeLabel);
  timelineChart.data.datasets[0].data.push(session.risk_percentage);
  timelineChart.data.datasets[1].data.push(40);
  timelineChart.data.datasets[2].data.push(70);

  if (timelineChart.data.labels.length > 15) {
    timelineChart.data.labels.shift();
    timelineChart.data.datasets[0].data.shift();
    timelineChart.data.datasets[1].data.shift();
    timelineChart.data.datasets[2].data.shift();
  }
  timelineChart.update();

  // Vector 1: Neural Conformer Model Card
  if (data.neural_detector) {
    const neural = data.neural_detector;
    document.getElementById('val-neural-prob').textContent = `${(neural.fake_probability * 100).toFixed(1)}%`;
    document.getElementById('prog-neural').style.width = `${neural.fake_probability * 100}%`;
    document.getElementById('prog-neural').style.backgroundColor = neural.prediction === 'FAKE' ? '#EF4444' : '#10B981';
    document.getElementById('val-neural-pred').textContent = `Prediction: ${neural.prediction} (${neural.confidence}% Conf)`;
  }

  // Vector 2: Glottal Biometrics Card
  if (data.glottal_biometrics) {
    const glottal = data.glottal_biometrics;
    const glottalScore = glottal.glottal_anomaly_score || 0.0;
    document.getElementById('val-glottal-score').textContent = `${(glottalScore * 100).toFixed(1)}%`;
    document.getElementById('val-glottal-score').style.color = glottalScore > 0.4 ? '#EF4444' : '#10B981';
    document.getElementById('val-kurtosis').textContent = glottal.residual_kurtosis || '--';
    document.getElementById('val-glottal-status').textContent = glottal.glottal_status ? (glottalScore < 0.4 ? 'Natural Impulse' : 'Synthetic Vocal Tract') : '--';
    document.getElementById('val-glottal-status').style.color = glottalScore > 0.4 ? '#EF4444' : '#10B981';

    if (glottal.waveform_preview && glottal.waveform_preview.length > 0) {
      drawGlottalResidual(glottal.waveform_preview);
    }
  }

  // Vector 3: Phase Forensics Card
  if (data.phase_forensics) {
    const phase = data.phase_forensics;
    const phaseScore = phase.phase_incoherence_score || 0.0;
    document.getElementById('val-phase-score').textContent = `${(phaseScore * 100).toFixed(1)}%`;
    document.getElementById('val-phase-score').style.color = phaseScore > 0.4 ? '#EF4444' : '#10B981';
    document.getElementById('val-phase-jitter').textContent = phase.high_freq_phase_jitter || '--';
    document.getElementById('val-phase-status').textContent = phase.status ? (phaseScore < 0.4 ? 'Continuous Phase' : 'Vocoder Phase Jitter') : '--';
    document.getElementById('val-phase-status').style.color = phaseScore > 0.4 ? '#EF4444' : '#10B981';
  }

  // Vector 4: Prosody & Spectral Metrics
  if (chunk.metrics) {
    document.getElementById('val-f0-std').textContent = `${chunk.metrics.f0_std_hz} Hz`;
    document.getElementById('val-jitter').textContent = `${chunk.metrics.jitter}%`;
    document.getElementById('val-rolloff').textContent = `${chunk.metrics.spectral_rolloff_hz} Hz`;
    document.getElementById('val-hf-ratio').textContent = `${chunk.metrics.hf_energy_ratio}`;
  }

  // SIEM CEF Event Preview
  if (data.enterprise_telemetry && data.enterprise_telemetry.cef_event) {
    document.getElementById('cef-preview').textContent = data.enterprise_telemetry.cef_event;
  }

  // Compliance Footer
  if (plan && plan.incident_id) {
    document.getElementById('disp-incident-id').textContent = plan.incident_id;
  }
  document.getElementById('disp-sha256').textContent = chunk.sha256;
}

// Run Complete Audio File Analysis
async function runAnalysis() {
  const analyzeBtn = document.getElementById('analyze-btn');
  analyzeBtn.disabled = true;
  analyzeBtn.innerHTML = '⏳ Analyzing Voice Signatures...';

  try {
    let audioBlob = null;
    let fileName = 'audio.wav';

    if (currentTab === 'benchmarks') {
      if (!selectedAudioSource || !selectedAudioSource.sample) {
        alert('Please select a benchmark sample first.');
        return;
      }
      const fetchAudio = await fetch(selectedAudioSource.sample.url);
      audioBlob = await fetchAudio.blob();
      fileName = selectedAudioSource.sample.filename;
    } else if (currentTab === 'upload') {
      if (!selectedAudioSource || !selectedAudioSource.file) {
        alert('Please upload an audio file first.');
        return;
      }
      audioBlob = selectedAudioSource.file;
      fileName = selectedAudioSource.file.name;
    } else if (currentTab === 'record') {
      if (!liveRecordedBlob && audioChunks.length === 0) {
        alert('Please record voice using "Start Live Intercept" first.');
        return;
      }
      audioBlob = liveRecordedBlob || new Blob(audioChunks, { type: audioChunks[0]?.type || 'audio/webm' });
      fileName = 'live_intercept_recording.webm';
    }


    const formData = new FormData();
    formData.append('file', audioBlob, fileName);
    formData.append('transaction_amount', document.getElementById('tx-amount').value);
    formData.append('is_cxo_call', document.getElementById('is-cxo').checked);
    formData.append('credential_request', document.getElementById('credential-req').checked);

    const claimedSpeaker = document.getElementById('claimed-speaker').value.trim();
    if (claimedSpeaker) {
      formData.append('claimed_speaker_id', claimedSpeaker);
    }

    const res = await fetch('/api/analyze-audio', { method: 'POST', body: formData });
    const rawText = await res.text();
    let data;
    try {
      data = JSON.parse(rawText);
    } catch (e) {
      let errMsg = `Server returned status ${res.status}`;
      if (res.status === 502) {
        errMsg = `Server returned status 502 (Bad Gateway). The cloud instance may be spinning up or restarting. Please try again in 15-30 seconds.`;
      } else if (rawText.includes('<title>')) {
        const match = rawText.match(/<title>(.*?)<\/title>/i);
        if (match && match[1]) errMsg = `Server Error (${res.status}): ${match[1]}`;
      }
      throw new Error(errMsg);
    }

    if (!res.ok) {
      throw new Error(data.detail || `Server returned status ${res.status}`);
    }

    renderAnalysisResults(data);
    saveAnalysisResultToChromeCache(data, fileName);
    loadHistoryData(true);
  } catch (err) {
    alert(`Analysis Error: ${err.message}`);
  } finally {
    analyzeBtn.disabled = false;
    analyzeBtn.innerHTML = '🔍 Run Voice Authenticity Analysis';
  }
}

// Render Results to UI
function renderAnalysisResults(data) {
  const risk = data.risk_assessment;
  const neural = data.neural_detector;
  const metrics = data.forensic_metrics;
  const plan = data.prevention_plan;
  const spk = data.speaker_verification;
  const audit = data.compliance_audit;

  const fusion = data.ensemble_fusion || {};
  const predictedClass = fusion.predicted_class || risk.predicted_class;
  updateRiskDisplay(risk.risk_level, risk.risk_percentage, risk.summary, plan, predictedClass, risk.badge);

  // Deep Multi-Model Ensemble Consensus Card
  if (data.ensemble_fusion) {
    const pClass = fusion.predicted_class || 'UNKNOWN';
    const conf = fusion.consensus_confidence_pct || 0;
    const agree = `${Math.round((fusion.model_agreement_ratio || 0) * 100)}% Models`;
    const uncert = `${Math.round((fusion.uncertainty_index || 0) * 100)}% Uncertainty`;

    const badgeEl = document.getElementById('val-consensus-badge');
    const predEl = document.getElementById('val-consensus-pred');
    if (predEl) predEl.textContent = pClass.replace(/_/g, ' ');

    if (badgeEl) {
      if (pClass === 'VOICE_CLONING_ATTACK') {
        badgeEl.textContent = '🔴 VOICE CLONE ATTACK';
        badgeEl.style.color = '#EF4444';
        badgeEl.style.borderColor = '#EF4444';
        badgeEl.style.background = 'rgba(239, 68, 68, 0.15)';
        if (predEl) predEl.style.color = '#EF4444';
      } else if (pClass === 'NON_HUMAN') {
        badgeEl.textContent = '🤖 NON-HUMAN / TTS';
        badgeEl.style.color = '#F59E0B';
        badgeEl.style.borderColor = '#F59E0B';
        badgeEl.style.background = 'rgba(245, 158, 11, 0.15)';
        if (predEl) predEl.style.color = '#F59E0B';
      } else {
        badgeEl.textContent = '🟢 AUTHENTIC HUMAN';
        badgeEl.style.color = '#10B981';
        badgeEl.style.borderColor = '#10B981';
        badgeEl.style.background = 'rgba(16, 185, 129, 0.15)';
        if (predEl) predEl.style.color = '#10B981';
      }
    }

    const confEl = document.getElementById('val-consensus-conf');
    const agreeEl = document.getElementById('val-consensus-agree');
    const uncertEl = document.getElementById('val-consensus-uncert');
    if (confEl) confEl.textContent = `${conf}%`;
    if (agreeEl) agreeEl.textContent = agree;
    if (uncertEl) uncertEl.textContent = uncert;

    if (fusion.probabilities) {
      const pH = (fusion.probabilities.human * 100).toFixed(1);
      const pNH = (fusion.probabilities.non_human * 100).toFixed(1);
      const pAtk = (fusion.probabilities.voice_cloning_attack * 100).toFixed(1);

      const pH_el = document.getElementById('prob-val-human');
      const pNH_el = document.getElementById('prob-val-nonhuman');
      const pAtk_el = document.getElementById('prob-val-attack');
      if (pH_el) pH_el.textContent = `${pH}%`;
      if (pNH_el) pNH_el.textContent = `${pNH}%`;
      if (pAtk_el) pAtk_el.textContent = `${pAtk}%`;

      const barH = document.getElementById('bar-human');
      const barNH = document.getElementById('bar-nonhuman');
      const barAtk = document.getElementById('bar-attack');
      if (barH) barH.style.width = `${pH}%`;
      if (barNH) barNH.style.width = `${pNH}%`;
      if (barAtk) barAtk.style.width = `${pAtk}%`;
    }

    const reasonsUl = document.getElementById('val-forensic-reasons');
    if (reasonsUl && fusion.forensic_explanations) {
      reasonsUl.innerHTML = '';
      fusion.forensic_explanations.forEach(r => {
        const li = document.createElement('li');
        li.textContent = r;
        reasonsUl.appendChild(li);
      });
    }
  }

  // Semantic Audio-Language (ALM/LLM) Cyber-Scam Intelligence Card
  const semantic = data.semantic_fraud_detector || (risk.semantic_assessment) || {};
  const scamBadge = document.getElementById('val-scam-badge');
  const dualAcoustic = document.getElementById('val-dual-acoustic');
  const dualSemantic = document.getElementById('val-dual-semantic');
  const dualVerdict = document.getElementById('val-dual-verdict');
  const transcriptBox = document.getElementById('val-speech-transcript');
  const engineTag = document.getElementById('val-alm-engine');
  const coercionPct = document.getElementById('val-coercion-pct');
  const coercionBar = document.getElementById('bar-coercion');
  const flaggedKws = document.getElementById('val-flagged-keywords');
  const tacticsList = document.getElementById('val-scam-tactics');

  const isScam = semantic.is_scam || false;
  const scamCategory = semantic.display_category || (isScam ? "🚨 Cyber Fraud Attack" : "🟢 Legitimate / Safe Dialog");

  if (scamBadge) {
    scamBadge.textContent = scamCategory;
    if (isScam) {
      scamBadge.style.color = '#EF4444';
      scamBadge.style.borderColor = '#EF4444';
      scamBadge.style.background = 'rgba(239, 68, 68, 0.15)';
    } else {
      scamBadge.style.color = '#10B981';
      scamBadge.style.borderColor = '#10B981';
      scamBadge.style.background = 'rgba(16, 185, 129, 0.15)';
    }
  }

  if (dualAcoustic) {
    const acClass = predictedClass || 'UNKNOWN';
    dualAcoustic.textContent = acClass.replace(/_/g, ' ');
    dualAcoustic.style.color = acClass === 'VOICE_CLONING_ATTACK' ? '#EF4444' : (acClass === 'NON_HUMAN' ? '#F59E0B' : '#10B981');
  }

  if (dualSemantic) {
    dualSemantic.textContent = isScam ? scamCategory : "🟢 Benign Dialog";
    dualSemantic.style.color = isScam ? '#EF4444' : '#10B981';
  }

  if (dualVerdict) {
    const verdictStr = (fusion.dual_matrix_verdict || (isScam ? "HUMAN_SOCIAL_ENGINEERING_SCAM" : "AUTHENTIC_HUMAN_SAFE")).replace(/_/g, ' ');
    dualVerdict.textContent = verdictStr;
    if (verdictStr.includes('CLONED') || verdictStr.includes('ATTACK') || verdictStr.includes('SCAM')) {
      dualVerdict.style.color = '#EF4444';
    } else if (verdictStr.includes('SYNTHETIC')) {
      dualVerdict.style.color = '#F59E0B';
    } else {
      dualVerdict.style.color = '#10B981';
    }
  }

  if (transcriptBox) {
    const transcriptText = data.transcript || semantic.transcript || "";
    if (transcriptText.trim()) {
      transcriptBox.textContent = `"${transcriptText}"`;
      transcriptBox.style.fontStyle = 'normal';
      transcriptBox.style.color = '#F8FAFC';
    } else {
      transcriptBox.textContent = "(No verbal speech detected in audio stream)";
      transcriptBox.style.fontStyle = 'italic';
      transcriptBox.style.color = '#94A3B8';
    }
  }

  if (engineTag) {
    engineTag.textContent = semantic.engine_used || "Whisper ALM + LLM/NLP";
  }

  const cScore = Math.round((semantic.coercion_urgency_score || 0) * 100);
  if (coercionPct) coercionPct.textContent = `${cScore}%`;
  if (coercionBar) {
    coercionBar.style.width = `${cScore}%`;
    coercionBar.style.background = cScore > 50 ? '#EF4444' : (cScore > 25 ? '#F59E0B' : '#10B981');
  }

  if (flaggedKws) {
    flaggedKws.innerHTML = '';
    const kws = semantic.flagged_keywords || [];
    if (kws.length > 0) {
      kws.forEach(kw => {
        const span = document.createElement('span');
        span.className = 'kw-tag';
        span.textContent = kw;
        flaggedKws.appendChild(span);
      });
    } else {
      flaggedKws.innerHTML = '<span class="empty-tag">No suspicious trigger phrases detected</span>';
    }
  }

  if (tacticsList) {
    tacticsList.innerHTML = '';
    const tactics = semantic.tactics_detected || [];
    if (tactics.length > 0) {
      tactics.forEach(t => {
        const li = document.createElement('li');
        li.textContent = t;
        tacticsList.appendChild(li);
      });
    } else {
      tacticsList.innerHTML = '<li>Legitimate communication — zero coercive exploitation patterns.</li>';
    }
  }

  // Neural Model Card
  document.getElementById('val-neural-prob').textContent = `${(neural.fake_probability * 100).toFixed(1)}%`;
  document.getElementById('prog-neural').style.width = `${neural.fake_probability * 100}%`;
  document.getElementById('prog-neural').style.backgroundColor = neural.prediction === 'FAKE' ? '#EF4444' : '#10B981';
  const neuralClassDisplay = neural.predicted_class ? `${neural.predicted_class} (${neural.confidence}% Conf)` : `${neural.prediction} (${neural.confidence}% Conf)`;
  document.getElementById('val-neural-pred').textContent = `Prediction: ${neuralClassDisplay}`;

  // Glottal Biometrics Card
  const glottal = data.glottal_biometrics || {};
  const glottalScore = glottal.glottal_anomaly_score || 0.0;
  const isAttack = risk.risk_level === 'HIGH' || neural.prediction === 'FAKE';
  document.getElementById('val-glottal-score').textContent = `${(glottalScore * 100).toFixed(1)}%`;
  document.getElementById('val-glottal-score').style.color = (glottalScore > 0.4 || isAttack) ? '#EF4444' : '#10B981';
  document.getElementById('val-kurtosis').textContent = glottal.residual_kurtosis || '--';
  document.getElementById('val-glottal-status').textContent = glottal.display_status || (glottalScore > 0.4 || isAttack ? 'Synthetic Vocal Tract' : 'Natural Impulse');
  document.getElementById('val-glottal-status').style.color = (glottalScore > 0.4 || isAttack) ? '#EF4444' : '#10B981';

  // Draw Glottal Residual Pulse Scope
  if (glottal.waveform_preview && glottal.waveform_preview.length > 0) {
    drawGlottalResidual(glottal.waveform_preview);
  }

  // Phase Forensics Card
  const phase = data.phase_forensics || {};
  const phaseScore = phase.phase_incoherence_score || 0.0;
  document.getElementById('val-phase-score').textContent = `${(phaseScore * 100).toFixed(1)}%`;
  document.getElementById('val-phase-score').style.color = (phaseScore > 0.4 || isAttack) ? '#EF4444' : '#10B981';
  document.getElementById('val-phase-jitter').textContent = phase.high_freq_phase_jitter || '--';
  document.getElementById('val-phase-status').textContent = phase.display_status || (phaseScore > 0.4 || isAttack ? 'Vocoder Phase Jitter' : 'Continuous Phase');
  document.getElementById('val-phase-status').style.color = (phaseScore > 0.4 || isAttack) ? '#EF4444' : '#10B981';

  // Vocoder Spectral Card
  const specScore = risk.sub_scores.spectral_artifact_score;
  document.getElementById('val-spectral-score').textContent = `${(specScore * 100).toFixed(1)}%`;
  document.getElementById('val-spectral-score').style.color = specScore > 0.4 ? '#EF4444' : '#10B981';
  document.getElementById('val-rolloff').textContent = `${metrics.spectral_rolloff_hz} Hz`;
  document.getElementById('val-hf-ratio').textContent = `${metrics.hf_energy_ratio}`;

  // Prosody Card
  const prosodyScore = risk.sub_scores.prosody_unnatural_score;
  document.getElementById('val-prosody-score').textContent = `${(prosodyScore * 100).toFixed(1)}%`;
  document.getElementById('val-prosody-score').style.color = prosodyScore > 0.4 ? '#EF4444' : '#10B981';
  document.getElementById('val-f0-std').textContent = `${metrics.f0_std_hz} Hz`;
  document.getElementById('val-jitter').textContent = `${metrics.jitter}%`;

  // Speaker Card
  if (spk && spk.enrolled) {
    document.getElementById('val-speaker-score').textContent = `${(spk.similarity * 100).toFixed(1)}%`;
    document.getElementById('val-spk-enrolled').textContent = spk.claimed_speaker;
    document.getElementById('val-spk-match').textContent = spk.status;
    document.getElementById('val-spk-match').style.color = spk.is_impersonation_mismatch ? '#EF4444' : '#10B981';
  } else {
    document.getElementById('val-speaker-score').textContent = 'N/A';
    document.getElementById('val-spk-enrolled').textContent = 'Not Claimed';
    document.getElementById('val-spk-match').textContent = 'Baseline Passed';
    document.getElementById('val-spk-match').style.color = '#94A3B8';
  }

  // Pretrained Foundation Speech Model Card
  if (data.pretrained_foundation) {
    const found = data.pretrained_foundation;
    const foundProb = found.pretrained_fake_prob || 0.0;
    document.getElementById('val-foundation-prob').textContent = `${(foundProb * 100).toFixed(1)}%`;
    document.getElementById('val-foundation-prob').style.color = (foundProb > 0.4 || isAttack) ? '#EF4444' : '#10B981';
    document.getElementById('val-foundation-stability').textContent = `${found.foundation_stability || '--'} m/s²`;
    document.getElementById('val-foundation-verdict').textContent = found.display_verdict || (found.prediction === 'FAKE' || isAttack ? 'Synthetic Dispersion' : 'Biological Dynamics');
    document.getElementById('val-foundation-verdict').style.color = (found.prediction === 'FAKE' || isAttack) ? '#EF4444' : '#10B981';
  }

  // SIEM CEF Event Preview
  if (data.enterprise_telemetry && data.enterprise_telemetry.cef_event) {
    document.getElementById('cef-preview').textContent = data.enterprise_telemetry.cef_event;
  }

  // Update Timeline Chart (Simulated 5 points across duration)
  const dur = data.audio_metadata.duration_sec;
  const p1 = Math.round(risk.risk_percentage * 0.85);
  const p2 = Math.round(risk.risk_percentage * 0.95);
  const p3 = Math.round(risk.risk_percentage);

  timelineChart.data.labels = ['0.0s', `${(dur * 0.5).toFixed(1)}s`, `${dur.toFixed(1)}s`];
  timelineChart.data.datasets[0].data = [p1, p2, p3];
  timelineChart.data.datasets[1].data = [40, 40, 40];
  timelineChart.data.datasets[2].data = [70, 70, 70];
  timelineChart.update();

  // Compliance Footer
  document.getElementById('disp-incident-id').textContent = plan.incident_id;
  document.getElementById('disp-sha256').textContent = data.audio_metadata.sha256;
}

function updateRiskDisplay(level, percentage, summary, plan, predictedClass, riskBadge) {
  const banner = document.getElementById('risk-banner');
  const badge = document.getElementById('risk-badge');
  const score = document.getElementById('risk-score-display');
  const sumText = document.getElementById('risk-summary');

  banner.className = `risk-banner risk-${level.toLowerCase()}`;
  score.textContent = `${percentage}% RISK`;
  sumText.textContent = summary;

  if (riskBadge) {
    badge.textContent = riskBadge;
  } else if (predictedClass === 'VOICE_CLONING_ATTACK') {
    badge.textContent = '🔴 HIGH RISK (VOICE CLONING ATTACK)';
  } else if (predictedClass === 'NON_HUMAN') {
    badge.textContent = '🤖 NON-HUMAN / SYNTHETIC AUDIO';
  } else if (predictedClass === 'HUMAN') {
    badge.textContent = '🟢 LOW RISK (AUTHENTIC HUMAN)';
  } else {
    if (level === 'LOW') {
      badge.textContent = '🟢 LOW RISK (AUTHENTIC)';
    } else if (level === 'SUSPICIOUS') {
      badge.textContent = '🟡 SUSPICIOUS (VERIFICATION REQUIRED)';
    } else {
      badge.textContent = '🔴 HIGH RISK (VOICE CLONING ATTACK)';
    }
  }

  // Prevention Card
  document.getElementById('prevention-action-title').textContent = plan.action_title;
  document.getElementById('prevention-immediate-action').textContent = plan.immediate_action;

  const stepsList = document.getElementById('prevention-steps-list');
  stepsList.innerHTML = '';
  plan.recommended_steps.forEach(step => {
    const li = document.createElement('li');
    li.textContent = step;
    stepsList.appendChild(li);
  });
}

function drawGlottalResidual(samples) {
  const canvas = document.getElementById('glottal-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#0F172A';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  ctx.lineWidth = 1.5;
  ctx.strokeStyle = '#10B981';
  ctx.beginPath();

  const maxVal = Math.max(...samples.map(Math.abs)) || 1.0;
  const sliceWidth = canvas.width / samples.length;
  let x = 0;

  for (let i = 0; i < samples.length; i++) {
    const norm = samples[i] / maxVal;
    const y = (canvas.height / 2) - (norm * (canvas.height * 0.4));
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
    x += sliceWidth;
  }
  ctx.stroke();
}

function copyCefEvent() {
  const text = document.getElementById('cef-preview').textContent;
  navigator.clipboard.writeText(text).then(() => {
    alert('✅ Enterprise CEF Syslog event copied to clipboard!');
  }).catch(() => {
    alert('Failed to copy to clipboard.');
  });
}

// =========================================================================
// REAL-TIME PHONE CALL DEFENSE & PRECAUTION ALERT LOGIC
// =========================================================================

let activePhoneCallId = null;
let phoneCallTimer = null;
let phoneCallSeconds = 0;
let lastDispatchedEmailHtml = '';

async function startPhoneCallSimulation() {
  const callerNum = document.getElementById('phone-caller-num').value || '+91-98765-43210';
  const claimedId = document.getElementById('phone-claimed-id').value || 'Unknown Number';
  const scenarioFile = document.getElementById('phone-audio-scenario').value;
  const userNum = document.getElementById('phone-user-num').value || '+91-99887-76655';
  const familyNum = document.getElementById('phone-family-num').value || '+91-91234-56789';

  const startBtn = document.getElementById('phone-start-btn');
  const dropBtn = document.getElementById('phone-drop-btn');
  const hud = document.getElementById('phone-hud');
  const statusBadge = document.getElementById('phone-status-badge');
  const timerDisplay = document.getElementById('phone-timer');
  const spkMatchDisplay = document.getElementById('phone-spk-match');
  const riskVal = document.getElementById('phone-risk-val');
  const riskBar = document.getElementById('phone-risk-bar');
  const transcriptBox = document.getElementById('phone-transcript-box');
  const alertsArea = document.getElementById('phone-alerts-area');

  // 1. Reset UI
  startBtn.disabled = true;
  dropBtn.disabled = false;
  hud.className = 'phone-call-hud in-call';
  statusBadge.className = 'call-status-badge call-status-active';
  statusBadge.textContent = '🟢 IN-CALL (MONITORING AUDIO)';
  alertsArea.style.display = 'none';

  spkMatchDisplay.textContent = 'Analyzing Voiceprint Directory (1:N Search)...';
  spkMatchDisplay.style.color = '#38BDF8';
  transcriptBox.textContent = 'Connecting telephone audio stream...';

  // Timer
  phoneCallSeconds = 0;
  clearInterval(phoneCallTimer);
  phoneCallTimer = setInterval(() => {
    phoneCallSeconds++;
    const mins = String(Math.floor(phoneCallSeconds / 60)).padStart(2, '0');
    const secs = String(phoneCallSeconds % 60).padStart(2, '0');
    timerDisplay.textContent = `${mins}:${secs}`;
  }, 1000);

  try {
    // 2. Initialize Call Session
    const startForm = new FormData();
    startForm.append('caller_number', callerNum);
    startForm.append('caller_claimed_name', claimedId);
    startForm.append('user_phone', userNum);
    startForm.append('emergency_contact', familyNum);

    const startResp = await fetch('/api/phone-call/start', { method: 'POST', body: startForm });
    const sessionData = await startResp.json();
    activePhoneCallId = sessionData.session_id;

    // 3. Fetch Scenario Audio Blob
    const audioResp = await fetch(`/api/sample-audio/${scenarioFile}`);
    if (!audioResp.ok) throw new Error('Failed to load scenario audio file');
    const audioBlob = await audioResp.blob();

    // 4. Stream Audio Chunk to Engine
    transcriptBox.textContent = 'Streaming call chunk for forensic evaluation...';
    const chunkForm = new FormData();
    chunkForm.append('session_id', activePhoneCallId);
    chunkForm.append('auto_drop_threshold', '0.75');
    chunkForm.append('file', audioBlob, scenarioFile);

    const chunkResp = await fetch('/api/phone-call/stream-chunk', { method: 'POST', body: chunkForm });
    if (!chunkResp.ok) throw new Error('Chunk processing failed');
    const result = await chunkResp.json();

    // 5. Update UI with Telephony Telemetry
    const riskPct = result.effective_risk_percentage || 0;
    riskVal.textContent = `${riskPct}%`;
    riskBar.style.width = `${Math.min(100, Math.max(4, riskPct))}%`;
    riskVal.style.color = riskPct >= 75 ? '#EF4444' : (riskPct >= 40 ? '#F59E0B' : '#10B981');

    transcriptBox.textContent = result.accumulated_transcript ? `"${result.accumulated_transcript}"` : 'No verbal speech detected.';

    // Speaker Identification Details
    const spk = result.speaker_identification || {};
    const disc = spk.discrepancy || {};
    if (disc.is_discrepancy) {
      spkMatchDisplay.textContent = `🚨 IMPOSTER MISMATCH: Claims '${claimedId}', Acoustics Mismatch (${disc.similarity_pct}% match)`;
      spkMatchDisplay.style.color = '#EF4444';
    } else if (spk.is_known_contact) {
      spkMatchDisplay.textContent = `🎯 VERIFIED CONTACT: ${spk.identified_name} (${spk.similarity_pct}% match)`;
      spkMatchDisplay.style.color = '#10B981';
    } else {
      spkMatchDisplay.textContent = `⚪ UNKNOWN CALLER: ${spk.identified_name} (${spk.similarity_pct || 0}% match)`;
      spkMatchDisplay.style.color = '#94A3B8';
    }

    // 6. Automated Call Drop Reaction
    if (result.call_terminated) {
      clearInterval(phoneCallTimer);
      hud.className = 'phone-call-hud terminated';
      statusBadge.className = 'call-status-badge call-status-dropped';
      statusBadge.textContent = '🛑 CALL AUTOMATICALLY TERMINATED';

      // Show Precaution Alert Box
      alertsArea.style.display = 'block';
      const smsTextPreview = document.getElementById('sms-text-preview');
      const smsTimeStamp = document.getElementById('sms-time-stamp');

      if (result.dispatched_alerts && result.dispatched_alerts.length > 0) {
        const smsAlert = result.dispatched_alerts[0];
        smsTextPreview.textContent = smsAlert.content;
        smsTimeStamp.textContent = smsAlert.timestamp || 'JUST NOW';

        if (result.dispatched_alerts.length > 1) {
          lastDispatchedEmailHtml = result.dispatched_alerts[1].html_content || '';
        }
      }

      startBtn.disabled = false;
      dropBtn.disabled = true;
    } else {
      // Benign Call completed safely
      setTimeout(() => {
        clearInterval(phoneCallTimer);
        statusBadge.className = 'call-status-badge call-status-active';
        statusBadge.textContent = '✅ CALL COMPLETED (SAFE)';
        startBtn.disabled = false;
        dropBtn.disabled = true;
      }, 3000);
    }
  } catch (err) {
    console.error('Call simulation error:', err);
    clearInterval(phoneCallTimer);
    transcriptBox.textContent = `Error in call defense stream: ${err.message}`;
    startBtn.disabled = false;
    dropBtn.disabled = true;
  }
}

async function terminatePhoneCallManually() {
  if (!activePhoneCallId) return;
  clearInterval(phoneCallTimer);

  const dropBtn = document.getElementById('phone-drop-btn');
  const startBtn = document.getElementById('phone-start-btn');
  const hud = document.getElementById('phone-hud');
  const statusBadge = document.getElementById('phone-status-badge');

  try {
    const form = new FormData();
    form.append('session_id', activePhoneCallId);
    form.append('reason', 'Manual User Terminate');

    await fetch('/api/phone-call/terminate', { method: 'POST', body: form });

    hud.className = 'phone-call-hud terminated';
    statusBadge.className = 'call-status-badge call-status-dropped';
    statusBadge.textContent = '🛑 CALL MANUALLY HUNG UP';

    dropBtn.disabled = true;
    startBtn.disabled = false;
  } catch (err) {
    console.error('Error terminating call:', err);
  }
}

function openEmailModal() {
  const modal = document.getElementById('email-modal');
  const body = document.getElementById('email-modal-body');
  if (modal && body) {
    body.innerHTML = lastDispatchedEmailHtml || '<p style="color:#94a3b8;">No email alert generated for this session.</p>';
    modal.style.display = 'flex';
  }
}

function closeEmailModal() {
  const modal = document.getElementById('email-modal');
  if (modal) {
    modal.style.display = 'none';
  }
}

// -----------------------------------------------------------------------------
// Real-World Alert Gateway Configuration & Live Verification
// -----------------------------------------------------------------------------

async function fetchGatewayStatus() {
  try {
    const res = await fetch('/api/phone-call/gateway-status');
    if (!res.ok) return;
    const status = await res.json();

    const pill = document.getElementById('gateway-status-pill');
    const userField = document.getElementById('gw-smtp-user');
    const recipientField = document.getElementById('gw-recipient-email');
    const modeSelect = document.getElementById('gw-sms-mode');

    if (status.email) {
      if (status.email.configured) {
        if (pill) {
          pill.textContent = '🟢 EMAIL CONNECTED';
          pill.style.background = 'rgba(16, 185, 129, 0.15)';
          pill.style.color = '#10B981';
          pill.style.borderColor = '#10B981';
        }
      } else {
        if (pill) {
          pill.textContent = '🟡 CONFIG REQUIRED';
          pill.style.background = 'rgba(245, 158, 11, 0.15)';
          pill.style.color = '#F59E0B';
          pill.style.borderColor = '#F59E0B';
        }
      }

      if (userField && status.email.sender_email && status.email.sender_email !== 'Not configured') {
        userField.value = status.email.sender_email;
      }
      if (recipientField && status.email.recipient_email && status.email.recipient_email !== 'Not configured') {
        recipientField.value = status.email.recipient_email;
      }
    }

    if (status.sms && modeSelect && status.sms.gateway_mode) {
      modeSelect.value = status.sms.gateway_mode;
    }
  } catch (err) {
    console.warn('Failed to load gateway status:', err);
  }
}

async function saveGatewayCredentials() {
  const user = document.getElementById('gw-smtp-user').value.trim();
  const pass = document.getElementById('gw-smtp-pass').value.trim();
  const recipient = document.getElementById('gw-recipient-email').value.trim();
  const mode = document.getElementById('gw-sms-mode').value;
  const feedback = document.getElementById('gw-feedback-box');

  const form = new FormData();
  if (user) form.append('smtp_user', user);
  if (pass) form.append('smtp_password', pass);
  if (recipient) form.append('alert_recipient_email', recipient);
  if (mode) form.append('sms_gateway', mode);

  try {
    const res = await fetch('/api/phone-call/configure-alerts', { method: 'POST', body: form });
    const data = await res.json();
    if (res.ok) {
      showGatewayFeedback(feedback, '✅ Gateway settings successfully saved & applied to VoiceShield AI!', '#10B981', 'rgba(16, 185, 129, 0.1)');
      fetchGatewayStatus();
    } else {
      showGatewayFeedback(feedback, `❌ Error: ${data.detail || 'Failed to save'}`, '#EF4444', 'rgba(239, 68, 68, 0.1)');
    }
  } catch (e) {
    showGatewayFeedback(feedback, `❌ Connection error: ${e.message}`, '#EF4444', 'rgba(239, 68, 68, 0.1)');
  }
}

async function testLiveEmailDispatch() {
  const recipient = document.getElementById('gw-recipient-email').value.trim();
  const feedback = document.getElementById('gw-feedback-box');

  showGatewayFeedback(feedback, '⏳ Connecting to SMTP server and transmitting live test email...', '#38BDF8', 'rgba(56, 189, 248, 0.1)');

  try {
    const form = new FormData();
    if (recipient) form.append('test_recipient', recipient);

    const res = await fetch('/api/phone-call/test-live-email', { method: 'POST', body: form });
    const data = await res.json();

    if (data.success) {
      showGatewayFeedback(feedback, `✅ Real Email Delivered! Test message successfully sent to: ${data.recipient} via ${data.smtp_server}. Check your inbox!`, '#10B981', 'rgba(16, 185, 129, 0.15)');
    } else if (data.status === 'CONFIG_REQUIRED') {
      showGatewayFeedback(feedback, `🟡 Setup Required: ${data.error || 'Please enter your Gmail and 16-character App Password above.'}`, '#F59E0B', 'rgba(245, 158, 11, 0.15)');
    } else {
      showGatewayFeedback(feedback, `❌ SMTP Error: ${data.error || 'Authentication/connection failure. Check your Gmail App Password.'}`, '#EF4444', 'rgba(239, 68, 68, 0.15)');
    }
  } catch (e) {
    showGatewayFeedback(feedback, `❌ Network error testing email: ${e.message}`, '#EF4444', 'rgba(239, 68, 68, 0.15)');
  }
}

async function testLiveSmsDispatch() {
  const phone = document.getElementById('phone-user-num').value.trim();
  const feedback = document.getElementById('gw-feedback-box');

  showGatewayFeedback(feedback, '⏳ Triggering real SMS dispatch test...', '#38BDF8', 'rgba(56, 189, 248, 0.1)');

  try {
    const form = new FormData();
    if (phone) form.append('test_recipient', phone);

    const res = await fetch('/api/phone-call/test-live-sms', { method: 'POST', body: form });
    const data = await res.json();

    if (data.channel === 'ANDROID_SIM_CARRIER') {
      showGatewayFeedback(
        feedback,
        `📱 Android SIM Mode Active: Formatted real GSM-7 precaution alert for ${data.recipient}. On your phone, VoiceShield AI sends this directly via your device carrier plan!`,
        '#10B981',
        'rgba(16, 185, 129, 0.15)'
      );
    } else if (data.success) {
      showGatewayFeedback(feedback, `✅ Real SMS Dispatched via ${data.channel} to ${data.recipient}!`, '#10B981', 'rgba(16, 185, 129, 0.15)');
    } else {
      showGatewayFeedback(feedback, `🟡 SMS Notice: ${data.error || 'Check chosen SMS gateway configuration.'}`, '#F59E0B', 'rgba(245, 158, 11, 0.15)');
    }
  } catch (e) {
    showGatewayFeedback(feedback, `❌ Error testing SMS: ${e.message}`, '#EF4444', 'rgba(239, 68, 68, 0.15)');
  }
}

function showGatewayFeedback(box, msg, color, bg) {
  if (!box) return;
  box.style.display = 'block';
  box.style.color = color;
  box.style.background = bg;
  box.style.border = `1px solid ${color}`;
  box.innerHTML = msg;
}

/* ==========================================================================
   DEEP FORENSIC ACTIVITY & AUDIT TRAIL LOGIC
   ========================================================================== */
const BROWSER_CACHE_KEY = 'voiceshield_audit_history_cache_v1';
let currentHistoryData = [];
let currentHistoryFilter = 'ALL';
let historySearchQuery = '';

function getBrowserCachedHistory() {
  try {
    const raw = localStorage.getItem(BROWSER_CACHE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    return [];
  }
}

function saveBrowserCachedHistory(list) {
  try {
    localStorage.setItem(BROWSER_CACHE_KEY, JSON.stringify(list));
  } catch (e) {
    console.warn('[Cache] LocalStorage save error:', e);
  }
}

function saveAnalysisResultToChromeCache(data, fileName) {
  try {
    const risk = data.risk_assessment || {};
    const fusion = data.ensemble_fusion || {};
    const fraud = data.semantic_fraud_detector || {};
    const vm = data.voicemod_forensics || {};
    const claimedSpeaker = document.getElementById('claimed-speaker')?.value?.trim() || 'None';
    
    const incidentId = 'AUD-' + Math.random().toString(16).substring(2, 10).toUpperCase();
    const now = new Date();
    const timestamp = now.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }) + 
                      ', ' + now.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) + ' UTC';

    const pClass = fusion.predicted_class || risk.predicted_class || 'ANALYZED';
    const riskPct = parseFloat(risk.risk_percentage || 0);

    const newRecord = {
      incident_id: incidentId,
      session_id: 'CHROME-SESSION-' + Math.random().toString(16).substring(2, 8).toUpperCase(),
      timestamp: timestamp,
      iso_timestamp: now.toISOString(),
      source: 'CHROME_BROWSER_CACHE',
      event_type: 'AUDIO_FORENSIC_ANALYSIS',
      caller_or_file: fileName || 'uploaded_voice_recording.wav',
      claimed_identity: claimedSpeaker,
      verdict: pClass,
      risk_percentage: riskPct,
      risk_level: risk.risk_level || 'LOW',
      threats_detected: risk.threats_detected || [],
      action_taken: riskPct >= 65 ? 'THREAT_FLIGHT_BLOCKED' : 'VERIFIED_SAFE',
      deep_forensics: {
        acoustic_vectors: data.forensic_metrics || {},
        conformer: data.neural_detector || {},
        ensemble_fusion: fusion,
        voicemod: vm,
        semantic_scam: fraud,
        speaker_biometrics: data.speaker_verification || {},
        glottal_lpc: data.glottal_biometrics || {},
        phase_mgd: data.spectral_phase_coherence || {}
      },
      compliance: {
        sha256_fingerprint: data.compliance_audit?.audio_sha256 || 'Ephemeral-Client-Hashed',
        privacy_standard: 'India DPDP Act 2023 (Zero-Retention Ephemeral RAM)'
      }
    };

    let cached = getBrowserCachedHistory();
    cached.unshift(newRecord);
    if (cached.length > 250) cached = cached.slice(0, 250);
    saveBrowserCachedHistory(cached);
    currentHistoryData = cached;
    updateHistoryStatsFromData(currentHistoryData);
  } catch (err) {
    console.warn('[Cache] Could not save analysis to Chrome cache:', err);
  }
}

function updateHistoryStatsFromData(list) {
  const total = list.length;
  const blocked = list.filter(i => (parseFloat(i.risk_percentage) || 0) >= 50 || (i.verdict || '').includes('ATTACK') || (i.verdict || '').includes('DROPPED')).length;
  const calls = list.filter(i => i.event_type === 'PHONE_CALL_DEFENSE' || i.event_type === 'CALL_SCREENING_INTERCEPT').length;
  const alerts = list.filter(i => i.alerts && (i.alerts.sms || i.alerts.email)).length;

  const totalEl = document.getElementById('hstat-total');
  const blockedEl = document.getElementById('hstat-blocked');
  const callsEl = document.getElementById('hstat-calls');
  const alertsEl = document.getElementById('hstat-alerts');
  const badgeCountEl = document.getElementById('history-badge-count');

  if (totalEl) totalEl.textContent = total;
  if (blockedEl) blockedEl.textContent = blocked;
  if (callsEl) callsEl.textContent = calls;
  if (alertsEl) alertsEl.textContent = alerts;
  if (badgeCountEl) badgeCountEl.textContent = total;
}

async function loadHistoryData(forceRefresh = false) {
  // 1. Instantly load and render from Chrome browser local storage cache
  const cached = getBrowserCachedHistory();
  if (cached && cached.length > 0) {
    currentHistoryData = cached;
    updateHistoryStatsFromData(currentHistoryData);
    renderHistoryTable();
  }

  // 2. Non-blocking background sync with backend
  try {
    const res = await fetch('/api/history?limit=25');
    if (res.ok) {
      const data = await res.json();
      const serverHistory = data.history || [];
      if (serverHistory.length > 0) {
        const existingIds = new Set(currentHistoryData.map(item => item.incident_id));
        let merged = [...currentHistoryData];
        for (const sItem of serverHistory) {
          if (!existingIds.has(sItem.incident_id)) {
            merged.push(sItem);
            existingIds.add(sItem.incident_id);
          }
        }
        if (merged.length > 250) merged = merged.slice(0, 250);
        currentHistoryData = merged;
        saveBrowserCachedHistory(currentHistoryData);
        updateHistoryStatsFromData(currentHistoryData);
        renderHistoryTable();
      }
    }
  } catch (err) {
    console.log('[History] Background sync skipped (using Chrome cache):', err.message);
  }

  if (currentHistoryData.length === 0) {
    updateHistoryStatsFromData([]);
    renderHistoryTable();
  }
}

function setHistoryFilter(filterType, ev) {
  currentHistoryFilter = filterType;
  document.querySelectorAll('.hfilter-btn').forEach(btn => btn.classList.remove('active'));
  if (ev && ev.target) {
    ev.target.classList.add('active');
  }
  renderHistoryTable();
}

function handleHistorySearch(query) {
  historySearchQuery = (query || '').trim().toLowerCase();
  renderHistoryTable();
}

function scrollToHistory() {
  const el = document.getElementById('history-section');
  if (el) {
    el.scrollIntoView({ behavior: 'smooth' });
  }
}

function renderHistoryTable() {
  const tbody = document.getElementById('history-table-body');
  if (!tbody) return;

  let filtered = currentHistoryData;

  // 1. Filter by category
  if (currentHistoryFilter !== 'ALL') {
    filtered = filtered.filter(item => (item.event_type || '').toUpperCase() === currentHistoryFilter.toUpperCase());
  }

  // 2. Filter by search query
  if (historySearchQuery) {
    filtered = filtered.filter(item => {
      const q = historySearchQuery;
      return (
        (item.incident_id || '').toLowerCase().includes(q) ||
        (item.caller_or_file || '').toLowerCase().includes(q) ||
        (item.claimed_identity || '').toLowerCase().includes(q) ||
        (item.verdict || '').toLowerCase().includes(q) ||
        (item.action_taken || '').toLowerCase().includes(q) ||
        (item.threats_detected || []).join(' ').toLowerCase().includes(q)
      );
    });
  }

  if (filtered.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7" style="text-align: center; padding: 2.5rem; color: #94A3B8;">
          <div style="font-size: 1.5rem; margin-bottom: 0.5rem;">🔍</div>
          No activity records found matching the active filter or search query.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = filtered.map(item => {
    const risk = parseFloat(item.risk_percentage || 0);
    let riskBadgeClass = 'verdict-safe';
    let riskColor = '#10B981';
    if (risk >= 75) {
      riskBadgeClass = 'verdict-critical';
      riskColor = '#EF4444';
    } else if (risk >= 40) {
      riskBadgeClass = 'verdict-warning';
      riskColor = '#F59E0B';
    }

    // Source Icon & Label
    const sourceIcon = item.source === 'ANDROID_MOBILE' ? '📱 Mobile SIM' : (item.source === 'CHROME_EXTENSION' ? '🧩 Extension' : '💻 Web Dashboard');
    
    // Event Type Icon
    let eventIcon = '🔬';
    let eventLabel = item.event_type || 'Event';
    if (item.event_type === 'PHONE_CALL_DEFENSE') {
      eventIcon = '📞';
      eventLabel = 'In-Call Defense';
    } else if (item.event_type === 'CALL_SCREENING_INTERCEPT') {
      eventIcon = '🛡️';
      eventLabel = 'Pre-Call Screen';
    } else if (item.event_type === 'AUDIO_FORENSIC_ANALYSIS') {
      eventIcon = '🎙️';
      eventLabel = 'Audio Forensics';
    } else if (item.event_type === 'ALERT_DISPATCH') {
      eventIcon = '✉️';
      eventLabel = 'Alert Dispatch';
    }

    // Threats Preview
    const threatSnippet = (item.threats_detected && item.threats_detected.length > 0)
      ? item.threats_detected.slice(0, 2).join(', ')
      : (item.verdict || 'Standard Operation');

    return `
      <tr>
        <td>
          <div style="font-weight: 700; color: #38BDF8; font-family: var(--font-mono);">${escapeHtml(item.incident_id || 'INC-PENDING')}</div>
          <div style="font-size: 0.7rem; color: #64748B;">${escapeHtml(item.timestamp || '')}</div>
        </td>
        <td>
          <div style="display: flex; align-items: center; gap: 0.3rem; font-weight: 600; color: #F8FAFC;">
            <span>${eventIcon}</span> <span>${eventLabel}</span>
          </div>
          <div style="font-size: 0.68rem; color: #94A3B8;">${sourceIcon}</div>
        </td>
        <td>
          <div style="font-weight: 600; color: #F8FAFC; max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
            ${escapeHtml(item.caller_or_file || 'Unknown')}
          </div>
          <div style="font-size: 0.68rem; color: #94A3B8;">
            Claim: <em>${escapeHtml(item.claimed_identity || 'None')}</em>
          </div>
        </td>
        <td>
          <span class="verdict-badge ${riskBadgeClass}">
            ${escapeHtml((item.verdict || 'ANALYZED').replace(/_/g, ' '))}
          </span>
          <div style="font-size: 0.68rem; color: #94A3B8; margin-top: 0.2rem; max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
            ${escapeHtml(threatSnippet)}
          </div>
        </td>
        <td>
          <div style="display: flex; align-items: center; gap: 0.5rem;">
            <strong style="color: ${riskColor}; font-family: var(--font-mono); min-width: 42px;">${risk.toFixed(1)}%</strong>
            <div style="width: 50px; height: 6px; background: #1E293B; border-radius: 3px; overflow: hidden;">
              <div style="width: ${Math.min(100, risk)}%; height: 100%; background: ${riskColor};"></div>
            </div>
          </div>
        </td>
        <td>
          <span style="font-size: 0.72rem; color: #E2E8F0;">
            ${escapeHtml((item.action_taken || 'LOGGED').replace(/_/g, ' '))}
          </span>
        </td>
        <td style="text-align: right;">
          <button class="btn btn-sm btn-outline" style="font-size: 0.72rem; padding: 0.25rem 0.6rem; border-color: #38BDF8; color: #38BDF8;" onclick="openHistoryDetail('${escapeHtml(item.incident_id)}')">
            🔍 Inspect
          </button>
        </td>
      </tr>
    `;
  }).join('');
}

async function openHistoryDetail(incidentId) {
  const modal = document.getElementById('history-detail-modal');
  const body = document.getElementById('hdetail-modal-body');
  const title = document.getElementById('hdetail-title');
  const subtitle = document.getElementById('hdetail-subtitle');

  if (!modal || !body) return;
  modal.style.display = 'flex';
  body.innerHTML = '<div style="text-align:center; padding:3rem; color:#94A3B8;"><div class="loading-spinner"></div> Loading deep forensic profile...</div>';

  try {
    let incident = currentHistoryData.find(i => i.incident_id === incidentId);
    if (!incident) {
      const res = await fetch(`/api/history/${incidentId}`);
      if (!res.ok) throw new Error(`Incident ${incidentId} not found`);
      incident = await res.json();
    }

    title.textContent = `Deep Forensic Profile: ${incident.incident_id}`;
    subtitle.textContent = `${incident.event_type} • ${incident.timestamp} • Source: ${incident.source}`;

    const df = incident.deep_forensics || {};
    const ac = df.acoustic_vectors || {};
    const conf = df.conformer || {};
    const fusion = df.ensemble_fusion || {};
    const vm = df.voicemod || {};
    const scam = df.semantic_scam || {};
    const spk = df.speaker_biometrics || {};
    const glottal = df.glottal_lpc || {};
    const phase = df.phase_mgd || {};
    const alerts = incident.alerts || {};

    const risk = parseFloat(incident.risk_percentage || 0);
    const riskColor = risk >= 75 ? '#EF4444' : (risk >= 40 ? '#F59E0B' : '#10B981');

    body.innerHTML = `
      <!-- Incident Overview Banner -->
      <div style="background: rgba(15, 23, 42, 0.9); border: 1px solid #1E293B; border-radius: 8px; padding: 1rem; margin-bottom: 1.2rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
        <div>
          <div style="font-size: 0.75rem; color: #94A3B8; text-transform: uppercase;">Overall Forensic Verdict</div>
          <div style="font-size: 1.2rem; font-weight: 800; color: ${riskColor}; margin-top: 0.2rem;">
            ${escapeHtml((incident.verdict || 'ANALYZED').replace(/_/g, ' '))}
          </div>
          <div style="font-size: 0.78rem; color: #E2E8F0; margin-top: 0.2rem;">
            Target / Caller: <strong>${escapeHtml(incident.caller_or_file || 'Unknown')}</strong> • Claimed: <em>${escapeHtml(incident.claimed_identity || 'None')}</em>
          </div>
        </div>
        <div style="text-align: right;">
          <div style="font-size: 0.75rem; color: #94A3B8; text-transform: uppercase;">Composite Threat Risk</div>
          <div style="font-size: 1.8rem; font-weight: 800; color: ${riskColor}; font-family: var(--font-mono);">
            ${risk.toFixed(1)}%
          </div>
        </div>
      </div>

      <!-- Deep Forensic Telemetry Grid -->
      <div class="telemetry-grid">
        <!-- 1. Acoustic Biometric Vectors -->
        <div class="telemetry-box">
          <h4>📊 7-Vector Acoustic Biometrics</h4>
          <table class="telemetry-table">
            <tr>
              <td>Spectral Centroid</td>
              <td>${ac.spectral_centroid_hz ? ac.spectral_centroid_hz.toFixed(1) + ' Hz' : '--'} <span class="baseline-diff ${ac.spectral_centroid_hz > 2200 ? 'diff-danger' : 'diff-ok'}">${ac.spectral_centroid_hz > 2200 ? 'Elevated' : 'Natural'}</span></td>
            </tr>
            <tr>
              <td>Spectral Rolloff</td>
              <td>${ac.spectral_rolloff_hz ? ac.spectral_rolloff_hz.toFixed(1) + ' Hz' : '--'}</td>
            </tr>
            <tr>
              <td>Pitch Mean (F0)</td>
              <td>${ac.pitch_mean_hz ? ac.pitch_mean_hz.toFixed(1) + ' Hz' : '--'}</td>
            </tr>
            <tr>
              <td>Pitch Stability (F0 Std)</td>
              <td>${ac.pitch_std_hz ? ac.pitch_std_hz.toFixed(1) + ' Hz' : '--'}</td>
            </tr>
            <tr>
              <td>Micro-Jitter %</td>
              <td>${ac.jitter_pct ? ac.jitter_pct.toFixed(2) + '%' : '--'} <span class="baseline-diff ${ac.jitter_pct > 2.0 ? 'diff-danger' : 'diff-ok'}">${ac.jitter_pct > 2.0 ? 'Synthetic' : 'Human'}</span></td>
            </tr>
            <tr>
              <td>Micro-Shimmer %</td>
              <td>${ac.shimmer_pct ? ac.shimmer_pct.toFixed(2) + '%' : '--'}</td>
            </tr>
            <tr>
              <td>Harmonics-to-Noise (HNR)</td>
              <td>${ac.hnr_db ? ac.hnr_db.toFixed(1) + ' dB' : '--'}</td>
            </tr>
            <tr>
              <td>Zero Crossing Rate</td>
              <td>${ac.zero_crossing_rate ? ac.zero_crossing_rate.toFixed(3) : '--'}</td>
            </tr>
          </table>
        </div>

        <!-- 2. AI Conformer & Ensemble Consensus -->
        <div class="telemetry-box">
          <h4>⚡ Neural Conformer & Ensemble</h4>
          <table class="telemetry-table">
            <tr>
              <td>Conformer Prediction</td>
              <td style="color: ${conf.predicted_class === 'VOICE_CLONING_ATTACK' ? '#EF4444' : '#10B981'};">${conf.predicted_class || '--'}</td>
            </tr>
            <tr>
              <td>Conformer Raw Probability</td>
              <td>${conf.raw_prob !== undefined ? (conf.raw_prob * 100).toFixed(1) + '%' : '--'}</td>
            </tr>
            <tr>
              <td>Entropy Uncertainty</td>
              <td>${conf.entropy !== undefined ? conf.entropy.toFixed(2) : '--'}</td>
            </tr>
            <tr>
              <td>Consensus Confidence</td>
              <td>${fusion.consensus_confidence_pct ? fusion.consensus_confidence_pct.toFixed(1) + '%' : '--'}</td>
            </tr>
            <tr>
              <td>Voicemod Voice Changer</td>
              <td style="color: ${vm.detected ? '#EF4444' : '#10B981'};">${vm.detected ? '🚨 DETECTED' : '🟢 None'}</td>
            </tr>
            <tr>
              <td>Comb Filter Ripple</td>
              <td>${vm.comb_ripple ? vm.comb_ripple.toFixed(3) : '0.000'}</td>
            </tr>
            <tr>
              <td>LPC Glottal Kurtosis</td>
              <td>${glottal.residual_kurtosis ? glottal.residual_kurtosis.toFixed(2) : '--'} (${glottal.status || 'NORMAL'})</td>
            </tr>
            <tr>
              <td>MGD Phase Jitter</td>
              <td>${phase.phase_jitter ? phase.phase_jitter.toFixed(3) : '--'} (${phase.status || 'COHERENT'})</td>
            </tr>
          </table>
        </div>

        <!-- 3. Semantic ALM & Social Engineering Intent -->
        <div class="telemetry-box" style="grid-column: span 2;">
          <h4>🧠 Semantic ALM & Social Engineering Telemetry</h4>
          <div style="background: rgba(0, 0, 0, 0.3); border: 1px solid #1E293B; border-radius: 6px; padding: 0.6rem; font-size: 0.76rem; color: #E2E8F0; font-style: italic; margin-bottom: 0.6rem;">
            "${escapeHtml(scam.transcript_snippet || df.transcript_snippet || 'No speech transcript recorded for this session.')}"
          </div>
          <table class="telemetry-table">
            <tr>
              <td>Scam Classification</td>
              <td style="color: #F59E0B;">${escapeHtml(scam.category || 'Standard Speech')}</td>
            </tr>
            <tr>
              <td>Coercion & Urgency Level</td>
              <td>${scam.coercion_urgency_pct ? scam.coercion_urgency_pct.toFixed(0) + '%' : '0%'}</td>
            </tr>
            <tr>
              <td>Flagged Threat Keywords</td>
              <td>
                ${(scam.flagged_keywords && scam.flagged_keywords.length > 0)
                  ? scam.flagged_keywords.map(k => `<span style="background:rgba(239,68,68,0.2); color:#F87171; padding:0.15rem 0.4rem; border-radius:4px; font-size:0.68rem; margin-right:0.25rem;">${escapeHtml(k)}</span>`).join('')
                  : '<span style="color:#94A3B8;">None</span>'}
              </td>
            </tr>
          </table>
        </div>

        <!-- 4. Enforcement & Alert Receipts -->
        <div class="telemetry-box" style="grid-column: span 2;">
          <h4>📱 Enforcement Action & Precaution Dispatches</h4>
          <table class="telemetry-table">
            <tr>
              <td>System Action Taken</td>
              <td><strong style="color: #38BDF8;">${escapeHtml((incident.action_taken || 'LOGGED').replace(/_/g, ' '))}</strong></td>
            </tr>
            <tr>
              <td>SMS Precaution Alert</td>
              <td>
                ${alerts.sms && alerts.sms.status
                  ? `<span style="color:#10B981;">✅ ${escapeHtml(alerts.sms.status)} via ${escapeHtml(alerts.sms.gateway || 'SMS Gateway')}</span> to <code>${escapeHtml(alerts.sms.recipient || 'User')}</code>`
                  : '<span style="color:#94A3B8;">No SMS dispatched</span>'}
              </td>
            </tr>
            <tr>
              <td>Security Advisory Email</td>
              <td>
                ${alerts.email && alerts.email.status
                  ? `<span style="color:#10B981;">✅ ${escapeHtml(alerts.email.status)}</span> to <code>${escapeHtml(alerts.email.recipient || 'User')}</code>`
                  : '<span style="color:#94A3B8;">No Email dispatched</span>'}
              </td>
            </tr>
            <tr>
              <td>DPDP Act 2023 Compliance</td>
              <td style="color: #10B981;">🔒 Zero-Retention Ephemeral RAM Certified</td>
            </tr>
            <tr>
              <td>Audio SHA-256 Digest</td>
              <td><code style="font-size:0.65rem; color:#94A3B8;">${escapeHtml(incident.compliance?.sha256_fingerprint || 'N/A')}</code></td>
            </tr>
          </table>
        </div>
      </div>
    `;
  } catch (err) {
    body.innerHTML = `<div style="padding:2rem; text-align:center; color:#EF4444;">Failed to load incident detail: ${escapeHtml(err.message)}</div>`;
  }
}

function closeHistoryDetailModal() {
  const modal = document.getElementById('history-detail-modal');
  if (modal) modal.style.display = 'none';
}

function exportHistoryFile() {
  if (!currentHistoryData || currentHistoryData.length === 0) {
    alert('No forensic history records in Chrome cache to export.');
    return;
  }
  const blob = new Blob([JSON.stringify(currentHistoryData, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `voiceshield_audit_trail_chrome_${new Date().toISOString().slice(0, 10)}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

async function confirmClearHistory() {
  if (!confirm('Are you sure you want to clear your local forensic history logs from Chrome cache? This cannot be undone.')) {
    return;
  }
  try {
    localStorage.removeItem(BROWSER_CACHE_KEY);
    currentHistoryData = [];
    updateHistoryStatsFromData([]);
    renderHistoryTable();

    fetch('/api/history/clear', { method: 'DELETE' }).catch(() => {});
    alert('✅ Forensic audit history cleared from Chrome cache.');
  } catch (err) {
    alert(`Error clearing history: ${err.message}`);
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
