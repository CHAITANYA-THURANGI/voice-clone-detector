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

      const tagClass = sample.type === 'REAL' ? 'tag-real' : 'tag-fake';
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
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Analysis request failed');
    }

    const data = await res.json();
    renderAnalysisResults(data);
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

  updateRiskDisplay(risk.risk_level, risk.risk_percentage, risk.summary, plan);

  // Neural Model Card
  document.getElementById('val-neural-prob').textContent = `${(neural.fake_probability * 100).toFixed(1)}%`;
  document.getElementById('prog-neural').style.width = `${neural.fake_probability * 100}%`;
  document.getElementById('prog-neural').style.backgroundColor = neural.prediction === 'FAKE' ? '#EF4444' : '#10B981';
  document.getElementById('val-neural-pred').textContent = `Prediction: ${neural.prediction} (${neural.confidence}% Conf)`;

  // Glottal Biometrics Card
  const glottal = data.glottal_biometrics || {};
  const glottalScore = glottal.glottal_anomaly_score || 0.0;
  document.getElementById('val-glottal-score').textContent = `${(glottalScore * 100).toFixed(1)}%`;
  document.getElementById('val-glottal-score').style.color = glottalScore > 0.4 ? '#EF4444' : '#10B981';
  document.getElementById('val-kurtosis').textContent = glottal.residual_kurtosis || '--';
  document.getElementById('val-glottal-status').textContent = glottal.glottal_status ? (glottalScore < 0.4 ? 'Natural Impulse' : 'Synthetic Vocal Tract') : '--';
  document.getElementById('val-glottal-status').style.color = glottalScore > 0.4 ? '#EF4444' : '#10B981';

  // Draw Glottal Residual Pulse Scope
  if (glottal.waveform_preview && glottal.waveform_preview.length > 0) {
    drawGlottalResidual(glottal.waveform_preview);
  }

  // Phase Forensics Card
  const phase = data.phase_forensics || {};
  const phaseScore = phase.phase_incoherence_score || 0.0;
  document.getElementById('val-phase-score').textContent = `${(phaseScore * 100).toFixed(1)}%`;
  document.getElementById('val-phase-score').style.color = phaseScore > 0.4 ? '#EF4444' : '#10B981';
  document.getElementById('val-phase-jitter').textContent = phase.high_freq_phase_jitter || '--';
  document.getElementById('val-phase-status').textContent = phase.status ? (phaseScore < 0.4 ? 'Continuous Phase' : 'Vocoder Phase Jitter') : '--';
  document.getElementById('val-phase-status').style.color = phaseScore > 0.4 ? '#EF4444' : '#10B981';

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
    document.getElementById('val-foundation-prob').style.color = foundProb > 0.4 ? '#EF4444' : '#10B981';
    document.getElementById('val-foundation-stability').textContent = `${found.foundation_stability || '--'} m/s²`;
    document.getElementById('val-foundation-verdict').textContent = found.prediction === 'FAKE' ? 'Synthetic Dispersion' : 'Biological Dynamics';
    document.getElementById('val-foundation-verdict').style.color = found.prediction === 'FAKE' ? '#EF4444' : '#10B981';
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

function updateRiskDisplay(level, percentage, summary, plan) {
  const banner = document.getElementById('risk-banner');
  const badge = document.getElementById('risk-badge');
  const score = document.getElementById('risk-score-display');
  const sumText = document.getElementById('risk-summary');

  banner.className = `risk-banner risk-${level.toLowerCase()}`;
  score.textContent = `${percentage}% RISK`;
  sumText.textContent = summary;

  if (level === 'LOW') {
    badge.textContent = '🟢 LOW RISK (AUTHENTIC)';
  } else if (level === 'SUSPICIOUS') {
    badge.textContent = '🟡 SUSPICIOUS (VERIFICATION REQUIRED)';
  } else {
    badge.textContent = '🔴 HIGH RISK (SYNTHETIC ATTACK)';
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

