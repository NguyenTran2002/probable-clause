// Prototype only. Plays one scripted sample run; there is no backend.
'use strict';

const MODEL = 'claude-sonnet-5-5';
const QUERIES = [
  'acquiring records held by a third party as a search',
  'stored location history and the warrant requirement',
];

const P = {
  'P-01': { kase: 'Exemplar v. United States', cite: '000 U.S. 101 (1967)', decided: 'December 18, 1967', kind: 'Majority opinion', by: 'Justice Alder', joined: 'joined by Justices Birch, Cedar, Dogwood, Elm, Fir and Gum', blocks: ['[Sample sentence 1 of 3, standing in for the opinion’s framing of the question.] ', '[Sample sentence 2 of 3, standing in for the test the later cases apply.] ', '[Sample sentence 3 of 3, standing in for the test applied to the facts.]'], pin: '000 U.S., at 106', q: 0, keep: true, reason: 'States the test the later cases apply.' },
  'P-02': { kase: 'Exemplar v. United States', cite: '000 U.S. 101 (1967)', decided: 'December 18, 1967', kind: 'Dissent', by: 'Justice Hazel', joined: 'joined by no other Justice', blocks: ['[Sample paragraph sent as a single block. It stands in for dissent text reading the test more narrowly.]'], pin: '000 U.S., at 112', q: 0, keep: true, reason: 'Shows where the opinions disagree on the reach of the test.' },
  'P-03': { kase: 'Placeholder v. State of Example', cite: '000 U.S. 202 (1979)', decided: 'June 20, 1979', kind: 'Majority opinion', by: 'Justice Ironwood', joined: 'joined by Justices Juniper, Katsura, Larch, Maple and Nutmeg', blocks: ['[Sample paragraph sent as a single block. It stands in for majority-opinion text on records a person hands to a third party.]'], pin: '000 U.S., at 209', q: 0, keep: true, reason: 'The third-party records rule the newest case narrows.' },
  'P-04': { kase: 'United States v. Specimen', cite: '000 U.S. 303 (2012)', decided: 'January 23, 2012', kind: 'Plurality opinion', by: 'Justice Oak', joined: 'joined by Justices Pine, Quince and Rowan', blocks: ['[Sample paragraph sent as a single block. It stands in for plurality-opinion text about a device attached to a vehicle.]'], pin: '000 U.S., at 307', q: 0, keep: false, reason: 'About a tracker fixed to a car, not stored records.' },
  'P-05': { kase: 'Illustration v. United States', cite: '000 U.S. ___ (2026)', decided: 'June 25, 2026', kind: 'Majority opinion', by: 'Justice Willow', joined: 'joined by Justices Aspen, Beech, Cypress, Ebony and Hawthorn', blocks: ['[Sample sentence 1 of 4, standing in for the facts of the case.] ', '[Sample sentence 2 of 4, standing in for the holding that acquiring stored location history is a search.] ', '[Sample sentence 3 of 4, standing in for why the third-party rule does not reach this kind of record.] ', '[Sample sentence 4 of 4, standing in for the disposition.]'], pin: 'slip op., at 9', q: 1, keep: true, slip: true, reason: 'Addresses stored location history directly, and is the newest case in the corpus.' },
  'P-06': { kase: 'Illustration v. United States', cite: '000 U.S. ___ (2026)', decided: 'June 25, 2026', kind: 'Syllabus', blocks: ['[Sample syllabus paragraph sent as a single block. It stands in for the Reporter’s summary of the holding.]'], q: 1, keep: false, slip: true, syllabus: true, reason: 'The Reporter’s summary, not the Court’s words; P-05 makes the point in the opinion.' },
  'P-07': { kase: 'United States v. Specimen', cite: '000 U.S. 303 (2012)', decided: 'January 23, 2012', kind: 'Concurrence', by: 'Justice Sycamore', joined: 'joined by Justice Tamarind', blocks: ['[Sample sentence 1 of 2, standing in for concurrence text about long-term location tracking.] ', '[Sample sentence 2 of 2, standing in for the concurrence’s reservation.]'], pin: '000 U.S., at 318', q: 1, keep: false, reason: 'A concurrence; the newer majority opinion (P-05) speaks to the question directly.' },
};
const KEPT = ['P-01', 'P-02', 'P-03', 'P-05'];
const HUE = { 'P-01': 'h1', 'P-02': 'h2', 'P-03': 'h3', 'P-05': 'h4' };
const CASES = ['Exemplar v. United States', 'Placeholder v. State of Example', 'Illustration v. United States', 'Phantom v. United States'];

// A citation is a passage plus a block range [start, end), as search_result_location gives it.
// Sentence-block passages (P-01, P-05) cite single sentences or runs of them;
// paragraph-block passages (P-02, P-03) cite the whole paragraph. One rendering path serves both.
const ANSWER = [
  { text: 'In Exemplar v. United States (1967), the majority set out the test the later cases apply.', cite: { p: 'P-01', start: 1, end: 2 } },
  { text: ' The dissent in that case read the test more narrowly.', cite: { p: 'P-02', start: 0, end: 1 } },
  { para: true },
  { text: 'Placeholder v. State of Example (1979) held that records a person hands to a third party fall outside that protection.', cite: { p: 'P-03', start: 0, end: 1 } },
  { text: ' Illustration v. United States (2026) treated the acquisition of stored location history as a search, narrowing the earlier rule for this kind of data.', cite: { p: 'P-05', start: 1, end: 3 } },
  { para: true },
  { text: 'Read in date order, the line runs from a broad test, to a third-party rule, to a narrower view of that rule for location data. Some discussions also point to Phantom v. United States.', tag: true },
  { para: true },
  { text: 'This describes what the Court held. It does not say how the holdings apply to anyone’s situation.', tag: true },
];
const CITES = ANSWER.filter(b => b.cite).map(b => b.cite);
CITES.forEach((c, k) => { c.k = k; });

const WEB = { query: 'Supreme Court stored location data Fourth Amendment', published_after: '2026-06-30', category: 'news', search_type: 'auto', num_results: 8 };
const LINKS = [
  ['https://example.com/sample-petition', 'Sample article: a petition on location data reaches the Court', 'example.com, published August 14, 2026'],
  ['https://example.org/sample-explainer', 'Sample explainer: what the newest location-data case left open', 'example.org, published July 2, 2026'],
  ['https://example.net/sample-docket', 'Sample docket note', 'example.net, published September 30, 2026'],
];

const $ = s => document.querySelector(s);
const body = document.body;
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
function el(tag, cls, html) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html != null) e.innerHTML = html;
  return e;
}
function paint(src) {
  return esc(src).replace(/(&quot;(?:[^&]|&(?!quot;))*?&quot;)(\s*:)?|\b(-?\d+(?:\.\d+)?)\b|\b(true|false|null)\b/g,
    (m, str, colon, num, lit) => str ? (colon ? `<span class="k">${str}</span>${colon}` : `<span class="s">${str}</span>`)
      : `<span class="n">${num || lit}</span>`);
}
// pretty-print, keeping short objects and arrays on one line
function pretty(v, ind = '') {
  const one = JSON.stringify(v);
  if (v === null || typeof v !== 'object' || one.length <= 60) return one;
  const pad = ind + '  ';
  if (Array.isArray(v)) return '[\n' + v.map(x => pad + pretty(x, pad)).join(',\n') + '\n' + ind + ']';
  return '{\n' + Object.entries(v).map(([k, x]) => pad + JSON.stringify(k) + ': ' + pretty(x, pad)).join(',\n') + '\n' + ind + '}';
}
const json = o => paint(pretty(o));
function callLine(name, input, max = 150) {
  let s = JSON.stringify(input);
  if (s.length > max) s = s.slice(0, max) + ' …';
  return `<span class="m">${name}(</span>${paint(s)}<span class="m">)</span>`;
}
const source = id => `probable-clause://passages/${id}`;
const title = id => `${P[id].kase}, ${P[id].cite}, ${P[id].kind.toLowerCase()}${P[id].by ? ' by ' + P[id].by : ''}`;
const result = id => ({ type: 'search_result', source: source(id), title: title(id), content: P[id].blocks.map(text => ({ type: 'text', text })), citations: { enabled: true } });
const citedText = c => P[c.p].blocks.slice(c.start, c.end).join('');
function fmt(text) {
  let h = esc(text);
  for (const c of CASES) h = h.split(c).join(c === 'Phantom v. United States' ? `<i class="phantom">${c}</i>` : `<i>${c}</i>`);
  return h;
}

// ---------- panes, modes, view ----------
const panes = { research: $('#pane-research'), sources: $('#pane-sources'), wire: $('#pane-wire') };
const phone = () => matchMedia('(max-width: 759px)').matches;

function setPane(p) {
  body.dataset.pane = p;
  if (playing) requestAnimationFrame(() => panes[p].scrollTo({ top: panes[p].scrollHeight }));
  redraw();
}
function setMode(m) {
  body.dataset.mode = m;
  document.querySelectorAll('.seg button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.mode === m)));
  if (m !== 'api' && body.dataset.pane === 'wire') body.dataset.pane = phone() ? 'research' : 'sources';
  if (m === 'api' && !phone() && innerWidth < 1280) body.dataset.pane = 'wire';
  if (playing) requestAnimationFrame(() => Object.values(panes).forEach(p => p.scrollTo({ top: p.scrollHeight })));
  redraw();
}
function swap(view) {
  const go = () => { body.dataset.view = view; scrollTo(0, 0); };
  if (document.startViewTransition && !matchMedia('(prefers-reduced-motion: reduce)').matches) document.startViewTransition(go);
  else go();
}
function visible(e) { return e && e.getClientRects().length > 0; }

// scroll an element to the middle of its own pane (scrollIntoView on two panes at once cancels one)
function centerIn(e, smooth = true) {
  const pane = e.closest('.col');
  if (!pane) return;
  const pr = pane.getBoundingClientRect(), er = e.getBoundingClientRect();
  const head = pane.querySelector('.col-head');
  const offset = Math.max((head ? head.offsetHeight : 0) + 12, (pane.clientHeight - er.height) / 2);
  pane.scrollTo({ top: pane.scrollTop + er.top - pr.top - offset, behavior: smooth ? 'smooth' : 'auto' });
}

// keep a pane pinned to its newest content unless the reader scrolled away
function fresh(node) {
  node.classList.add('fresh');
  setTimeout(() => node.classList.remove('fresh'), 450);
  return node;
}
function append(pane, list, node) {
  fresh(node);
  const near = pane.scrollHeight - pane.scrollTop - pane.clientHeight < 260;
  list.append(node);
  if (near) pane.scrollTo({ top: pane.scrollHeight, behavior: skipping ? 'auto' : 'smooth' });
  return node;
}

// ---------- rendering ----------
const stepsEl = $('#steps'), passagesEl = $('#passages'), wireEl = $('#wire');

function status(text, working) {
  const s = $('#status');
  s.textContent = text;
  s.classList.toggle('working', !!working);
}
function addStep({ title: t, say, query, meta, code, wire }) {
  const li = el('li', 'step working');
  li.innerHTML = `<h3>${esc(t)}</h3>` +
    (say ? `<p class="say">${esc(say)}</p>` : '') +
    (query ? `<p class="query">“${esc(query)}”</p>` : '') +
    `<p class="meta">${meta ? esc(meta) : ''}</p>` +
    (code ? `<code class="code anno" data-wire="${wire}">${callLine(code[0], code[1])}</code>` : '');
  return append(panes.research, stepsEl, li);
}
function finish(li, t, meta, chips, rejected) {
  li.classList.remove('working');
  li.classList.add(rejected ? 'rejected' : 'done');
  li.querySelector('h3').textContent = t;
  if (meta != null) li.querySelector('.meta').textContent = meta;
  if (chips) {
    const c = el('p', 'chips');
    c.innerHTML = chips.map(id => {
      const v = P[id].verdictShown;
      const cls = v === 'kept' ? HUE[id] : v === 'discarded' ? 'out' : '';
      return `<button type="button" class="pill ${cls}" data-goto="${id}">${id}</button>`;
    }).join('');
    li.querySelector('.meta').after(c);
  }
}
function addCard(id) {
  const p = P[id];
  const li = el('li', `card reviewing ${p.keep ? HUE[id] : ''}${p.syllabus ? ' syllabus' : ''}`);
  li.id = 'src-' + id;
  li.dataset.id = id;
  const meta = p.syllabus ? `Decided ${p.decided}. Syllabus.` : `Decided ${p.decided}. ${p.kind} by ${p.by}, ${p.joined}.`;
  li.innerHTML = `
    <p class="verdict"><span class="pid">${id}</span><span class="mark">Reviewing</span><span class="reason"></span></p>
    <p class="case"><i>${esc(p.kase)}</i>, ${esc(p.cite)}</p>
    <p class="meta">${esc(meta)}</p>
    <div class="body">
      ${p.syllabus ? '<p class="syl-label">Syllabus, prepared by the Reporter of Decisions. It constitutes no part of the opinion of the Court.</p>' : ''}
      <p class="text">${p.blocks.map((b, i) => `<span class="sb" data-i="${i}">${esc(b)}</span>`).join('')}${p.pin ? ` <span class="pin">${esc(p.pin)}</span>` : ''}</p>
      <p class="small guarantee">This passage appears verbatim in this ${p.syllabus ? 'opinion’s syllabus' : 'opinion'}.</p>
      ${p.slip ? '<p class="slip">Slip opinion: not yet final in the U.S. Reports, and subject to formal revision.</p>' : ''}
      <p class="small">Found by “${esc(QUERIES[p.q])}”</p>
      <p class="anno"><span class="blk">search_result</span> <span class="blk">${p.blocks.length} text block${p.blocks.length > 1 ? 's' : ''}</span> <span class="blk">${esc(source(id))}</span></p>
    </div>
    <button type="button" class="toggle">Show passage</button>`;
  append(panes.sources, passagesEl, li);
  counts();
}
function verdict(id) {
  const p = P[id], card = $('#src-' + id);
  p.verdictShown = p.keep ? 'kept' : 'discarded';
  card.classList.remove('reviewing');
  card.classList.add(p.verdictShown);
  card.querySelector('.mark').textContent = p.keep ? 'Kept' : 'Discarded';
  card.querySelector('.reason').textContent = p.reason;
  document.querySelectorAll(`[data-goto="${id}"]`).forEach(b => b.classList.add(p.keep ? HUE[id] : 'out'));
  counts();
}
function counts() {
  const all = passagesEl.children.length;
  const kept = Object.values(P).filter(p => p.verdictShown === 'kept').length;
  $('#src-count').textContent = all ? `${all} considered, ${kept} kept` : 'Passages appear here as Claude finds them.';
  $('#tab-count').textContent = all ? `${kept} of ${all}` : '';
}
function addWire(id, dir, label, note, parts) {
  const li = el('li', `msg ${dir}`);
  li.id = id;
  li.innerHTML = `<div class="msg-head"><b>${esc(label)}</b><span>${esc(note)}</span></div>`;
  for (const part of parts) addPart(li, part);
  return append(panes.wire, wireEl, li);
}
function addPart(msg, { id, path, obj, hue }) {
  const d = el('div', `part${hue ? ' cite ' + hue : ''}`);
  if (id) d.id = id;
  d.innerHTML = `<p class="path">${esc(path)}</p><pre>${json(obj)}</pre>`;
  msg.append(d);
  const near = panes.wire.scrollHeight - panes.wire.scrollTop - panes.wire.clientHeight < 400;
  if (near) panes.wire.scrollTo({ top: panes.wire.scrollHeight, behavior: skipping ? 'auto' : 'smooth' });
  return d;
}
function showUpdate() {
  const u = fresh($('#update'));
  u.innerHTML = `
    <h2>Update check</h2>
    <p class="label">Update check, a convenience: searched the web for material published since June 30, 2026. Finding nothing does not mean nothing has changed.</p>
    <p class="summary"><span class="whose">Claude’s summary of what the search found</span>[Sample summary.] Two sources published after the corpus’s coverage date mention a pending petition on a related question about location data. None reports a new Supreme Court decision on this question.</p>
    <ul>${LINKS.map(([href, t, pub]) => `<li><a href="${href}" rel="noopener">${esc(t)}</a><span>${esc(pub)}</span></li>`).join('')}</ul>
    <dl class="params" aria-label="Parameters Claude chose">
      <dt>query</dt><dd>${esc(WEB.query)}</dd>
      <dt>published after</dt><dd>${WEB.published_after}</dd>
      <dt>published before</dt><dd>not set</dd>
      <dt>category</dt><dd>${WEB.category}</dd>
      <dt>include domains</dt><dd>not set</dd>
      <dt>exclude domains</dt><dd>not set</dd>
      <dt>search type</dt><dd>${WEB.search_type}</dd>
      <dt>results</dt><dd>${WEB.num_results} (the server allows up to 10)</dd>
    </dl>
    <p class="anno"><code class="code" data-wire="w12">${callLine('search_web_updates', WEB, 400)}</code></p>`;
  const near = panes.research.scrollHeight - panes.research.scrollTop - panes.research.clientHeight < 260;
  if (near) panes.research.scrollTo({ top: panes.research.scrollHeight, behavior: skipping ? 'auto' : 'smooth' });
}

// ---------- the run ----------
let runId = 0, skipping = false, playing = false;
const STALE = Symbol('stale');
const sleep = ms => skipping ? Promise.resolve() : new Promise(r => setTimeout(r, ms));

function reset() {
  for (const id in P) delete P[id].verdictShown;
  stepsEl.replaceChildren(); passagesEl.replaceChildren(); wireEl.replaceChildren();
  $('#update').replaceChildren(); $('#answer').replaceChildren();
  $('#after').classList.remove('on');
  $('#skip').hidden = false;
  Object.values(panes).forEach(p => p.scrollTo(0, 0));
  counts();
  clearThread(true);
}

async function play(question) {
  const my = ++runId;
  skipping = false;
  playing = true;
  const wait = async ms => { await sleep(ms); if (my !== runId) throw STALE; };
  reset();
  let req = 1, round = 0;
  const working = () => status(`Working. Tool round ${round} of up to 12.`, true);

  status('Working. Sending the question.', true);
  addWire('w1', 'sent', `Request ${req}`, 'POST /v1/messages', [
    { path: 'body (tool definitions shortened)', obj: { model: MODEL, max_tokens: 4096, tools: [{ name: 'search_corpus' }, { name: 'review_passages' }, { name: 'search_web_updates' }, { name: 'submit_answer' }], messages: [{ role: 'user', content: question }] } },
  ]);

  // a corpus search, then a review of what came back
  async function searchAndReview(q, ids, say, wSearch, wResult, wReview, wReviewResult, toolSearch, toolReview) {
    await wait(900);
    round++; working();
    const s = addStep({ title: 'Searching the corpus', say, query: QUERIES[q], code: ['search_corpus', { query: QUERIES[q] }], wire: wSearch });
    addWire(wSearch, 'recv', `Response ${req}`, 'stop_reason: tool_use', [
      { path: 'content[0]', obj: { type: 'text', text: say } },
      { path: 'content[1]', obj: { type: 'tool_use', id: toolSearch, name: 'search_corpus', input: { query: QUERIES[q] } } },
    ]);
    await wait(1000);
    for (const id of ids) { addCard(id); await wait(220); }
    finish(s, 'Searched the corpus', `${ids.length} passages returned`, ids);
    req++;
    addWire(wResult, 'sent', `Request ${req}`, 'tool_result, new in this request', ids.map((id, i) => (
      { id: 'wr-' + id, path: `messages[-1].content[0].content[${i}]`, obj: result(id) })));

    await wait(900);
    round++; working();
    const decisions = ids.map(id => ({ passage: id, keep: P[id].keep, reason: P[id].reason }));
    const r = addStep({ title: `Reviewing ${ids.length} passages`, code: ['review_passages', { decisions }], wire: wReview });
    addWire(wReview, 'recv', `Response ${req}`, 'stop_reason: tool_use', [
      { path: 'content[0]', obj: { type: 'tool_use', id: toolReview, name: 'review_passages', input: { decisions } } },
    ]);
    await wait(500);
    for (const id of ids) { verdict(id); await wait(450); }
    const k = ids.filter(id => P[id].keep).length;
    finish(r, `Reviewed ${ids.length} passages`, `Kept ${k}, discarded ${ids.length - k}`, ids);
    req++;
    addWire(wReviewResult, 'sent', `Request ${req}`, 'tool_result, new in this request', [
      { path: 'messages[-1].content[0]', obj: { type: 'tool_result', tool_use_id: toolReview, content: `Recorded: kept ${k}, discarded ${ids.length - k}.` } },
    ]);
  }

  await searchAndReview(0, ['P-01', 'P-02', 'P-03', 'P-04'], 'I’ll start with the cases on records held by third parties.', 'w2', 'w3', 'w4', 'w5', 'toolu_s01', 'toolu_s02');
  await searchAndReview(1, ['P-05', 'P-06', 'P-07'], 'Now the newer cases on location data.', 'w6', 'w7', 'w8', 'w9', 'toolu_s03', 'toolu_s04');

  // a submit the server refuses
  await wait(900);
  round++; working();
  let s = addStep({ title: 'Submitting the answer', say: 'I have enough to answer.', code: ['submit_answer', { kept: KEPT }], wire: 'w10' });
  addWire('w10', 'recv', `Response ${req}`, 'stop_reason: tool_use', [
    { path: 'content[0]', obj: { type: 'text', text: 'I have enough to answer.' } },
    { path: 'content[1]', obj: { type: 'tool_use', id: 'toolu_s05', name: 'submit_answer', input: { kept: KEPT } } },
  ]);
  await wait(900);
  const refusal = 'Not accepted: no update check has been run. Run one, or explain why it isn’t needed, then resubmit.';
  finish(s, 'Submit not accepted', `submit_answer with ${KEPT.join(', ')}`, null, true);
  s.querySelector('.meta').after(el('p', 'refused', esc(refusal)));
  req++;
  addWire('w11', 'sent', `Request ${req}`, 'tool_result, new in this request', [
    { path: 'messages[-1].content[0]', obj: { type: 'tool_result', tool_use_id: 'toolu_s05', is_error: true, content: refusal } },
  ]);

  // the update check
  await wait(1000);
  round++; working();
  const sayWeb = 'Checking for anything published after the corpus’s coverage date.';
  s = addStep({ title: 'Checking the web for later developments', say: sayWeb, meta: `Published after ${WEB.published_after}, ${WEB.category}, up to ${WEB.num_results} results`, code: ['search_web_updates', WEB], wire: 'w12' });
  addWire('w12', 'recv', `Response ${req}`, 'stop_reason: tool_use', [
    { path: 'content[0]', obj: { type: 'text', text: sayWeb } },
    { path: 'content[1]', obj: { type: 'tool_use', id: 'toolu_s06', name: 'search_web_updates', input: WEB } },
  ]);
  await wait(1400);
  finish(s, 'Checked the web', '3 sources returned, linked below and never quoted');
  showUpdate();
  req++;
  addWire('w13', 'sent', `Request ${req}`, 'tool_result, page text withheld here', LINKS.map(([href, t], i) => (
    { path: `messages[-1].content[0].content[${i}]`, obj: { type: 'search_result', source: href, title: t, content: [{ type: 'text', text: '(page text is not shown on this page)' }], citations: { enabled: true } } })));

  // the accepted submit
  await wait(1000);
  round++; working();
  s = addStep({ title: 'Submitting the answer', code: ['submit_answer', { kept: KEPT }], wire: 'w14' });
  addWire('w14', 'recv', `Response ${req}`, 'stop_reason: tool_use', [
    { path: 'content[0]', obj: { type: 'tool_use', id: 'toolu_s07', name: 'submit_answer', input: { kept: KEPT } } },
  ]);
  await wait(700);
  finish(s, 'Submitted the answer', `Accepted with ${KEPT.join(', ')}`);
  req++;
  addWire('w15', 'sent', `Request ${req}`, 'composition call: no tools', [
    { path: 'body (shortened)', obj: { model: MODEL, max_tokens: 2048, system: '(instructions for writing the answer)', messages: [{ role: 'user', content: [...KEPT.map(id => ({ type: 'search_result', source: source(id), title: title(id), content: P[id].blocks.map(() => ({ type: 'text', text: '…' })), citations: { enabled: true } })), { type: 'text', text: question }] }] } },
  ]);

  // composition: the answer streams, and each content block lands on the wire as it completes
  await wait(900);
  status('Working. Writing the answer.', true);
  s = addStep({ title: `Writing the answer from ${KEPT.length} kept passages`, meta: 'No tools in this call, so the only sources Claude can cite are the kept passages.' });
  const ans = fresh($('#answer'));
  ans.innerHTML = '<h2>Answer</h2><p class="by">Written by Claude from the kept passages. A sample answer about fictional cases.</p><div class="prose"></div>';
  const prose = ans.querySelector('.prose');
  const resp = addWire('w16', 'recv', `Response ${req}`, 'stop_reason: end_turn', []);
  let para = prose.appendChild(el('p')), block = 0, newPara = false;
  for (const b of ANSWER) {
    if (b.para) { para = prose.appendChild(el('p')); newPara = true; continue; }
    if (b.tag) para.append(el('span', 'synth-tag', 'Claude’s synthesis, no source'), ' ');
    const c = b.cite;
    const span = el('span', c ? `cited ${HUE[c.p]}` : 'synth');
    if (c) span.dataset.c = c.k;
    para.append(span);
    span.classList.add('caret');
    for (const tok of b.text.split(/(\s+)/)) {
      span.textContent += tok;
      if (!skipping && tok.trim()) await wait(32); else if (my !== runId) throw STALE;
    }
    span.classList.remove('caret');
    const i = block++;
    span.innerHTML = fmt(b.text) + (c ? ` <span class="pill">${c.p}</span>` : '') +
      `<span class="blk anno" data-wire="${c ? 'wc-' + c.k : 'w16'}">content[${i}], ${c ? `cites ${c.p} blocks [${c.start}:${c.end}]` : 'no citations'}</span>`;
    const text = (newPara ? '\n\n' : '') + b.text;
    newPara = false;
    addPart(resp, c
      ? { id: 'wc-' + c.k, hue: HUE[c.p], path: `content[${i}]`, obj: { type: 'text', text, citations: [{ type: 'search_result_location', source: source(c.p), title: title(c.p), cited_text: citedText(c), search_result_index: KEPT.indexOf(c.p), start_block_index: c.start, end_block_index: c.end }] } }
      : { path: `content[${i}]`, obj: { type: 'text', text } });
    await wait(120);
  }
  finish(s, 'Wrote the answer', `Cites ${KEPT.length} kept passages. Every citation points to a passage you watched Claude keep.`);

  // our own check, no model involved
  await wait(700);
  s = addStep({ title: 'Checking case names against the corpus' });
  await wait(800);
  finish(s, 'Checked case names', '1 name not found in the corpus');
  const ph = prose.querySelector('.phantom');
  ph.classList.add('flagged');
  ph.closest('p').after(el('p', 'flag-note', '<strong>Case name not found in the corpus:</strong> <i>Phantom v. United States</i>. It may be misnamed or outside the corpus; check it before relying on it.'));
  addWire('w17', 'local', 'Name check', 'no model call', [
    { path: 'result', obj: { checked: CASES, resolved: 3, not_found: ['Phantom v. United States'] } },
  ]);

  status(`Finished in ${stepsEl.children.length} steps: ${round} tool rounds, the answer, and a name check.`, false);
  playing = false;
  $('#skip').hidden = true;
  $('#after').classList.add('on');
  if (!skipping) panes.research.scrollTo({ top: panes.research.scrollHeight, behavior: 'smooth' });
}

function start(question, recorded) {
  $('#asked-q').textContent = question;
  $('#run-label').textContent = recorded
    ? 'Recording made Oct 23, 2026. Sample run, fictional cases.'
    : 'Prototype: every question plays the same sample run.';
  body.dataset.pane = 'research';
  swap('run');
  play(question).catch(e => { if (e !== STALE) throw e; });
}

// ---------- threads: sentence to cited range to citation block ----------
const svg = $('#threads');
let active = null; // { p, k, pinned }: a passage, and the citation into it if there is one

function unlight() {
  document.querySelectorAll('.lit').forEach(e => e.classList.remove('lit'));
  document.querySelectorAll('.card.focus').forEach(e => e.classList.remove('focus'));
  document.querySelectorAll('.sb.hit').forEach(e => e.classList.remove('hit'));
}
function clearThread(force) {
  if (active && active.pinned && !force) return;
  unlight();
  active = null;
  svg.replaceChildren();
}
// light citation k: the sentence that carries it, the cited blocks in context, and its block on the wire
function light(p, k, pinned, fresh = true) {
  unlight();
  active = { p, k, pinned };
  const card = $('#src-' + p);
  if (card) {
    card.classList.add('lit');
    if (k != null) {
      card.classList.add('focus');
      const c = CITES[k];
      card.querySelectorAll('.sb').forEach(sb => { const i = +sb.dataset.i; if (i >= c.start && i < c.end) sb.classList.add('hit'); });
    }
  }
  if (k != null) document.querySelectorAll(`.cited[data-c="${k}"]`).forEach(e => e.classList.add('lit'));
  const part = wirePart();
  part && part.classList.add('lit');
  draw(fresh);
}
function wirePart() {
  if (!active) return null;
  return (active.k != null && document.getElementById('wc-' + active.k)) || document.getElementById('wr-' + active.p);
}
function firstCite(p) {
  const c = CITES.find(c => c.p === p);
  return c && document.querySelector(`.cited[data-c="${c.k}"]`) ? c.k : null;
}
function clampY(y, e) {
  const col = e.closest('.col'), r = col.getBoundingClientRect();
  const head = col.querySelector('.col-head');
  const top = head ? head.getBoundingClientRect().bottom : r.top;
  return Math.min(Math.max(y, top + 10), r.bottom - 10);
}
function curve(x1, y1, x2, y2, hue, fresh) {
  const dx = Math.max(40, (x2 - x1) / 2);
  const p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  p.setAttribute('d', `M${x1},${y1} C${x1 + dx},${y1} ${x2 - dx},${y2} ${x2},${y2}`);
  p.setAttribute('stroke', hue);
  svg.append(p);
  if (fresh) { p.style.setProperty('--len', p.getTotalLength()); p.classList.add('draw'); }
  for (const [x, y] of [[x1, y1], [x2, y2]]) {
    const c = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    c.setAttribute('cx', x); c.setAttribute('cy', y); c.setAttribute('r', 4); c.setAttribute('fill', hue);
    svg.append(c);
  }
}
function draw(fresh) {
  svg.replaceChildren();
  if (!active || phone()) return;
  const card = $('#src-' + active.p);
  if (!visible(card)) return;
  const hue = getComputedStyle(card).getPropertyValue('--hue').trim() || '#5d6474';
  const cr = card.getBoundingClientRect();
  // land on the first line of the cited range, or the card's top when nothing is cited yet
  const hit = card.querySelector('.sb.hit');
  const hr = hit && hit.getClientRects()[0];
  const cy = clampY(hr ? hr.top + hr.height / 2 : cr.top + 22, card);
  const s = active.k != null && document.querySelector(`.cited[data-c="${active.k}"]`);
  if (visible(s)) {
    const rects = (s.querySelector('.pill') || s).getClientRects();
    const a = rects[rects.length - 1];
    curve(a.right + 2, clampY(a.top + a.height / 2, s), cr.left, cy, hue, fresh);
  }
  const part = wirePart();
  if (visible(part)) {
    const pr = part.getBoundingClientRect();
    curve(cr.right, cy, pr.left, clampY(pr.top + 14, part), hue, fresh);
  }
}
let queued = false;
function redraw() {
  if (queued || !active) return;
  queued = true;
  requestAnimationFrame(() => { queued = false; draw(false); });
}
addEventListener('scroll', redraw, true);
addEventListener('resize', redraw);

function focusSource(p, k) {
  if (phone()) setPane('sources');
  light(p, k, true);
  const card = $('#src-' + p);
  centerIn(card.querySelector('.sb.hit') || card, !phone());
  const part = wirePart();
  if (visible(part)) centerIn(part);
}

// ---------- events ----------
$('#ask').addEventListener('submit', e => {
  e.preventDefault();
  const q = $('#q').value.trim() || $('#q').placeholder;
  start(q, false);
});
$('#q').addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); $('#ask').requestSubmit(); }
});
document.querySelectorAll('.recorded .chip').forEach(b => b.addEventListener('click', () => start(b.dataset.q, true)));
$('#home').addEventListener('click', () => { runId++; clearThread(true); swap('landing'); });
$('#again').addEventListener('click', () => { runId++; clearThread(true); swap('landing'); });
$('#replay').addEventListener('click', () => play($('#asked-q').textContent).catch(e => { if (e !== STALE) throw e; }));
$('#skip').addEventListener('click', () => { skipping = true; });
document.querySelectorAll('.seg button').forEach(b => b.addEventListener('click', () => setMode(b.dataset.mode)));
document.querySelectorAll('button[data-pane]').forEach(b => b.addEventListener('click', () => setPane(b.dataset.pane)));

const research = panes.research;
research.addEventListener('mouseover', e => {
  const s = e.target.closest('.cited');
  if (s && !(active && active.pinned)) { const c = CITES[s.dataset.c]; light(c.p, c.k, false); }
});
research.addEventListener('mouseout', e => {
  const s = e.target.closest('.cited');
  if (s && !s.contains(e.relatedTarget)) clearThread();
});
passagesEl.addEventListener('mouseover', e => {
  const card = e.target.closest('.card.kept');
  if (!card || (active && (active.pinned || active.p === card.dataset.id))) return;
  light(card.dataset.id, firstCite(card.dataset.id), false);
});
passagesEl.addEventListener('mouseleave', () => clearThread());

document.addEventListener('click', e => {
  const t = e.target;
  const toggle = t.closest('.toggle');
  if (toggle) {
    const card = toggle.closest('.card');
    card.classList.toggle('open');
    toggle.textContent = card.classList.contains('open') ? 'Hide passage' : 'Show passage';
    return;
  }
  const code = t.closest('[data-wire]');
  if (code && body.dataset.mode !== 'plain') {
    setMode('api');
    if (phone()) setPane('wire');
    const target = document.getElementById(code.dataset.wire);
    if (target) {
      requestAnimationFrame(() => centerIn(target));
      target.classList.add('lit');
      setTimeout(() => target.classList.remove('lit'), 1600);
    }
    return;
  }
  const s = t.closest('.cited');
  if (s) { const c = CITES[s.dataset.c]; focusSource(c.p, c.k); return; }
  const go = t.closest('[data-goto]');
  if (go) {
    const id = go.dataset.goto;
    if (P[id].verdictShown === 'kept') focusSource(id, firstCite(id));
    else { phone() && setPane('sources'); requestAnimationFrame(() => centerIn($('#src-' + id))); }
    return;
  }
  if (!t.closest('.card')) clearThread(true);
});
