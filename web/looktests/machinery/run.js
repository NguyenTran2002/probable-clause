// Prototype only. Plays one scripted sample run; there is no backend.
'use strict';

const MODEL = 'claude-sonnet-5-5';
const QUERIES = [
  'acquiring records held by a third party as a search',
  'stored location history and the warrant requirement',
];

// Each passage is the ordered list of text blocks sent in its search_result's content.
// P-01, P-05 and P-07 are sent one sentence per block; the rest as one paragraph block.
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
// Sentence-block passages cite single sentences or runs of them; paragraph-block passages
// cite the whole paragraph. One rendering path serves both.
const ANSWER = [
  { text: 'In Exemplar v. United States (1967), the majority set out the test the later cases apply.', cite: { p: 'P-01', start: 1, end: 2 } },
  { text: ' The dissent in that case read the test more narrowly.', cite: { p: 'P-02', start: 0, end: 1 } },
  { para: true },
  { text: 'Placeholder v. State of Example (1979) held that records a person hands to a third party fall outside that protection.', cite: { p: 'P-03', start: 0, end: 1 } },
  { text: ' Illustration v. United States (2026) treated the acquisition of stored location history as a search, narrowing the earlier rule for this kind of data.', cite: { p: 'P-05', start: 1, end: 3 } },
  { para: true },
  { text: 'Read in date order, the line runs from a broad test, to a third-party rule, to a narrower view of that rule for location data. Some discussions also point to Phantom v. United States.' },
  { para: true },
  { text: 'This describes what the Court held. It does not say how the holdings apply to anyone’s situation.' },
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
const root = document.documentElement;
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
  if (v === null || typeof v !== 'object' || one.length <= 84) return one;
  const pad = ind + '  ';
  if (Array.isArray(v)) return '[\n' + v.map(x => pad + pretty(x, pad)).join(',\n') + '\n' + ind + ']';
  return '{\n' + Object.entries(v).map(([k, x]) => pad + JSON.stringify(k) + ': ' + pretty(x, pad)).join(',\n') + '\n' + ind + '}';
}
const json = o => paint(pretty(o));
const source = id => `probable-clause://passages/${id}`;
const title = id => `${P[id].kase}, ${P[id].cite}, ${P[id].kind.toLowerCase()}${P[id].by ? ' by ' + P[id].by : ''}`;
const result = id => ({ type: 'search_result', source: source(id), title: title(id), content: P[id].blocks.map(text => ({ type: 'text', text })), citations: { enabled: true } });
const citedText = c => P[c.p].blocks.slice(c.start, c.end).join('');
function fmt(text) {
  let h = esc(text);
  for (const c of CASES) h = h.split(c).join(c === 'Phantom v. United States' ? `<i class="phantom">${c}</i>` : `<i>${c}</i>`);
  return h;
}

// ---------- prototype controls: palette and theme ----------
function remember(key, value) { try { localStorage.setItem(key, value); } catch (e) { /* storage may be blocked */ } }
function recall(key) { try { return localStorage.getItem(key); } catch (e) { return null; } }
function setPref(name, value) {
  root.dataset[name] = value;
  remember('pc2-' + name, value);
  document.querySelectorAll(`.proto-controls [data-${name}]`).forEach(b => b.setAttribute('aria-pressed', String(b.dataset[name] === value)));
  redraw();
}

// ---------- panes and view ----------
const panes = { thread: $('#thread-scroll'), sources: $('#pane-sources') };
const threadEl = $('#thread'), passagesEl = $('#passages');
const phone = () => matchMedia('(max-width: 759px)').matches;

function setPane(p) { body.dataset.pane = p; redraw(); }
function swap(view) {
  const go = () => { body.dataset.view = view; scrollTo(0, 0); };
  if (document.startViewTransition && !matchMedia('(prefers-reduced-motion: reduce)').matches) document.startViewTransition(go);
  else go();
}
function visible(e) { return e && e.getClientRects().length > 0; }
function paneTop(pane) {
  const head = pane.querySelector('.col-head');
  return head ? head.getBoundingClientRect().bottom : pane.getBoundingClientRect().top;
}
function inView(e) {
  const pane = e.closest('.scroller'), r = e.getBoundingClientRect();
  return r.top >= paneTop(pane) && r.bottom <= pane.getBoundingClientRect().bottom;
}
// scroll an element to the middle of its own pane (scrollIntoView on two panes at once cancels one)
function centerIn(e, smooth = true) {
  const pane = e.closest('.scroller');
  if (!pane) return;
  const pr = pane.getBoundingClientRect(), er = e.getBoundingClientRect();
  const head = pane.querySelector('.col-head');
  const offset = Math.max((head ? head.offsetHeight : 0) + 12, (pane.clientHeight - er.height) / 2);
  pane.scrollTo({ top: pane.scrollTop + er.top - pr.top - offset, behavior: smooth ? 'smooth' : 'auto' });
}
function fresh(node) {
  node.classList.add('fresh');
  setTimeout(() => node.classList.remove('fresh'), 450);
  return node;
}
// add to a pane and keep it pinned to the newest content, unless the reader scrolled away
function append(pane, parent, node) {
  fresh(node);
  const near = pane.scrollHeight - pane.scrollTop - pane.clientHeight < 260;
  parent.append(node);
  if (near) follow(pane);
  return node;
}
function follow(pane) { pane.scrollTo({ top: pane.scrollHeight, behavior: skipping ? 'auto' : 'smooth' }); }

// ---------- rendering ----------
let stepsEl = null;

function status(text, working) {
  const s = $('#status');
  s.textContent = text;
  s.classList.toggle('working', !!working);
}
function addStep({ title: t, say, query, meta }) {
  const li = el('li', 'step working');
  li.innerHTML = `<h3>${esc(t)}</h3>` +
    (say ? `<p class="say">${esc(say)}</p>` : '') +
    (query ? `<p class="query">“${esc(query)}”</p>` : '') +
    `<p class="meta">${meta ? esc(meta) : ''}</p>`;
  return append(panes.thread, stepsEl, li);
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
function cardClass(id) {
  const p = P[id], v = p.verdictShown;
  return `card ${v || 'reviewing'} ${p.keep ? HUE[id] : ''}${p.syllabus ? ' syllabus' : ''}`;
}
function cardHTML(id) {
  const p = P[id], v = p.verdictShown;
  const meta = p.syllabus ? `Decided ${p.decided}. Syllabus.` : `Decided ${p.decided}. ${p.kind} by ${p.by}, ${p.joined}.`;
  return `
    <p class="verdict"><span class="pid">${id}</span><span class="mark">${v === 'kept' ? 'Kept' : v === 'discarded' ? 'Discarded' : 'Reviewing'}</span><span class="reason">${v ? esc(p.reason) : ''}</span></p>
    <p class="case"><i>${esc(p.kase)}</i>, ${esc(p.cite)}</p>
    <p class="meta">${esc(meta)}</p>
    <div class="body">
      ${p.syllabus ? '<p class="syl-label">Syllabus, prepared by the Reporter of Decisions. It constitutes no part of the opinion of the Court.</p>' : ''}
      <p class="text">${p.blocks.map((b, i) => `<span class="sb" data-i="${i}">${esc(b)}</span>`).join('')}${p.pin ? ` <span class="pin">${esc(p.pin)}</span>` : ''}</p>
      <p class="small guarantee">This passage appears verbatim in this ${p.syllabus ? 'opinion’s syllabus' : 'opinion'}.</p>
      ${p.slip ? '<p class="slip">Slip opinion: not yet final in the U.S. Reports, and subject to formal revision.</p>' : ''}
      <p class="small">Found by “${esc(QUERIES[p.q])}”</p>
    </div>
    <div class="card-actions">
      <button type="button" class="ghost api-btn" data-api="${id}">View API calls</button>
      <button type="button" class="ghost read-btn" data-read="${id}">View source</button>
      <button type="button" class="toggle">Show passage</button>
    </div>`;
}
function addCard(id) {
  const li = el('li', cardClass(id), cardHTML(id));
  li.id = 'src-' + id;
  li.dataset.id = id;
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
function showUpdate() {
  const u = el('section', 'update');
  u.setAttribute('aria-label', 'Update check');
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
    </dl>`;
  append(panes.thread, threadEl, u);
}

// ---------- the API record behind each passage, shown in the modal ----------
// TRACE[id] lists the exchanges that touched passage id, in order, as the run makes them.
let TRACE = {};
function trace(ids, entry) { for (const id of ids) (TRACE[id] = TRACE[id] || []).push(typeof entry === 'function' ? entry(id) : entry); }

const dlg = $('#api');
// one line that says what an exchange carried, shown while its row is closed
function preview(o) {
  if (o.type === 'tool_use') return `${o.name}(${JSON.stringify(o.input)})`;
  if (o.type === 'search_result') return `search_result: ${o.content.length} text block${o.content.length > 1 ? 's' : ''}`;
  if (o.type === 'text' && o.citations) return JSON.stringify({ cited_text: o.citations[0].cited_text });
  return JSON.stringify(o);
}
function openApi(id) {
  const p = P[id];
  $('#api-title').textContent = `${id}: the API calls behind this source`;
  const card = el('div', cardClass(id), cardHTML(id));
  const ks = CITES.filter(c => c.p === id && document.querySelector(`.cited[data-c="${c.k}"]`));
  if (ks.length) {
    card.classList.add('focus');
    card.querySelectorAll('.sb').forEach(sb => { const i = +sb.dataset.i; if (ks.some(c => i >= c.start && i < c.end)) sb.classList.add('hit'); });
  }
  $('#api-card').replaceChildren(card);
  const steps = (TRACE[id] || []).map(x => `
    <li><details${x.open ? ' open' : ''}>
      <summary class="x-head"><b>${esc(x.title)}</b><span>${esc(x.where)}</span><code class="x-preview">${paint(preview(x.parts[x.parts.length - 1].obj))}</code></summary>
      <div class="x-body">${x.parts.map(part => `<p class="path">${esc(part.path)}</p><pre class="${part.hue ? 'cite ' + part.hue : ''}">${json(part.obj)}</pre>`).join('')}</div>
      ${x.note ? `<p class="x-note">${esc(x.note)}</p>` : ''}
    </details></li>`);
  if (p.verdictShown === 'discarded') steps.push(`<li><p class="x-note">Not sent to the composition call. Claude discarded this passage, so the call that writes the answer never saw it and cannot cite it.</p></li>`);
  if (playing) steps.push(`<li><p class="x-note">The run is still working. More exchanges appear here as it goes.</p></li>`);
  $('#api-steps').innerHTML = steps.join('');
  dlg.querySelector('.dlg-wire').scrollTop = 0;
  dlg.showModal();
}
// both modals close from their Close button or a click on the backdrop
for (const d of document.querySelectorAll('dialog')) {
  d.querySelector('[data-close]').addEventListener('click', () => d.close());
  d.addEventListener('click', e => { if (e.target === d) d.close(); });
}

// ---------- the source reader: the whole opinion, opened at the excerpt ----------
// Mock text until Phase 1's corpus lands: every paragraph but the retrieved one is a labelled placeholder.
const TOPICS = ['the facts and the proceedings below', 'the question presented', 'the earlier cases on the subject',
  'the parties’ arguments', 'the history of the warrant requirement', 'how the rule applies to records held by others',
  'the limits of the holding', 'the response to the other opinions', 'the practical consequences', 'the disposition'];
const HEADINGS = { 'Majority opinion': 'Opinion of the Court', 'Dissent': 'Dissenting opinion', 'Concurrence': 'Concurring opinion', 'Plurality opinion': 'Plurality opinion', 'Syllabus': 'Syllabus' };
function byline(p) {
  const names = (p.joined || '').replace(/^joined by /, '');
  const one = !/,| and /.test(names);
  if (p.kind === 'Majority opinion') return `${p.by} delivered the opinion of the Court, in which ${names} joined.`;
  if (p.kind === 'Plurality opinion') return `${p.by} announced the judgment of the Court and delivered an opinion, in which ${names} join.`;
  const role = p.kind === 'Dissent' ? 'dissenting' : 'concurring';
  return names === 'no other Justice' ? `${p.by}, ${role}.` : `${p.by}, with whom ${names} ${one ? 'joins' : 'join'}, ${role}.`;
}
function readerHTML(id) {
  const p = P[id];
  const n = p.syllabus ? 6 : 14, at = p.syllabus ? 2 : 6;
  // pages turn every two paragraphs, placed so the excerpt lands on its pinpoint page
  const pin = p.pin && +p.pin.match(/(\d+)$/)[1];
  const pageWord = p.slip ? 'Slip opinion page' : 'U.S. Reports page';
  const page = i => pin - Math.floor(at / 2) + Math.floor(i / 2);
  const ks = CITES.filter(c => c.p === id && document.querySelector(`.cited[data-c="${c.k}"]`));
  const label = ks.length ? `The passage Claude retrieved, ${id}. The sentences the answer cites are lit.` : `The passage Claude retrieved, ${id}${p.verdictShown === 'discarded' ? ', later discarded' : ''}.`;
  let h = `<div class="reader-text"><h3>${HEADINGS[p.kind]}</h3>` +
    (p.syllabus ? '<p class="syl-label">Prepared by the Reporter of Decisions. It constitutes no part of the opinion of the Court.</p>' : `<p class="byline">${esc(byline(p))}</p>`);
  for (let i = 0; i < n; i++) {
    const marker = pin && i % 2 === 0 ? `<span class="pg"><span class="pg-word">${pageWord} </span>${page(i)}</span>` : '';
    if (i === at) {
      h += `<div class="excerpt ${HUE[id] && p.keep ? HUE[id] : ''}${ks.length ? ' focus' : ''}" id="reader-excerpt">${marker}
        <p class="ex-label">${esc(label)}</p>
        <p class="ex-text">${p.blocks.map((b, j) => `<span class="sb${ks.some(c => j >= c.start && j < c.end) ? ' hit' : ''}">${esc(b)}</span>`).join('')}</p></div>`;
    } else {
      h += `<p>${marker}[Sample paragraph ${i + 1} of ${n}, standing in for text on ${TOPICS[i % TOPICS.length]}. Phase 1 supplies the verbatim ${p.syllabus ? 'syllabus' : 'opinion'}.]</p>`;
    }
  }
  h += `</div><div class="reader-foot">
    <p>${p.slip ? 'Slip opinion: not yet final in the U.S. Reports, and subject to formal revision. ' : ''}The text is normalised from the official opinion and is unofficial; the official text is the U.S. Reports.</p>
    <p>Opinion text via CourtListener, from Free Law Project.</p></div>`;
  return h;
}
const reader = $('#reader'), readerBody = $('#reader-body');
function toExcerpt(smooth) {
  const ex = $('#reader-excerpt');
  readerBody.scrollTo({ top: ex.offsetTop - Math.max(24, (readerBody.clientHeight - ex.offsetHeight) / 2), behavior: smooth ? 'smooth' : 'auto' });
}
function openReader(id) {
  const p = P[id];
  $('#reader-title').innerHTML = `<i>${esc(p.kase)}</i>, ${esc(p.cite)}`;
  $('#reader-sub').innerHTML = `${HEADINGS[p.kind]}. Decided ${esc(p.decided)}. Opened at <span class="nw">${id}</span>.`;
  readerBody.innerHTML = readerHTML(id);
  reader.showModal();
  requestAnimationFrame(() => toExcerpt(false));
}
$('#reader-jump').addEventListener('click', () => toExcerpt(true));

// ---------- the run ----------
let runId = 0, skipping = false, playing = false;
const STALE = Symbol('stale');
const sleep = ms => skipping ? Promise.resolve() : new Promise(r => setTimeout(r, ms));

function reset() {
  for (const id in P) delete P[id].verdictShown;
  TRACE = {};
  threadEl.replaceChildren();
  passagesEl.replaceChildren();
  Object.values(panes).forEach(p => p.scrollTo(0, 0));
  counts();
  clearThread(true);
}
function setPlaying(on) {
  playing = on;
  body.classList.toggle('playing', on);
  const q2 = $('#q2');
  q2.disabled = on;
  q2.placeholder = on ? 'Working…' : 'Ask another question';
}

async function play(question, recorded) {
  const my = ++runId;
  skipping = false;
  setPlaying(true);
  const wait = async ms => { await sleep(ms); if (my !== runId) throw STALE; };
  reset();

  const ask = el('div', 'ask-msg');
  ask.innerHTML = `<p class="bubble"></p><p class="caption"></p>`;
  ask.querySelector('.bubble').textContent = question;
  ask.querySelector('.caption').textContent = recorded
    ? 'Recording made Oct 23, 2026. Sample run, fictional cases.'
    : 'Prototype: every question plays the same sample run.';
  append(panes.thread, threadEl, ask);
  stepsEl = el('ol', 'steps');
  threadEl.append(stepsEl);

  let req = 1, round = 0;
  const working = () => status(`Working. Tool round ${round} of up to 12.`, true);
  status('Working. Sending the question.', true);

  // a corpus search, then a review of what came back
  async function searchAndReview(q, ids, say, toolSearch, toolReview) {
    await wait(900);
    round++; working();
    const s = addStep({ title: 'Searching the corpus', say, query: QUERIES[q] });
    const call = { type: 'tool_use', id: toolSearch, name: 'search_corpus', input: { query: QUERIES[q] } };
    trace(ids, { title: 'Claude asked for a corpus search', where: `Received, response ${req}`, parts: [{ path: 'content[1]', obj: call }] });
    await wait(1000);
    for (const id of ids) { addCard(id); await wait(220); }
    finish(s, 'Searched the corpus', `${ids.length} passages returned`, ids);
    req++;
    trace(ids, id => ({ title: 'Our server returned this passage', where: `Sent, request ${req}`, parts: [{ path: `messages[-1].content[0].content[${ids.indexOf(id)}]`, obj: result(id) }], note: `${P[id].blocks.length} text block${P[id].blocks.length > 1 ? 's' : ''}. Each block is the smallest piece Claude can cite.` }));

    await wait(900);
    round++; working();
    const decisions = ids.map(id => ({ passage: id, keep: P[id].keep, reason: P[id].reason }));
    const r = addStep({ title: `Reviewing ${ids.length} passages` });
    trace(ids, id => ({ open: !P[id].keep, title: P[id].keep ? 'Claude kept it' : 'Claude discarded it', where: `Received, response ${req}`, parts: [{ path: `content[0].input.decisions[${ids.indexOf(id)}]  (review_passages, ${toolReview})`, obj: decisions[ids.indexOf(id)] }] }));
    await wait(500);
    for (const id of ids) { verdict(id); await wait(450); }
    const k = ids.filter(id => P[id].keep).length;
    finish(r, `Reviewed ${ids.length} passages`, `Kept ${k}, discarded ${ids.length - k}`, ids);
    req++;
  }

  await searchAndReview(0, ['P-01', 'P-02', 'P-03', 'P-04'], 'I’ll start with the cases on records held by third parties.', 'toolu_s01', 'toolu_s02');
  await searchAndReview(1, ['P-05', 'P-06', 'P-07'], 'Now the newer cases on location data.', 'toolu_s03', 'toolu_s04');

  // a submit the server refuses
  await wait(900);
  round++; working();
  let s = addStep({ title: 'Submitting the answer', say: 'I have enough to answer.' });
  await wait(900);
  const refusal = 'Not accepted: no update check has been run. Run one, or explain why it isn’t needed, then resubmit.';
  finish(s, 'Submit not accepted', `submit_answer with ${KEPT.join(', ')}`, null, true);
  s.querySelector('.meta').after(el('p', 'refused', esc(refusal)));
  trace(KEPT, { title: 'Claude submitted it; the server refused the submit', where: `Response ${req}, then request ${req + 1}`, parts: [
    { path: `response ${req}: content[1]`, obj: { type: 'tool_use', id: 'toolu_s05', name: 'submit_answer', input: { kept: KEPT } } },
    { path: `request ${req + 1}: messages[-1].content[0]`, obj: { type: 'tool_result', tool_use_id: 'toolu_s05', is_error: true, content: refusal } },
  ] });
  req++;

  // the update check
  await wait(1000);
  round++; working();
  s = addStep({ title: 'Checking the web for later developments', say: 'Checking for anything published after the corpus’s coverage date.', meta: `Published after ${WEB.published_after}, ${WEB.category}, up to ${WEB.num_results} results` });
  await wait(1400);
  finish(s, 'Checked the web', '3 sources returned, linked below and never quoted');
  showUpdate();
  req++;

  // the accepted submit
  await wait(1000);
  round++; working();
  s = addStep({ title: 'Submitting the answer' });
  await wait(700);
  finish(s, 'Submitted the answer', `Accepted with ${KEPT.join(', ')}`);
  trace(KEPT, { title: 'Claude submitted it again; accepted', where: `Received, response ${req}`, parts: [{ path: 'content[0]', obj: { type: 'tool_use', id: 'toolu_s07', name: 'submit_answer', input: { kept: KEPT } } }] });
  req++;
  trace(KEPT, id => ({ title: 'Sent to the composition call, which has no tools', where: `Sent, request ${req}`, parts: [{ path: `messages[0].content[${KEPT.indexOf(id)}]`, obj: result(id) }], note: `Its position makes it search_result_index ${KEPT.indexOf(id)} in this call’s citations.` }));

  // composition: the answer streams into the conversation
  await wait(900);
  status('Working. Writing the answer.', true);
  s = addStep({ title: `Writing the answer from ${KEPT.length} kept passages`, meta: 'No tools in this call, so the only sources Claude can cite are the kept passages.' });
  const ans = el('section', 'answer');
  ans.setAttribute('aria-label', 'Answer');
  ans.innerHTML = `<h2>Answer</h2>
    <p class="by">Written by Claude from the kept passages. A sample answer about fictional cases.</p>
    <p class="key"><span class="key-cited">Underlined sentences</span> rest on a passage Claude kept; hover or tap one to see the exact text it cites. Sentences without a line are Claude’s own synthesis and have no source.</p>
    <div class="prose"></div>`;
  append(panes.thread, threadEl, ans);
  const prose = ans.querySelector('.prose');
  let para = prose.appendChild(el('p')), block = 0, newPara = false;
  for (const b of ANSWER) {
    if (b.para) { para = prose.appendChild(el('p')); newPara = true; continue; }
    const c = b.cite;
    const span = el('span', c ? `cited ${HUE[c.p]}` : 'synth');
    para.append(span);
    span.classList.add('caret');
    for (const tok of b.text.split(/(\s+)/)) {
      span.textContent += tok;
      if (!skipping && tok.trim()) await wait(32); else if (my !== runId) throw STALE;
      if (!skipping) follow(panes.thread);
    }
    span.classList.remove('caret');
    const i = block++;
    span.innerHTML = fmt(b.text) + (c ? ` <span class="pill">${c.p}</span>` : '');
    if (c) {
      span.dataset.c = c.k;
      const text = (newPara ? '\n\n' : '') + b.text;
      trace([c.p], { open: true, title: 'Claude cited it in the answer', where: `Received, response ${req}`, parts: [{ path: `content[${i}]`, hue: HUE[c.p], obj: { type: 'text', text, citations: [{ type: 'search_result_location', source: source(c.p), title: title(c.p), cited_text: citedText(c), search_result_index: KEPT.indexOf(c.p), start_block_index: c.start, end_block_index: c.end }] } }], note: `cited_text is blocks ${c.start} to ${c.end - 1} of this passage, word for word.` });
    }
    newPara = false;
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

  status(`Finished in ${stepsEl.children.length} steps: ${round} tool rounds, the answer, and a name check.`, false);
  setPlaying(false);
  follow(panes.thread);
}

function run(question, recorded) {
  play(question, recorded).catch(e => { if (e !== STALE) throw e; });
}
function start(question, recorded) {
  body.dataset.pane = 'thread';
  swap('run');
  run(question, recorded);
}
function stop() {
  runId++;
  setPlaying(false);
  clearThread(true);
}

// ---------- threads: sentence to cited range ----------
const svg = $('#threads');
let active = null; // { p, k, pinned }: a passage, and the citation into it if there is one

function unlight() {
  document.querySelectorAll('.lit').forEach(e => e.classList.remove('lit'));
  document.querySelectorAll('#passages .card.focus').forEach(e => e.classList.remove('focus'));
  document.querySelectorAll('#passages .sb.hit').forEach(e => e.classList.remove('hit'));
}
function clearThread(force) {
  if (active && active.pinned && !force) return;
  unlight();
  active = null;
  svg.replaceChildren();
}
// light citation k: the sentence that carries it, and the cited blocks in the context of their paragraph
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
  draw(fresh);
}
function target(p) {
  const card = $('#src-' + p);
  return card && (card.querySelector('.sb.hit') || card);
}
function firstCite(p) {
  const c = CITES.find(c => c.p === p);
  return c && document.querySelector(`.cited[data-c="${c.k}"]`) ? c.k : null;
}
function clampY(y, e) {
  const pane = e.closest('.scroller');
  return Math.min(Math.max(y, paneTop(pane) + 10), pane.getBoundingClientRect().bottom - 10);
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
  if (!active || active.k == null || phone()) return;
  const card = $('#src-' + active.p);
  const s = document.querySelector(`.cited[data-c="${active.k}"]`);
  if (!visible(card) || !visible(s)) return;
  const hue = getComputedStyle(card).getPropertyValue('--hue').trim();
  const cr = card.getBoundingClientRect();
  const hit = card.querySelector('.sb.hit');
  const hr = hit && hit.getClientRects()[0];
  const cy = clampY(hr ? hr.top + hr.height / 2 : cr.top + 22, card);
  // start at the answer column's right edge, level with the sentence's tag, so the line never crosses text
  const rects = (s.querySelector('.pill') || s).getClientRects();
  const a = rects[rects.length - 1];
  const x0 = (s.closest('.prose') || s).getBoundingClientRect().right + 8;
  curve(x0, clampY(a.top + a.height / 2, s), cr.left, cy, hue, fresh);
}
let queued = false;
function redraw() {
  if (queued || !active) return;
  queued = true;
  requestAnimationFrame(() => { queued = false; draw(false); });
}
addEventListener('scroll', redraw, true);
addEventListener('resize', redraw);

// bring the cited range into view in the sources pane, without moving it if it already shows
function reveal(p, smooth = true) {
  const t = target(p);
  if (t && visible(t) && !inView(t)) centerIn(t, smooth);
}
function focusSource(p, k) {
  if (phone()) setPane('sources');
  light(p, k, true);
  const t = target(p);
  if (t) centerIn(t, !phone());
}

// ---------- events ----------
$('#ask').addEventListener('submit', e => {
  e.preventDefault();
  const q = $('#q').value.trim() || $('#q').placeholder;
  start(q, false);
});
$('#composer').addEventListener('submit', e => {
  e.preventDefault();
  const q = $('#q2').value.trim();
  if (!q || playing) return;
  $('#q2').value = '';
  run(q, false);
});
for (const id of ['#q', '#q2']) {
  $(id).addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); e.target.form.requestSubmit(); }
  });
}
document.querySelectorAll('.recorded .chip').forEach(b => b.addEventListener('click', () => start(b.dataset.q, true)));
$('#home').addEventListener('click', () => { stop(); swap('landing'); });
$('#skip').addEventListener('click', () => { skipping = true; });
document.querySelectorAll('.tabs button[data-pane]').forEach(b => b.addEventListener('click', () => setPane(b.dataset.pane)));

threadEl.addEventListener('mouseover', e => {
  const s = e.target.closest('.cited');
  if (!s || (active && active.pinned)) return;
  const c = CITES[s.dataset.c];
  if (active && active.k === c.k) return;
  light(c.p, c.k, false);
  reveal(c.p);
});
threadEl.addEventListener('mouseout', e => {
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
  if (t.closest('dialog')) return;
  const api = t.closest('[data-api]');
  if (api) { openApi(api.dataset.api); return; }
  const read = t.closest('[data-read]');
  if (read) { openReader(read.dataset.read); return; }
  const toggle = t.closest('.toggle');
  if (toggle) {
    const card = toggle.closest('.card');
    card.classList.toggle('open');
    toggle.textContent = card.classList.contains('open') ? 'Hide passage' : 'Show passage';
    return;
  }
  const s = t.closest('.cited');
  if (s) { const c = CITES[s.dataset.c]; focusSource(c.p, c.k); return; }
  const go = t.closest('[data-goto]');
  if (go) {
    const id = go.dataset.goto;
    if (P[id].verdictShown === 'kept' && firstCite(id) != null) focusSource(id, firstCite(id));
    else { if (phone()) setPane('sources'); requestAnimationFrame(() => centerIn($('#src-' + id))); }
    return;
  }
  if (!t.closest('.card')) clearThread(true);
});

for (const name of ['palette', 'theme']) {
  const saved = recall('pc2-' + name);
  if (saved) setPref(name, saved);
  document.querySelectorAll(`.proto-controls [data-${name}]`).forEach(b => b.addEventListener('click', () => setPref(name, b.dataset[name])));
}
