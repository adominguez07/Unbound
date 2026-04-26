'use strict';

// ─── Metadata ────────────────────────────────────────────────────────────────

const GESTURES = {
  wink_left:     'Left Wink',
  wink_right:    'Right Wink',
  mouth_open:    'Mouth Open',
  smile:         'Smile',
  pucker:        'Pucker / Kiss',
  eyebrow_raise: 'Eyebrow Raise',
};

const ACTIONS = {
  none:            'None (disabled)',
  left_click:      'Left Click',
  right_click:     'Right Click',
  double_click:    'Double Click',
  scroll_up:       'Scroll Up (hold)',
  scroll_down:     'Scroll Down (hold)',
  drag_toggle:     'Drag Toggle',
  open_osk:        'Open / Close On-Screen Keyboard',
  pause_tracking:  'Pause / Resume Tracking',
};

// The blendshape MediaPipe key most relevant to each gesture (for bar highlighting)
const GESTURE_BLENDSHAPES = {
  wink_left:     ['eyeBlinkLeft'],
  wink_right:    ['eyeBlinkRight'],
  mouth_open:    ['jawOpen'],
  smile:         ['mouthSmileLeft', 'mouthSmileRight'],
  pucker:        ['mouthPucker'],
  eyebrow_raise: ['browInnerUp'],
};

// Blendshape names shown in the live bars section
const TRACKED_BLENDSHAPES = [
  'eyeBlinkLeft', 'eyeBlinkRight',
  'jawOpen',
  'mouthSmileLeft', 'mouthSmileRight',
  'mouthPucker',
  'browInnerUp',
  'browOuterUpLeft', 'browOuterUpRight',
  'mouthFrownLeft', 'mouthFrownRight',
];

// ─── State ────────────────────────────────────────────────────────────────────

let currentSettings = {};
let saveTimer = null;
let isPaused = false;

// ─── Boot ─────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
  buildGestureBindings();
  buildGestureThresholds();
  buildGestureCalibButtons();
  buildBlendshapeBars();

  await loadSettings();
  wireInputs();
  wireButtons();
  startBlendshapePolling();
  startStatusPolling();
});

// ─── Build UI ─────────────────────────────────────────────────────────────────

function buildGestureBindings() {
  const container = document.getElementById('gesture-bindings');
  for (const [key, label] of Object.entries(GESTURES)) {
    const row = document.createElement('div');
    row.className = 'gesture-row';

    const name = document.createElement('span');
    name.className = 'gesture-label';
    name.textContent = label;

    const select = document.createElement('select');
    select.id = `binding-${key}`;
    for (const [val, text] of Object.entries(ACTIONS)) {
      const opt = document.createElement('option');
      opt.value = val;
      opt.textContent = text;
      select.appendChild(opt);
    }

    row.appendChild(name);
    row.appendChild(select);
    container.appendChild(row);
  }
}

function buildGestureThresholds() {
  const container = document.getElementById('gesture-thresholds');
  for (const [key, label] of Object.entries(GESTURES)) {
    const row = document.createElement('div');
    row.className = 'threshold-row';

    row.innerHTML = `
      <label>${label}</label>
      <input type="range" id="trig-${key}" min="0.05" max="0.99" step="0.01">
      <span class="val" id="trig-${key}-val"></span>
      <input type="range" id="rel-${key}"  min="0.01" max="0.95" step="0.01">
      <span class="val" id="rel-${key}-val"></span>
    `;
    container.appendChild(row);
  }
}

function buildGestureCalibButtons() {
  const container = document.getElementById('gesture-calib-buttons');
  for (const [key, label] of Object.entries(GESTURES)) {
    const btn = document.createElement('button');
    btn.className = 'btn btn-secondary';
    btn.id = `btn-calib-${key}`;
    btn.textContent = label;
    btn.addEventListener('click', () => runGestureCalibration(key, label));
    container.appendChild(btn);
  }
}

function buildBlendshapeBars() {
  const container = document.getElementById('blendshape-bars');
  for (const name of TRACKED_BLENDSHAPES) {
    const row = document.createElement('div');
    row.className = 'bs-row';
    row.innerHTML = `
      <span class="bs-name">${name}</span>
      <div class="bs-track"><div class="bs-fill" id="bs-${name}" style="width:0%"></div></div>
      <span class="bs-score" id="bs-score-${name}">0.00</span>
    `;
    container.appendChild(row);
  }
}

// ─── Settings load / save ─────────────────────────────────────────────────────

async function loadSettings() {
  try {
    const res = await fetch('/api/settings');
    currentSettings = await res.json();
    populateForm(currentSettings);
  } catch (e) {
    showSaveStatus('Could not load settings.', 'error');
  }
}

function populateForm(s) {
  setField('camera-index',      s.camera_index);
  setField('movement-mode',     s.movement_mode);
  setSlider('sensitivity',      s.sensitivity);
  setSlider('smoothing-alpha',  s.smoothing_alpha);
  setSlider('deadzone-radius',  s.deadzone_radius);
  setSlider('acceleration-expo',s.acceleration_expo);
  setSlider('hold-duration',    s.hold_duration_ms);
  setChecked('failsafe-enabled', s.failsafe_enabled);

  if (s.gesture_bindings) {
    for (const [key, action] of Object.entries(s.gesture_bindings)) {
      setField(`binding-${key}`, action);
    }
  }

  if (s.gesture_thresholds) {
    for (const [key, t] of Object.entries(s.gesture_thresholds)) {
      setSlider(`trig-${key}`, t.trigger);
      setSlider(`rel-${key}`,  t.release);
    }
  }
}

function collectForm() {
  const bindings = {};
  const thresholds = {};
  for (const key of Object.keys(GESTURES)) {
    const sel = document.getElementById(`binding-${key}`);
    if (sel) bindings[key] = sel.value;

    const trig = document.getElementById(`trig-${key}`);
    const rel  = document.getElementById(`rel-${key}`);
    if (trig && rel) {
      thresholds[key] = {
        trigger: parseFloat(trig.value),
        release: parseFloat(rel.value),
      };
    }
  }

  return {
    camera_index:      parseInt(document.getElementById('camera-index').value),
    movement_mode:     document.getElementById('movement-mode').value,
    sensitivity:       parseFloat(document.getElementById('sensitivity').value),
    smoothing_alpha:   parseFloat(document.getElementById('smoothing-alpha').value),
    deadzone_radius:   parseFloat(document.getElementById('deadzone-radius').value),
    acceleration_expo: parseFloat(document.getElementById('acceleration-expo').value),
    hold_duration_ms:  parseInt(document.getElementById('hold-duration').value),
    failsafe_enabled:  document.getElementById('failsafe-enabled').checked,
    gesture_bindings:  bindings,
    gesture_thresholds: thresholds,
  };
}

async function saveSettings() {
  showSaveStatus('Saving...', 'saving');
  try {
    const patch = collectForm();
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    });
    if (!res.ok) {
      const err = await res.json();
      showSaveStatus(`Error: ${err.detail}`, 'error');
    } else {
      currentSettings = patch;
      showSaveStatus('Saved', 'saved');
      setTimeout(() => showSaveStatus('', ''), 3000);
    }
  } catch (e) {
    showSaveStatus('Save failed.', 'error');
  }
}

// ─── Wire inputs ──────────────────────────────────────────────────────────────

function wireInputs() {
  // Sliders: update value display live; debounce save
  document.querySelectorAll('input[type="range"]').forEach(el => {
    updateSliderDisplay(el);
    el.addEventListener('input', () => {
      updateSliderDisplay(el);
      scheduleSave();
    });
  });

  // Other inputs: debounce save on change
  document.querySelectorAll('input[type="number"], select, input[type="checkbox"]')
    .forEach(el => el.addEventListener('change', scheduleSave));
}

function scheduleSave() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(saveSettings, 1500);
}

// ─── Wire buttons ─────────────────────────────────────────────────────────────

function wireButtons() {
  document.getElementById('btn-save').addEventListener('click', saveSettings);

  document.getElementById('btn-pause-resume').addEventListener('click', async () => {
    const endpoint = isPaused ? '/api/resume' : '/api/pause';
    await fetch(endpoint, { method: 'POST' });
  });

  document.getElementById('btn-calib-neutral').addEventListener('click', runNeutralCalibration);

  document.getElementById('btn-reset').addEventListener('click', async () => {
    if (!confirm('Reset all settings to defaults? This cannot be undone.')) return;
    await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ __reset: true }),
    });
    await loadSettings();
  });

  document.getElementById('btn-speech-toggle').addEventListener('click', toggleSpeech);

  document.getElementById('btn-quit').addEventListener('click', async () => {
    if (!confirm('Quit Unbound?')) return;
    await fetch('/api/quit', { method: 'POST' });
    window.close();
  });
}

// ─── Calibration ──────────────────────────────────────────────────────────────

async function runNeutralCalibration() {
  const btn = document.getElementById('btn-calib-neutral');
  setAllCalibButtons(true);
  showCalibStatus('Hold your face still and relaxed... (3 s)', 'running');
  try {
    const res = await fetch('/api/calibrate/neutral', { method: 'POST' });
    if (res.ok) {
      showCalibStatus('Neutral calibration complete.', 'success');
    } else {
      const err = await res.json();
      showCalibStatus(`Failed: ${err.detail}`, 'error');
    }
  } catch (e) {
    showCalibStatus('Request failed.', 'error');
  } finally {
    setAllCalibButtons(false);
    setTimeout(() => hideCalibStatus(), 4000);
  }
}

async function runGestureCalibration(key, label) {
  setAllCalibButtons(true);
  showCalibStatus(`Perform "${label}" clearly for 2 seconds...`, 'running');
  try {
    const res = await fetch(`/api/calibrate/gesture/${key}`, { method: 'POST' });
    if (res.ok) {
      const data = await res.json();
      const { trigger, release } = data.thresholds;
      setSlider(`trig-${key}`, trigger);
      setSlider(`rel-${key}`,  release);
      showCalibStatus(`${label} calibrated — trigger: ${trigger.toFixed(3)}, release: ${release.toFixed(3)}`, 'success');
      scheduleSave();
    } else {
      const err = await res.json();
      showCalibStatus(`Failed: ${err.detail}`, 'error');
    }
  } catch (e) {
    showCalibStatus('Request failed.', 'error');
  } finally {
    setAllCalibButtons(false);
    setTimeout(() => hideCalibStatus(), 5000);
  }
}

function setAllCalibButtons(disabled) {
  document.getElementById('btn-calib-neutral').disabled = disabled;
  for (const key of Object.keys(GESTURES)) {
    const btn = document.getElementById(`btn-calib-${key}`);
    if (btn) btn.disabled = disabled;
  }
}

function showCalibStatus(msg, type) {
  const el = document.getElementById('calib-status');
  el.textContent = msg;
  el.className = `calib-status ${type}`;
}

function hideCalibStatus() {
  const el = document.getElementById('calib-status');
  el.className = 'calib-status hidden';
}

// ─── Blendshape polling ───────────────────────────────────────────────────────

function startBlendshapePolling() {
  setInterval(async () => {
    try {
      const res = await fetch('/api/blendshapes');
      const data = await res.json();
      updateBars(data);
    } catch (_) {}
  }, 120);
}

function updateBars(data) {
  for (const name of TRACKED_BLENDSHAPES) {
    const score = data[name] ?? 0;
    const fill  = document.getElementById(`bs-${name}`);
    const label = document.getElementById(`bs-score-${name}`);
    if (!fill) continue;

    fill.style.width = `${(score * 100).toFixed(1)}%`;
    label.textContent = score.toFixed(2);

    fill.className = 'bs-fill' + (score > 0.7 ? ' peak' : score > 0.4 ? ' high' : '');
  }
}

// ─── Status polling ───────────────────────────────────────────────────────────

function startStatusPolling() {
  setInterval(async () => {
    try {
      const res = await fetch('/api/status');
      const data = await res.json();
      applyStatus(data);
    } catch (_) {}
  }, 500);
}

function applyStatus(data) {
  applySpeechStatus(data.speech_active ?? false);
  isPaused = data.paused;
  const badge = document.getElementById('tracking-badge');
  const btn   = document.getElementById('btn-pause-resume');

  if (data.calibration_in_progress) {
    badge.textContent = 'Calibrating';
    badge.className = 'badge badge-calib';
    btn.disabled = true;
  } else if (data.paused) {
    badge.textContent = 'Paused';
    badge.className = 'badge badge-paused';
    btn.textContent = 'Resume';
    btn.disabled = false;
  } else {
    badge.textContent = 'Tracking';
    badge.className = 'badge badge-active';
    btn.textContent = 'Pause';
    btn.disabled = false;
  }
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function setField(id, value) {
  const el = document.getElementById(id);
  if (el && value !== undefined && value !== null) el.value = value;
}

function setChecked(id, value) {
  const el = document.getElementById(id);
  if (el) el.checked = !!value;
}

function setSlider(id, value) {
  const el = document.getElementById(id);
  if (el && value !== undefined && value !== null) {
    el.value = value;
    updateSliderDisplay(el);
  }
}

function updateSliderDisplay(el) {
  const valEl = document.getElementById(`${el.id}-val`);
  if (valEl) valEl.textContent = parseFloat(el.value).toFixed(
    el.step && parseFloat(el.step) >= 1 ? 0 : 2
  );
}

async function toggleSpeech() {
  const btn = document.getElementById('btn-speech-toggle');
  const badge = document.getElementById('speech-badge');
  const isActive = badge.classList.contains('badge-active');
  btn.disabled = true;
  try {
    const endpoint = isActive ? '/api/speech/stop' : '/api/speech/start';
    const res = await fetch(endpoint, { method: 'POST' });
    if (!res.ok) {
      const err = await res.json();
      alert(`Speech error: ${err.detail}`);
    }
  } finally {
    btn.disabled = false;
  }
}

function applySpeechStatus(active) {
  const btn = document.getElementById('btn-speech-toggle');
  const badge = document.getElementById('speech-badge');
  if (active) {
    btn.textContent = 'Disable Speech Mode';
    btn.className = 'btn btn-danger btn-wide';
    badge.textContent = 'Listening';
    badge.className = 'badge badge-active';
  } else {
    btn.textContent = 'Enable Speech Mode';
    btn.className = 'btn btn-primary btn-wide';
    badge.textContent = 'Off';
    badge.className = 'badge badge-paused';
  }
}

function showSaveStatus(msg, type) {
  const el = document.getElementById('save-status');
  el.textContent = msg;
  el.className = `save-status ${type}`;
}
