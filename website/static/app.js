// Aboard website: talks to server.py. Rules decide statuses; the local model reads, explains and answers.
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const state = { crew: 'mo', today: null, trends: null, labels: {}, found: {}, manual: new Set(), aiKeys: new Set(),
                photoText: null, region: 'General', lastRead: '', timer: null, run: 0 };
const SITE_KEYS = { brain: ['sleep'], eyes: ['trt250_left', 'trt250_right'], heart: ['pulse', 'systolic', 'diastolic'],
  labs: ['serum_sodium', 'serum_potassium', 'serum_creatinine', 'serum_glucose'], calf_left: ['calf_csa_left'], calf_right: ['calf_csa_right'] };
const SITE_NAMES = { brain: 'Brain · sleep', eyes: 'Eyes · optic nerve OCT', heart: 'Heart', labs: 'Blood labs',
  calf_left: 'Left calf', calf_right: 'Right calf' };
const QUESTIONS = { mental_fatigue: 'How mentally exhausted do you feel right now?', stress_now: 'How stressed do you feel right now?',
  workload_now: 'How demanding has your work felt today?', sleep_difficulty: 'How much difficulty did you have sleeping last night?',
  low_mood: 'How low or down have you felt today?', task_difficulty: 'How much have your symptoms affected your duties today?' };
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmt = v => { const n = +v; return Math.abs(n) >= 10 ? +n.toFixed(1) : +n.toFixed(2); };

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
  renderBody(); renderTiles(); renderSticker(state.today.mood); fillMetricSelect();
}
function renderBody() {
  for (const btn of $$('.site')) {
    btn.classList.remove('ok', 'watch', 'alert', 'none'); btn.classList.add(state.today.body[btn.dataset.site] || 'none');
  }
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
    <div class="sum">${esc(t.summary)}</div></div>`;
}
function renderTiles() {
  const tiles = state.today.tiles, attn = tiles.filter(t => t.status === 'watch' || t.status === 'alert');
  const groups = [['Needs attention', attn, 'attn'], ['Vital signs', tiles.filter(t => ['sleep', 'pulse', 'systolic', 'diastolic'].includes(t.key))],
    ['Blood labs', tiles.filter(t => t.key.startsWith('serum'))], ['Muscle and eyes', tiles.filter(t => /^(calf|trt)/.test(t.key))]];
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

// ------------------------------------------------------------------ trends
function chartSVG(m) {
  const pts = m.series, W = 600, H = 150, L = 8, R = 92, T = 10, B = 18;
  if (!pts.length) return `<svg viewBox="0 0 ${W} ${H}"><text x="${W / 2}" y="${H / 2}" fill="#a9c0ba" text-anchor="middle" font-size="14">No readings yet</text></svg>`;
  const vals = pts.map(p => p[1]).concat([m.low, m.high, m.baseline]);
  let lo = Math.min(...vals), hi = Math.max(...vals); const pad = (hi - lo) * .08 || 1; lo -= pad; hi += pad;
  const y = v => T + (hi - v) / (hi - lo) * (H - T - B), x = i => L + (pts.length === 1 ? 0.5 : i / (pts.length - 1)) * (W - L - R);
  const band = m.kind === 'nasa' ? '#1c3552' : '#2e2748', word = m.kind === 'nasa' ? 'NASA' : 'preflight';
  const line = pts.map((p, i) => `${x(i).toFixed(1)},${y(p[1]).toFixed(1)}`).join(' ');
  const dots = pts.map((p, i) => { const inside = p[1] >= m.low && p[1] <= m.high;
    return `<circle cx="${x(i)}" cy="${y(p[1])}" r="${pts.length > 20 ? 2.6 : 4}" fill="${inside ? '#a1e7cc' : '#ffd181'}"><title>${p[0]} · ${p[1]} ${m.unit}</title></circle>`; }).join('');
  return `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
    <rect x="${L}" y="${y(m.high)}" width="${W - L - R}" height="${y(m.low) - y(m.high)}" fill="${band}"/>
    <line x1="${L}" x2="${W - R}" y1="${y(m.baseline)}" y2="${y(m.baseline)}" stroke="#f3f5ed" stroke-dasharray="6 4" stroke-width="1.2"/>
    <text x="${W - 4}" y="${y(m.baseline) + 4}" fill="#f3f5ed" font-size="12" font-weight="700" text-anchor="end">${word} ${fmt(m.baseline)}</text>
    <text x="${W - 4}" y="${y(m.high) + 4}" fill="#a9c0ba" font-size="11" text-anchor="end">${fmt(m.high)}</text>
    <text x="${W - 4}" y="${y(m.low) + 4}" fill="#a9c0ba" font-size="11" text-anchor="end">${fmt(m.low)}</text>
    <polyline points="${line}" fill="none" stroke="#a1e7cc" stroke-width="2"/>${dots}</svg>`;
}
function chartHTML(m) {
  const last = m.series.at(-1);
  const where = last ? (last[1] >= m.low && last[1] <= m.high ? 'within' : 'outside') + (m.kind === 'nasa' ? ' NASA range' : ' normal range') : '';
  return `<div class="chart"><div class="chart-head"><b>${esc(m.label)} <span class="muted small">${esc(m.unit)}</span></b>
    <span><span class="muted small">${esc(m.range_text)}</span> <b class="badge ${m.kind}">${m.kind === 'nasa' ? 'NASA' : 'SIM'}</b></span></div>
    ${chartSVG(m)}<div class="foot">${last ? `Latest ${last[1]} ${esc(m.unit)} on ${last[0]} · ${m.series.length} readings · ${where}` : ''}</div></div>`;
}
async function loadTrends() {
  state.trends = await api(`/api/trends?crew=${state.crew}`);
  $('#charts').innerHTML = state.trends.metrics.map(chartHTML).join('');
}
async function openTrend(keys, title) {
  if (!state.trends) await loadTrends();
  $('#trend-title').textContent = title;
  $('#trend-body').innerHTML = state.trends.metrics.filter(m => keys.includes(m.key)).map(chartHTML).join('');
  $('#trend-dialog').showModal();
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
  const url = URL.createObjectURL(file);
  $('#photo-preview').innerHTML = `<img src="${url}" alt="Your photo">`;
  if (!window.Tesseract) { $('#entry-status').textContent = 'Photo reader is still loading. Try again in a moment.'; return; }
  $('#entry-status').textContent = 'Reading the photo in your browser…';
  try {
    const { data } = await Tesseract.recognize(file, 'eng');
    state.photoText = data.text.trim();
    $('#entry-status').textContent = state.photoText ? 'Photo says: ' + state.photoText.replace(/\s*\n\s*/g, ' · ').slice(0, 90) : 'No printed numbers in the photo.';
    state.lastRead = ''; await readEntry();
  } catch (err) { $('#entry-status').textContent = 'Could not read the photo: ' + err.message; }
};
async function saveEntry(urgent = false) {
  const text = $('#entry-text').value.trim();
  if (!urgent && text && text + '|' + (state.photoText || '') !== state.lastRead) await readEntry();
  const readings = Object.fromEntries(Object.entries(state.found).filter(([, v]) => String(v).trim()));
  if (!urgent && !text && !Object.keys(readings).length) { $('#entry-status').textContent = 'Nothing to save yet.'; return; }
  try {
    const r = await api('/api/entry', { crew: state.crew, readings, notes: text, region: state.region, urgent });
    $('#entry-dialog').close(); showResult(r); state.trends = null; loadToday();
  } catch (e) { $('#entry-status').textContent = e.message; }
}
$('#entry-save').onclick = () => saveEntry(false);
$('#entry-help').onclick = () => saveEntry(true);

// ------------------------------------------------------------------ result + explanation
function showResult(r) {
  const words = { green: ['All clear', 'ok'], yellow: ['Follow up', 'watch'], red: ['Immediate attention', 'alert'] }[r.status] || ['Saved', 'none'];
  $('#result-title').textContent = r.status === 'green' ? 'All clear' : r.title;
  const cmp = (r.comparisons || []).map(c => `<li><b>${esc(c.label)} ${c.reading} ${esc(c.unit)}</b> · <span class="badge ${c.kind}">${c.kind === 'nasa' ? 'NASA' : 'SIM'}</span>
    <span class="${c.inside ? '' : 'warn'}" style="color:${c.inside ? 'var(--ok)' : 'var(--watch)'}">${esc(c.summary)}</span></li>`).join('');
  $('#result-body').innerHTML = `<span class="status-chip ${words[1]}">${words[0]}</span>
    ${cmp ? `<ul class="muted" style="padding-left:18px">${cmp}</ul>` : ''}
    ${r.status !== 'green' ? `<h3>What to do next</h3><ol class="steps ${words[1]}">${r.actions.map(a => `<li>${esc(a)}</li>`).join('')}</ol>` : ''}
    <div class="explain"><b>✦ What this means</b><div id="explain-text" class="muted">Thinking on this server…</div>
    ${r.questions?.length ? `<p class="small" style="margin:8px 0 0"><b style="display:inline">Worth noting:</b> ${r.questions.map(esc).join(' ')}</p>` : ''}
    <p class="small muted" style="margin:8px 0 0">Explains the rule result above. It never changes the status or gives a diagnosis.</p></div>
    <details style="margin-top:10px"><summary class="muted">Why this result?</summary><ul class="muted small">${r.rationale.map(x => `<li>${esc(x)}</li>`).join('')}</ul></details>`;
  $('#result-dialog').showModal();
  if (r.status !== 'green' || r.wellbeing) {
    stream('/api/explain', { crew: state.crew, stamp: r.stamp }, t => { const el = $('#explain-text'); if (el) { el.textContent = t; el.classList.remove('muted'); } })
      .catch(e => { const el = $('#explain-text'); if (el) el.textContent = 'Local AI unavailable: ' + e.message; });
  } else { $('#explain-text').textContent = 'Everything you logged is within its baseline range.'; }
}

// ------------------------------------------------------------------ ask
async function ask(question) {
  $('#ask-input').value = question; $('#ask-answer').textContent = 'Thinking on this server…';
  try { await stream('/api/ask', { crew: state.crew, question }, t => $('#ask-answer').textContent = t); }
  catch (e) { $('#ask-answer').textContent = e.message; }
}
$('#ask-form').onsubmit = e => { e.preventDefault(); const q = $('#ask-input').value.trim(); if (q) ask(q); };
$$('.chip').forEach(c => c.onclick = () => ask(c.textContent));

// ------------------------------------------------------------------ questionnaire
function openQuiz() {
  $('#quiz-rows').innerHTML = Object.entries(QUESTIONS).map(([k, q]) =>
    `<div class="qrow"><span>${esc(q)}</span><input type="range" min="1" max="10" value="3" data-k="${k}"><b id="v-${k}">3</b></div>`).join('');
  $$('#quiz-rows input').forEach(i => i.oninput = () => $('#v-' + i.dataset.k).textContent = i.value);
  $('#quiz-dialog').showModal();
}
$('#quiz-save').onclick = async () => {
  const ratings = Object.fromEntries($$('#quiz-rows input').map(i => [i.dataset.k, +i.value]));
  try { const r = await api('/api/questionnaire', { crew: state.crew, ratings }); $('#quiz-dialog').close(); renderSticker(r.mood); showResult(r); state.trends = null; }
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
$('#open-quiz').onclick = openQuiz;
api('/api/health').then(h => { const el = $('#ai-status'); el.textContent = h.ai ? `Local AI ready · ${h.model}` : 'Local AI offline · rules still work';
  el.classList.add(h.ai ? 'ready' : 'off'); }).catch(() => {});
loadToday().catch(e => { $('#tiles').innerHTML = `<p class="muted">Could not load data: ${esc(e.message)}</p>`; });
