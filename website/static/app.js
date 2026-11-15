// Healthy Astronauts website: talks to server.py. Rules decide statuses; the local model reads, explains and answers.
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const state = { crew: 'mo', today: null, trends: null, labels: {}, found: {}, manual: new Set(), aiKeys: new Set(),
                photoText: null, region: 'General', lastRead: '', timer: null, run: 0, group: 'all' };
const SITE_KEYS = { brain: ['sleep'], eyes: ['trt250_left', 'trt250_right'], heart: ['pulse', 'systolic', 'diastolic'],
  labs: ['serum_sodium', 'serum_potassium', 'serum_creatinine', 'serum_glucose'], calf_left: ['calf_csa_left'], calf_right: ['calf_csa_right'] };
const SITE_NAMES = { brain: 'Brain · sleep', eyes: 'Eyes · optic nerve OCT', heart: 'Heart', labs: 'Blood labs', calf_left: 'Left calf', calf_right: 'Right calf' };
const QUESTIONS = { mental_fatigue: 'How mentally exhausted do you feel right now?', stress_now: 'How stressed do you feel right now?',
  workload_now: 'How demanding has your work felt today?', sleep_difficulty: 'How much difficulty did you have sleeping last night?',
  low_mood: 'How low or down have you felt today?', task_difficulty: 'How much have your symptoms affected your duties today?' };
const COLOURS = { sleep: '#a9bdff', pulse: '#ff8fb1', systolic: '#ffb26b', diastolic: '#ffd36b', serum_sodium: '#6fd6ff',
  serum_potassium: '#7af0c8', serum_creatinine: '#9be36b', serum_glucose: '#ff9f6b', calf_csa_left: '#c9a7ff', calf_csa_right: '#b48cff',
  trt250_left: '#7ad7f0', trt250_right: '#5fc2e8' };
const GROUP = k => ['sleep', 'pulse', 'systolic', 'diastolic'].includes(k) ? 'vital' : k.startsWith('serum') ? 'labs' : 'body';
// SI-generated animation clips (Codex), exported with a visible watermark.
const CLIPS = { nap: 4, water: 4, sit: 4, walk: 4, meditate: 2, 'measure-bp': 3, 'measure-pulse': 2, 'measure-sleep': 2, 'measure-labs': 3 };
const MEASURE_CLIP = k => ['systolic', 'diastolic'].includes(k) ? 'measure-bp' : k === 'pulse' ? 'measure-pulse' : k === 'sleep' ? 'measure-sleep' : k.startsWith('serum') ? 'measure-labs' : 'sit';
const HOWTO = {
  'measure-bp': ['Sit still for 5 minutes, feet flat, back supported.', 'Put the cuff on your bare upper arm at heart level.', 'Stay quiet during the reading, then record both numbers.'],
  'measure-pulse': ['Rest quietly for 5 minutes first.', 'Use the heart-rate monitor or count your pulse for 60 seconds.', 'Avoid measuring right after exercise or caffeine.'],
  'measure-sleep': ['Check the wrist tracker or sleep log for your main sleep period.', 'Do not count naps or time spent awake in bed.', 'Record the total hours slept.'],
  'measure-labs': ['Check the report row is the right test and the unit matches.', 'Use the measured value from the lab analyser.', 'Ask the medical officer if the sample was flagged.'],
  sit: ['Follow the onboard procedure for this measurement.', 'Compare the same side and the same scan site as before.', 'Record the value in the unit shown.'] };
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmt = v => { const n = +v; return Math.abs(n) >= 10 ? +n.toFixed(1) : +n.toFixed(2); };
const timers = new WeakMap();

function anim(name, cls = '') {
  const n = CLIPS[name] || 1;
  return `<div class="anim ${cls}" data-clip="${name}" data-n="${n}"><img src="/img/anim/${name}-0.jpg" alt="${name} animation (SI-generated)"></div>`;
}
function startAnims(root = document) {
  for (const el of $$('.anim[data-clip]', root)) {
    if (timers.has(el)) continue;
    const img = $('img', el), n = +el.dataset.n, name = el.dataset.clip; let i = 0;
    for (let k = 0; k < n; k++) { const p = new Image(); p.src = `/img/anim/${name}-${k}.jpg`; }
    timers.set(el, setInterval(() => { if (!document.body.contains(el)) return; i = (i + 1) % n; img.src = `/img/anim/${name}-${i}.jpg`; }, 650));
  }
}

async function api(path, body) {
  const res = await fetch(path, body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {});
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Request failed');
  return data;
}
async function stream(path, body, onText) {
  const res = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  if (!res.ok) { const d = await res.json().catch(() => ({})); throw new Error(d.error || 'Request failed'); }
  const reader = res.body.getReader(); const dec = new TextDecoder(); let text = '';
  for (;;) { const { value, done } = await reader.read(); if (done) break; text += dec.decode(value, { stream: true }); onText(text); }
  return text;
}

// ------------------------------------------------------------------ today
async function loadToday() {
  state.today = await api(`/api/today?crew=${state.crew}`);
  for (const t of state.today.tiles) state.labels[t.key] = [t.label, t.unit];
  renderBody(); renderTiles(); renderSticker(state.today.mood); renderQuizStatus(); renderCoach(); fillMetricSelect();
}
function renderBody() {
  for (const btn of $$('.site')) { btn.classList.remove('ok', 'watch', 'alert', 'none'); btn.classList.add(state.today.body[btn.dataset.site] || 'none'); }
}
function tileHTML(t) {
  const lo = Math.min(t.low, t.baseline, t.value ?? t.low), hi = Math.max(t.high, t.baseline, t.value ?? t.high);
  const span = (hi - lo) || 1, s = lo - span * .12, e = hi + span * .12, at = v => ((v - s) / (e - s) * 100).toFixed(1) + '%';
  const bandColour = t.kind === 'nasa' ? '#3f6fa8' : '#6b55a0';
  return `<div class="tile ${t.status}" data-key="${t.key}" title="${esc(t.source)}">
    <span class="badge ${t.kind}">${t.kind === 'nasa' ? 'NASA' : 'SIM'}</span>
    <div class="label">${esc(t.label)}</div>
    <div class="value">${t.value ?? '—'}<small>${t.value != null ? esc(t.unit) : ''}</small></div>
    <div class="bar"><span class="band" style="left:${at(t.low)};right:calc(100% - ${at(t.high)});background:${bandColour}"></span>
      <span class="base" style="left:${at(t.baseline)}"></span>${t.value != null ? `<span class="dot" style="left:${at(+t.value)}"></span>` : ''}</div>
    <div class="sum">${esc(t.summary)}</div><span class="off">⚠ Off baseline · tap to repeat</span></div>`;
}
function renderTiles() {
  const tiles = state.today.tiles, attn = tiles.filter(t => t.status === 'watch' || t.status === 'alert');
  const groups = [['⚠ Needs attention', attn, 'attn'], ['Vital signs', tiles.filter(t => GROUP(t.key) === 'vital')],
    ['Blood labs', tiles.filter(t => GROUP(t.key) === 'labs')], ['Muscle and eyes', tiles.filter(t => GROUP(t.key) === 'body')]];
  const shown = new Set(); let html = '';
  for (const [title, list, cls] of groups) {
    const rows = list.filter(t => !shown.has(t.key)); if (!rows.length) continue;
    rows.forEach(t => shown.add(t.key));
    html += `<h4 class="${cls || ''}">${title.toUpperCase()}</h4>` + rows.map(tileHTML).join('');
  }
  $('#tiles').innerHTML = html;
  $$('.tile').forEach(el => el.onclick = () => openTrend([el.dataset.key], state.labels[el.dataset.key][0]));
}
function face(kind) {
  const mouth = { happy: 'M18 34 Q27 43 36 34', up: 'M18 34 Q27 43 36 34', ok: 'M18 36 L36 36', down: 'M18 39 Q27 31 36 39', low: 'M18 39 Q27 31 36 39' }[kind];
  return `<svg viewBox="0 0 54 54"><circle cx="27" cy="27" r="24" fill="#fff7d6" stroke="#222" stroke-width="2"/><circle cx="19" cy="21" r="3" fill="#222"/><circle cx="35" cy="21" r="3" fill="#222"/><path d="${mouth}" stroke="#222" stroke-width="3" fill="none" stroke-linecap="round"/></svg>`;
}
function renderSticker(m) {
  $('#sticker').innerHTML = `<div class="sticker-inner" style="--sc:${m.colour}">${face(m.face)}<div><div class="kicker">${esc(m.kicker).toUpperCase()}</div>
    <div class="title">${esc(m.title)}</div><div class="detail">${esc(m.detail)}</div></div><div class="comment">${esc(m.comment)}</div></div>`;
}
function renderQuizStatus() {
  const t = state.today, done = t.questionnaire_today;
  $('#quiz-status').className = 'quiz-status ' + (done ? 'done' : 'todo');
  $('#quiz-status').innerHTML = done
    ? `<div class="ring">✓</div><div><b>Daily questionnaire done</b><span>Completed today · ${esc(t.wellbeing?.label || '')}</span></div>`
    : `<div class="ring">!</div><div><b>Daily questionnaire not done yet</b><span>${t.last_questionnaire ? 'Last one: ' + t.last_questionnaire : 'No questionnaire yet'}</span></div>
       <button class="btn primary" id="quiz-now">Start</button>`;
  const b = $('#quiz-now'); if (b) b.onclick = openQuiz;
}
function coachChoice() {
  const t = state.today, wb = t.wellbeing, mood = t.mood || {};
  const off = t.tiles.filter(x => (x.status === 'watch' || x.status === 'alert') && x.key !== 'sleep');
  const sleep = t.tiles.find(x => x.key === 'sleep');
  if ((wb && wb.scene === 'support') || ['Heavy orbit', 'Low on fuel'].includes(mood.title))
    return { clip: 'meditate', colour: '#cdb4ff', head: 'MIND · SELF-CARE', title: 'Take 10 minutes for your mind',
      text: 'Try a short meditation, slow breathing or your favourite music. Talking helps too: book a private session with the flight psychologist.', psy: true };
  if (sleep && sleep.value != null && (+sleep.value < 6 || sleep.status !== 'ok'))
    return { clip: 'nap', colour: '#a9bdff', head: 'SLEEP · RECOVER', title: 'Short on sleep: take a nap',
      text: `You slept ${sleep.value} h. When your schedule allows, a 20-minute nap helps. Tell the crew lead before safety-critical work if you feel too tired.` };
  if (off.length) {
    const k = off[0];
    return { clip: MEASURE_CLIP(k.key), colour: '#ff8a7a', head: 'REPEAT · MEASURE AGAIN', title: `Repeat ${k.label} correctly`,
      text: `${k.label} is outside its baseline. Follow the steps in the animation, then enter the new value.`, repeat: k.key, earth: true };
  }
  if (wb && wb.scene !== 'routine')
    return { clip: 'meditate', colour: '#cdb4ff', head: 'MIND · SELF-CARE', title: 'Make time for a short break',
      text: 'A few minutes of breathing, music or a chat with crewmates helps. If strain continues, book a private psychological conference.' };
  return { clip: 'walk', colour: '#a1e7cc', head: 'KEEP IT UP', title: 'All readings in range',
    text: 'Keep your exercise, water and sleep routine. Next check-in tomorrow.' };
}
function renderCoach() {
  const c = coachChoice();
  $('#coach').innerHTML = `<div class="head" style="background:${c.colour}">${c.head}</div><div class="body">${anim(c.clip)}<div>
    <h3>${esc(c.title)}</h3><p>${esc(c.text)}</p>
    ${c.repeat ? `<button class="btn primary" id="coach-repeat">Repeat now</button>` : ''}
    ${c.psy ? `<button class="btn" id="coach-psy">Book psychologist</button>` : ''}</div></div>
    ${c.earth ? `<div class="notice" style="margin:0 12px 12px"><span class="ico">📡</span><div>Your flight surgeon on Earth has been notified.<small>Simulated in this demo.</small></div></div>` : ''}
    ${c.psy ? `<div class="notice psy" style="margin:0 12px 12px"><span class="ico">🧠</span><div>Flight psychologist notified of your check-in.<small>Simulated in this demo.</small></div></div>` : ''}`;
  startAnims($('#coach'));
  const r = $('#coach-repeat'); if (r) r.onclick = () => openTrend([c.repeat], state.labels[c.repeat][0]);
  const p = $('#coach-psy'); if (p) p.onclick = () => { p.textContent = 'Request sent (demo) ✓'; p.disabled = true; };
}

// ------------------------------------------------------------------ trends (colourful)
function smooth(points) {
  if (points.length < 3) return 'M' + points.map(p => p.join(',')).join(' L');
  let d = `M${points[0][0]},${points[0][1]}`;
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[i - 1] || points[i], p1 = points[i], p2 = points[i + 1], p3 = points[i + 2] || p2;
    const c1 = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6], c2 = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
    d += ` C${c1[0].toFixed(1)},${c1[1].toFixed(1)} ${c2[0].toFixed(1)},${c2[1].toFixed(1)} ${p2[0].toFixed(1)},${p2[1].toFixed(1)}`;
  }
  return d;
}
function chartSVG(m, colour, id) {
  const pts = m.series, W = 640, H = 190, L = 10, R = 64, T = 14, B = 26;
  if (!pts.length) return `<svg viewBox="0 0 ${W} ${H}"><text x="${W / 2}" y="${H / 2}" fill="#a9c0ba" text-anchor="middle" font-size="15">No readings yet. Click to add one.</text></svg>`;
  const vals = pts.map(p => p[1]).concat([m.low, m.high, m.baseline]);
  let lo = Math.min(...vals), hi = Math.max(...vals); const pad = (hi - lo) * .1 || 1; lo -= pad; hi += pad;
  const y = v => T + (hi - v) / (hi - lo) * (H - T - B), x = i => L + (pts.length === 1 ? .5 : i / (pts.length - 1)) * (W - L - R);
  const P = pts.map((p, i) => [x(i), y(p[1])]), line = smooth(P);
  const area = `${line} L${P.at(-1)[0]},${H - B} L${P[0][0]},${H - B} Z`;
  const bandFill = m.band || (m.kind === 'nasa' ? '#2b5f9e' : '#6a4fb0'), word = m.kind === 'nasa' ? 'NASA' : 'SIM';
  const dots = pts.map((p, i) => { const inside = p[1] >= m.low && p[1] <= m.high, last = i === pts.length - 1;
    return `${!inside ? `<circle cx="${P[i][0]}" cy="${P[i][1]}" r="9" fill="#ff5f6d" opacity=".25"/>` : ''}
      <circle cx="${P[i][0]}" cy="${P[i][1]}" r="${last ? 6 : pts.length > 20 ? 3 : 4.5}" fill="${inside ? colour : '#ff5f6d'}" stroke="#0e2026" stroke-width="${last ? 2 : 1}"><title>${p[0]} · ${p[1]} ${m.unit}</title></circle>`; }).join('');
  const ticks = [0, Math.floor((pts.length - 1) / 2), pts.length - 1].filter((v, i, a) => a.indexOf(v) === i)
    .map(i => `<text x="${P[i][0]}" y="${H - 6}" fill="#8fa8a2" font-size="11" text-anchor="middle">${pts[i][0].slice(5)}</text>`).join('');
  const last = P.at(-1);
  return `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
    <defs><linearGradient id="g${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${colour}" stop-opacity=".45"/><stop offset="1" stop-color="${colour}" stop-opacity="0"/></linearGradient></defs>
    <rect x="${L}" y="${y(m.high)}" width="${W - L - R}" height="${y(m.low) - y(m.high)}" fill="${bandFill}" opacity=".28" rx="4"/>
    <text x="${L + 6}" y="${y(m.high) + 13}" fill="#cfe0ff" font-size="11" font-weight="700" opacity=".9">${m.bandLabel || word + ' RANGE'}</text>
    <line x1="${L}" x2="${W - R}" y1="${y(m.baseline)}" y2="${y(m.baseline)}" stroke="#f3f5ed" stroke-dasharray="7 5" stroke-width="1.3" opacity=".8"/>
    <text x="${W - 4}" y="${y(m.baseline) + 4}" fill="#f3f5ed" font-size="12" font-weight="700" text-anchor="end">${m.baseLabel || (word === 'NASA' ? 'NASA' : 'pre')} ${fmt(m.baseline)}</text>
    <text x="${W - 4}" y="${y(m.high) + 4}" fill="#9fb4ae" font-size="11" text-anchor="end">${fmt(m.high)}</text>
    <text x="${W - 4}" y="${y(m.low) + 4}" fill="#9fb4ae" font-size="11" text-anchor="end">${fmt(m.low)}</text>
    <path d="${area}" fill="url(#g${id})"/><path d="${line}" fill="none" stroke="${colour}" stroke-width="2.6" stroke-linecap="round"/>
    ${dots}${ticks}
    <circle cx="${last[0]}" cy="${last[1]}" r="11" fill="none" stroke="${colour}" stroke-width="2" opacity=".6"><animate attributeName="r" values="7;13;7" dur="2s" repeatCount="indefinite"/></circle></svg>`;
}
let chartId = 0;
function chartHTML(m) {
  const colour = COLOURS[m.key] || '#a1e7cc', last = m.series.at(-1);
  const inside = last ? last[1] >= m.low && last[1] <= m.high : true;
  const delta = last ? last[1] - m.baseline : 0;
  return `<div class="chart ${inside ? '' : 'off'}" data-key="${m.key}" style="--accent:${colour}">
    <div class="chart-top"><div><div class="name">${esc(m.label)}</div>
      <div class="src"><b class="badge ${m.kind}">${m.kind === 'nasa' ? 'NASA' : 'SIM'}</b> ${esc(m.range_text)}</div></div>
      <div class="now">${last ? `<b>${last[1]}</b> <small>${esc(m.unit)}</small><br><span class="delta ${inside ? 'in' : 'out'}">${inside ? '✓ in range' : '⚠ off baseline'} · ${delta >= 0 ? '+' : '−'}${fmt(Math.abs(delta))}</span>` : '<small>no data</small>'}</div></div>
    ${chartSVG(m, colour, ++chartId)}</div>`;
}
function moodChartHTML(strain) {
  if (!strain.length) return '';
  const m = { key: 'strain', label: 'Mental strain (daily questionnaire)', unit: '/10', series: strain, kind: 'sim', low: 1, high: 4, baseline: 2, range_text: 'Lower is better · 1–4 low strain', band: '#2f8f6a', bandLabel: 'LOW STRAIN', baseLabel: 'calm' };
  const last = strain.at(-1)[1];
  return `<div class="chart mood-chart ${last > 4 ? 'off' : ''}" style="--accent:#cdb4ff"><div class="chart-top"><div><div class="name">${m.label}</div>
    <div class="src">Average of the six wellbeing questions · lower is calmer</div></div>
    <div class="now"><b>${last}</b> <small>/10</small><br><span class="delta ${last > 4 ? 'out' : 'in'}">${last > 6 ? 'high strain' : last > 4 ? 'some strain' : 'low strain'}</span></div></div>
    ${chartSVG(m, '#cdb4ff', ++chartId)}</div>`;
}
function renderCharts() {
  const list = state.trends.metrics.filter(m => state.group === 'all' || GROUP(m.key) === state.group);
  $('#charts').innerHTML = (state.group === 'all' ? moodChartHTML(state.trends.strain) : '') + list.map(chartHTML).join('');
  $$('#charts .chart[data-key]').forEach(c => c.onclick = () => openTrend([c.dataset.key], state.labels[c.dataset.key][0]));
}
async function loadTrends() { state.trends = await api(`/api/trends?crew=${state.crew}`); renderCharts(); }
$$('[data-group]').forEach(b => b.onclick = () => { $$('[data-group]').forEach(x => x.classList.toggle('on', x === b)); state.group = b.dataset.group; if (state.trends) renderCharts(); });

// ------------------------------------------------------------------ trend pop-up with quick add
async function openTrend(keys, title) {
  if (!state.trends) state.trends = await api(`/api/trends?crew=${state.crew}`);
  $('#trend-title').textContent = title;
  $('#trend-body').innerHTML = state.trends.metrics.filter(m => keys.includes(m.key)).map(chartHTML).join('');
  $('#quick-add').innerHTML = `<b>Add a reading now</b>` + keys.map(k => `<label>${esc(state.labels[k][0])}
      <input name="${k}" inputmode="decimal" placeholder="${esc(state.labels[k][1])}" autocomplete="off"></label>`).join('') +
    `<button class="btn primary">Save</button>`;
  $('#quick-result').innerHTML = '';
  $('#quick-add').onsubmit = async e => {
    e.preventDefault();
    const readings = Object.fromEntries($$('#quick-add input').map(i => [i.name, i.value.trim()]).filter(([, v]) => v));
    if (!Object.keys(readings).length) return;
    try {
      const r = await api('/api/entry', { crew: state.crew, readings, notes: '' });
      state.trends = null; await loadToday();
      state.trends = await api(`/api/trends?crew=${state.crew}`);
      $('#trend-body').innerHTML = state.trends.metrics.filter(m => keys.includes(m.key)).map(chartHTML).join('');
      $$('#quick-add input').forEach(i => i.value = '');
      $('#quick-result').innerHTML = resultHTML(r, true); startAnims($('#quick-result')); wireRepeat($('#quick-result'));
      if ($('#trends').classList.contains('on')) renderCharts();
    } catch (err) { $('#quick-result').innerHTML = `<p class="muted">${esc(err.message)}</p>`; }
  };
  $('#trend-dialog').showModal(); const first = $('#quick-add input'); if (first) first.focus();
}

// ------------------------------------------------------------------ new entry (reads as you type)
function fillMetricSelect() {
  $('#add-metric').innerHTML = '<option value="">Add a reading by hand…</option>' +
    state.today.tiles.map(t => `<option value="${t.key}">${esc(t.label)} (${esc(t.unit)})</option>`).join('');
}
function renderFound(comparisons = {}) {
  const keys = Object.keys(state.found);
  $('#found-rows').innerHTML = keys.length ? keys.map(k => {
    const [label, unit] = state.labels[k] || [k, ''];
    const cmp = comparisons[k] || state.lastCmp?.[k] || '';
    return `<div class="frow"><b>${esc(label)}</b><input data-k="${k}" value="${esc(state.found[k])}" inputmode="decimal">
      <span class="muted small">${esc(unit)}</span><span class="cmp ${cmp.startsWith('within') ? 'in' : 'out'}">${esc(cmp)}</span>
      <button class="rm" data-k="${k}" aria-label="Remove">✕</button></div>`;
  }).join('') : '<p class="muted small">No readings yet. Write or photograph a number, or add one by hand.</p>';
  $$('#found-rows input').forEach(i => i.oninput = () => { state.found[i.dataset.k] = i.value; state.manual.add(i.dataset.k); });
  $$('#found-rows .rm').forEach(b => b.onclick = () => { delete state.found[b.dataset.k]; state.manual.delete(b.dataset.k); renderFound(); });
  $('#entry-region').textContent = 'Body area: ' + state.region;
}
async function readEntry() {
  const text = $('#entry-text').value.trim();
  if (!text && !state.photoText) return;
  const key = text + '|' + (state.photoText || '');
  if (key === state.lastRead) return;
  const run = ++state.run;
  $('#entry-status').textContent = 'Reading your entry…';
  try {
    const r = await api('/api/extract', { text, crew: state.crew, photo_text: state.photoText });
    if (run !== state.run) return;
    state.lastRead = key;
    for (const k of [...state.aiKeys]) if (!(k in r.readings) && !state.manual.has(k)) delete state.found[k];
    for (const [k, v] of Object.entries(r.readings)) { if (!state.manual.has(k)) state.found[k] = v; }
    Object.assign(state.labels, r.labels); state.aiKeys = new Set(Object.keys(r.readings));
    state.region = r.region || 'General'; state.lastCmp = r.comparisons;
    const noted = (r.symptoms || []).join(', ');
    $('#entry-status').textContent = `Read by ${r.engine}` + (noted ? ` · noted: ${noted}` : '');
    renderFound(r.comparisons);
  } catch (e) { $('#entry-status').textContent = 'Could not read the entry: ' + e.message; }
}
function openEntry() {
  Object.assign(state, { found: {}, manual: new Set(), aiKeys: new Set(), photoText: null, region: 'General', lastRead: '', lastCmp: {} });
  $('#entry-text').value = ''; $('#photo-preview').innerHTML = ''; $('#entry-status').textContent = 'Runs on this server with a local model.';
  renderFound(); $('#entry-dialog').showModal(); $('#entry-text').focus();
}
$('#entry-text').addEventListener('input', () => { clearTimeout(state.timer); state.timer = setTimeout(readEntry, 900); });
$('#add-metric').onchange = e => { const k = e.target.value; if (k) { state.found[k] = state.found[k] || ''; state.manual.add(k); renderFound(); e.target.value = ''; } };
$('#entry-photo').onchange = async e => {
  const file = e.target.files[0]; if (!file) return;
  $('#photo-preview').innerHTML = `<img src="${URL.createObjectURL(file)}" alt="Your photo">`;
  if (!window.Tesseract) { $('#entry-status').textContent = 'Photo reader is still loading. Try again in a moment.'; return; }
  $('#entry-status').textContent = 'Reading the photo in your browser…';
  try {
    const { data } = await Tesseract.recognize(file, 'eng');
    state.photoText = data.text.trim();
    $('#entry-status').textContent = state.photoText ? 'Photo says: ' + state.photoText.replace(/\s*\n\s*/g, ' · ').slice(0, 90) : 'No printed numbers in the photo.';
    state.lastRead = ''; await readEntry();
  } catch (err) { $('#entry-status').textContent = 'Could not read the photo: ' + err.message; }
};
$('#entry-save').onclick = async () => {
  const text = $('#entry-text').value.trim();
  if (text && text + '|' + (state.photoText || '') !== state.lastRead) await readEntry();
  const readings = Object.fromEntries(Object.entries(state.found).filter(([, v]) => String(v).trim()));
  if (!text && !Object.keys(readings).length) { $('#entry-status').textContent = 'Nothing to save yet.'; return; }
  try {
    const r = await api('/api/entry', { crew: state.crew, readings, notes: text, region: state.region });
    $('#entry-dialog').close(); showResult(r); state.trends = null; loadToday();
  } catch (e) { $('#entry-status').textContent = e.message; }
};

// ------------------------------------------------------------------ results (entries and questionnaire)
function resultHTML(r, compact = false) {
  const wb = r.wellbeing;
  if (wb) {
    const scene = wb.scene, high = scene === 'support';
    const head = high ? ['Talk with a psychologist', 'Your answers show high strain. You do not have to handle it alone.']
      : scene === 'routine' ? ['Low strain today', 'Your answers look calm. Keep your routine going.']
      : scene === 'sleep' ? ['Protect your sleep', 'Sleep difficulty stands out today.'] : ['Take care of yourself today', 'Some strain shows up in your answers.'];
    const clip = scene === 'routine' ? 'walk' : scene === 'sleep' ? 'nap' : 'meditate';
    const care = scene === 'routine' ? ['Keep exercising', 'Drink water and keep your sleep window.']
      : scene === 'sleep' ? ['Rest when you can', 'Use your scheduled rest window and a short nap if allowed.']
      : ['Meditate, breathe, listen to music', 'Take 10 minutes: slow breathing, a guided meditation or music you like. A short call home can help too.'];
    return `<div class="banner ${high ? 'alert' : scene === 'routine' ? 'ok' : 'mind'}"><div><p class="big">${head[0]}</p><div class="sub">${esc(wb.label)} · ${head[1]}</div></div></div>
      <div class="split">${anim(clip, 'big')}<div class="howto"><b>${care[0]}</b><p class="small" style="margin:6px 0 0">${care[1]}</p>
        <p class="small" style="margin:10px 0 0"><b>Next step:</b> ${esc(wb.action)}</p>
        ${high || scene !== 'routine' ? `<button class="btn primary" style="margin-top:10px" data-psy>Book a private psychologist session</button>` : ''}</div></div>
      ${high ? `<div class="notice psy"><span class="ico">🧠</span><div>Your flight psychologist on Earth has been notified of this check-in.<small>Simulated in this demo. NASA Standard Measures track mental fatigue, stress and mood because they matter on long missions.</small></div></div>` : ''}
      <div class="explain"><b>✦ What this means</b><div id="explain-text" class="muted">Thinking on this server…</div></div>`;
  }
  const off = (r.comparisons || []).filter(c => !c.inside), sleepOff = off.find(c => c.key === 'sleep');
  const words = { green: ['All clear', 'Everything you logged is within its baseline range.', 'ok'], yellow: ['Off baseline: let\'s check again', r.title, 'watch'],
    red: ['Immediate attention', r.title, 'alert'] }[r.status] || ['Saved', '', 'ok'];
  const cmp = (r.comparisons || []).map(c => `<li><b>${esc(c.label)} ${c.reading} ${esc(c.unit)}</b> <span class="badge ${c.kind}">${c.kind === 'nasa' ? 'NASA' : 'SIM'}</span>
    <span style="color:${c.inside ? 'var(--ok)' : '#ff8a8a'}">${esc(c.summary)}</span></li>`).join('');
  let guide = '';
  const target = off.find(c => c.key !== 'sleep');
  if (target) {
    const clip = MEASURE_CLIP(target.key), keys = ['systolic', 'diastolic'].includes(target.key) ? ['systolic', 'diastolic'] : [target.key];
    guide = `<div class="split">${anim(clip, 'big')}<div class="howto"><b>Measure ${esc(target.label.toLowerCase())} again, correctly</b>
      <ol>${(HOWTO[clip] || HOWTO.sit).map(s => `<li>${esc(s)}</li>`).join('')}</ol>
      <form class="repeat" data-repeat>${keys.map(k => `<input name="${k}" placeholder="${esc((state.labels[k] || [k, ''])[0])}" inputmode="decimal">`).join('')}
        <button class="btn primary">Save repeat</button></form></div></div>
      <div class="notice"><span class="ico">📡</span><div>Your flight surgeon on Earth has been notified of this reading.<small>Simulated in this demo.</small></div></div>`;
  } else if (sleepOff) {
    guide = `<div class="split">${anim('nap', 'big')}<div class="howto"><b>Short on sleep: take a nap when you can</b>
      <ol><li>When your schedule allows, take a 20-minute nap.</li><li>Tell the crew lead before safety-critical work if you feel too tired.</li><li>Protect your next sleep period.</li></ol></div></div>`;
  } else if (r.status === 'green' && !compact) {
    guide = `<div class="split">${anim('water', 'big')}<div class="howto"><b>Nice work</b><p class="small">Keep drinking water, exercising and sleeping on schedule.</p></div></div>`;
  }
  return `<div class="banner ${words[2]}"><div><p class="big">${words[0]}</p><div class="sub">${esc(words[1])}</div></div></div>
    ${cmp ? `<ul class="muted" style="padding-left:18px;margin:6px 0">${cmp}</ul>` : ''}${guide}
    ${!compact && r.status !== 'green' ? `<h3>What to do next</h3><ol class="steps ${words[2]}">${r.actions.map(a => `<li>${esc(a)}</li>`).join('')}</ol>` : ''}
    ${!compact ? `<div class="explain"><b>✦ What this means</b><div id="explain-text" class="muted">${r.status === 'green' ? 'Everything you logged is within its baseline range.' : 'Thinking on this server…'}</div>
      ${r.questions?.length ? `<p class="small" style="margin:8px 0 0"><b style="display:inline">Worth noting:</b> ${r.questions.map(esc).join(' ')}</p>` : ''}
      <p class="small muted" style="margin:8px 0 0">Explains the rule result above. It never changes the status or gives a diagnosis.</p></div>
      <details style="margin-top:10px"><summary class="muted">Why this result?</summary><ul class="muted small">${r.rationale.map(x => `<li>${esc(x)}</li>`).join('')}</ul></details>` : ''}`;
}
function wireRepeat(root) {
  const f = $('[data-repeat]', root);
  if (f) f.onsubmit = async e => {
    e.preventDefault();
    const readings = Object.fromEntries($$('input', f).map(i => [i.name, i.value.trim()]).filter(([, v]) => v));
    if (!Object.keys(readings).length) return;
    const r = await api('/api/entry', { crew: state.crew, readings, notes: 'Repeat measurement' });
    $('#result-dialog').open ? showResult(r) : ($('#quick-result').innerHTML = resultHTML(r, true), startAnims($('#quick-result')), wireRepeat($('#quick-result')));
    state.trends = null; loadToday();
  };
  $$('[data-psy]', root).forEach(b => b.onclick = () => { b.textContent = 'Session request sent (demo) ✓'; b.disabled = true; });
}
function showResult(r) {
  $('#result-title').textContent = r.wellbeing ? 'Wellbeing check-in' : r.status === 'green' ? 'All clear' : 'Entry result';
  $('#result-body').innerHTML = resultHTML(r); startAnims($('#result-body')); wireRepeat($('#result-body'));
  if (!$('#result-dialog').open) $('#result-dialog').showModal();
  if (r.status !== 'green' || r.wellbeing) {
    stream('/api/explain', { crew: state.crew, stamp: r.stamp }, t => { const el = $('#explain-text'); if (el) { el.textContent = t; el.classList.remove('muted'); } })
      .catch(e => { const el = $('#explain-text'); if (el) el.textContent = 'Local AI unavailable: ' + e.message; });
  }
}

// ------------------------------------------------------------------ ask
async function ask(question) {
  $('#ask-input').value = question; $('#ask-answer').textContent = 'Thinking on this server… (can take up to 30 seconds)';
  try { await stream('/api/ask', { crew: state.crew, question }, t => $('#ask-answer').textContent = t); }
  catch (e) { $('#ask-answer').textContent = e.message; }
}
$('#ask-form').onsubmit = e => { e.preventDefault(); const q = $('#ask-input').value.trim(); if (q) ask(q); };
$$('#ask-dialog .chip').forEach(c => c.onclick = () => ask(c.textContent));

// ------------------------------------------------------------------ questionnaire
function openQuiz() {
  $('#quiz-rows').innerHTML = Object.entries(QUESTIONS).map(([k, q]) =>
    `<div class="qrow"><span>${esc(q)}</span><input type="range" min="1" max="10" value="3" data-k="${k}"><b id="v-${k}">3</b></div>`).join('');
  $$('#quiz-rows input').forEach(i => i.oninput = () => $('#v-' + i.dataset.k).textContent = i.value);
  $('#quiz-dialog').showModal();
}
$('#quiz-save').onclick = async () => {
  const ratings = Object.fromEntries($$('#quiz-rows input').map(i => [i.dataset.k, +i.value]));
  try { const r = await api('/api/questionnaire', { crew: state.crew, ratings }); $('#quiz-dialog').close(); state.trends = null; await loadToday(); showResult(r); }
  catch (e) { alert(e.message); }
};

// ------------------------------------------------------------------ wiring
$$('[data-crew]').forEach(b => b.onclick = async () => {
  $$('[data-crew]').forEach(x => x.classList.toggle('on', x === b)); state.crew = b.dataset.crew; state.trends = null;
  await loadToday(); if ($('#trends').classList.contains('on')) loadTrends();
});
$$('[data-tab]').forEach(b => b.onclick = () => {
  $$('[data-tab]').forEach(x => x.classList.toggle('on', x === b));
  $$('.view').forEach(v => v.classList.toggle('on', v.id === b.dataset.tab));
  if (b.dataset.tab === 'trends') loadTrends();
});
$$('.site').forEach(s => s.onclick = () => openTrend(SITE_KEYS[s.dataset.site], SITE_NAMES[s.dataset.site]));
$('#open-entry').onclick = openEntry;
$('#open-ask').onclick = () => { $('#ask-answer').textContent = ''; $('#ask-dialog').showModal(); $('#ask-input').focus(); };
api('/api/health').then(h => { const el = $('#ai-status'); el.textContent = h.ai ? `Local AI ready · ${h.model}` : 'Local AI offline · rules still work';
  el.classList.add(h.ai ? 'ready' : 'off'); }).catch(() => {});
loadToday().catch(e => { $('#tiles').innerHTML = `<p class="muted">Could not load data: ${esc(e.message)}</p>`; });
