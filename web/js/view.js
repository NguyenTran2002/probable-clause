// The run screen: the conversation (the question, the step log, the answer, the later-developments box) and the sources
// panel, fed one event at a time through the run model. Live runs, reattached runs and replays all play here.

import { h, $, $$, clear, fresh, setQuiet } from './dom.js';
import { createRun, apply, answerLabels, hueOf, tagsFor } from './model.js';
import { createSteps } from './steps.js';
import { createSources, lightSentences, unlightSentences } from './sources.js';
import { renderBand, inkIn } from './band.js';
import { renderCosts } from './costs.js';
import { createApiModal } from './apicalls.js';
import { createReader } from './reader.js';
import { layoutAnswer, mount } from './answer.js';
import { withheld } from './steps.js';
import * as T from './text.js';

export function createView({ cfg, corpus, md }) {
  const thread = $('#thread'), threadScroll = $('#thread-scroll'), sourcesPane = $('#pane-sources');
  const statusEl = $('#status');
  const sources = createSources({ list: $('#passages'), countEl: $('#src-count'), tabCount: $('#tab-count'),
    onApi: id => api.open(run, id), onRead: id => reader.open(run, id) });
  const api = createApiModal($('#api'), { cardFor: id => cardCopy(id) });
  const reader = createReader($('#reader'));
  for (const d of $$('dialog')) {
    d.querySelector('[data-close]').addEventListener('click', () => d.close());
    let downOnBackdrop = false;
    d.addEventListener('mousedown', e => { downOnBackdrop = e.target === d; });
    d.addEventListener('click', e => { if (e.target === d && downOnBackdrop) d.close(); });
  }

  let run = createRun(), steps = null, bandSlot = null, answerSlot = null, endSlot = null, costSlot = null, replayDate = null;
  let bandShown = false;
  // the box's first subheading, the furthest a run's end scrolls, and whether the visitor scrolled while the
  // web search ran on after the answer, after which the run's end does not scroll at all (round 29)
  let bandCap = null, leftAlone = false;
  let answerNodes = null;
  const phone = () => matchMedia('(max-width: 759px)').matches;

  // ---------- panes ----------
  const smooth = () => !matchMedia('(prefers-reduced-motion: reduce)').matches;
  function setPane(p) {
    document.body.dataset.pane = p;
    $$('.tabs button[data-pane]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.pane === p)));
    redraw();
  }
  $$('.tabs button[data-pane]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.pane === (document.body.dataset.pane || 'thread'))));
  $$('.tabs button[data-pane]').forEach(b => b.addEventListener('click', () => setPane(b.dataset.pane)));
  function near(pane) { return pane.scrollHeight - pane.scrollTop - pane.clientHeight < 260; }
  function follow(pane, glide = true) {
    const behavior = glide && smooth() ? 'smooth' : 'auto';
    if (pane !== threadScroll || !bandCap) { pane.scrollTo({ top: pane.scrollHeight, behavior }); return; }
    // the later-developments box can run long: the run's end shows it only down to its first subheading ("Claude's
    // overview"), so the answer above stays in view, and it never scrolls back up (the user, round 29, Oct 26, 2026)
    const top = capBottom(bandCap) - pane.clientHeight;
    if (top > pane.scrollTop + 1) pane.scrollTo({ top, behavior });
  }
  // measured from the box and the heading's offset in it, not the heading's own box, which moves while the box inks in
  function capBottom(head) {
    const sec = head.offsetParent;
    return sec.getBoundingClientRect().top - threadScroll.getBoundingClientRect().top + threadScroll.scrollTop
      + head.offsetTop + head.offsetHeight + 12;
  }

  // Following the newest content: a pane stays pinned to its bottom until the visitor scrolls it away, and pins again
  // when they scroll back near the bottom. Pinning is decided by the visitor's own scrolling, never by measuring at
  // each event: in a burst of events (a held research step releasing what queued behind it), a smooth scroll still
  // under way leaves the pane far from a bottom that just moved, and following stopped for good (the user, Oct 25).
  const pinned = new Map([[threadScroll, true], [sourcesPane, true]]);
  const touched = new Map([...pinned.keys()].map(p => [p, -Infinity]));   // each pane's last wheel, touch, key or scrollbar grab
  addEventListener('keydown', () => { for (const p of touched.keys()) touched.set(p, performance.now()); }, true);
  for (const pane of pinned.keys()) {
    const mark = () => touched.set(pane, performance.now());
    for (const t of ['wheel', 'touchstart', 'touchmove']) pane.addEventListener(t, mark, { passive: true });
    pane.addEventListener('pointerdown', e => { if (e.target === pane) mark(); });    // the scrollbar itself
    // within a second of the visitor's input, a scroll is theirs (momentum included); ours never change the pin
    pane.addEventListener('scroll', () => {
      if (performance.now() - touched.get(pane) >= 1000) return;
      pinned.set(pane, near(pane));
      // any scroll of theirs, up or down, once the answer is written and the web search still runs (round 29)
      if (pane === threadScroll && !run.ended && webWaiting()) leftAlone = true;
    }, { passive: true });
  }
  // the dock grows when a run ends (the line under the composer returns): a pinned conversation keeps its last line
  // in view instead of sliding under the dock
  new ResizeObserver(() => { if (pinned.get(threadScroll) && !leftAlone) follow(threadScroll, false); }).observe(threadScroll);
  // an opened fold near the bottom (the cost line's parts) scrolls up far enough to show all of it
  function revealFold(e) {
    const pr = threadScroll.getBoundingClientRect(), er = e.getBoundingClientRect();
    const by = Math.min(er.bottom - pr.bottom + 16, er.top - pr.top - 16);
    if (er.bottom > pr.bottom && by > 0) threadScroll.scrollBy({ top: by, behavior: smooth() ? 'smooth' : 'auto' });
  }

  // ---------- a new run screen (T4.4 #12: conversation and sources cleared) ----------
  function reset({ question, replay = null }) {
    clearThread(true);
    run = createRun();
    sources.reset();
    clear(thread);
    replayDate = replay ? T.chicagoDate(replay.recorded_at) : null;
    if (replay) {
      thread.append(h('div', { class: 'notice replay' }, T.REPLAY_BANNER(replayDate),
        replay.corpus_label === 'before_chatrie' ? h('span', { class: 'block' }, ...richParts(T.BEFORE_CHATRIE)) : null));
    }
    thread.append(h('div', { class: 'ask-msg', attrs: { hidden: !question } }, h('p', { class: 'bubble' }, question)));
    const stepsBox = h('div', { class: 'steps-box' });
    thread.append(stepsBox);
    steps = createSteps(stepsBox, { onGoto: id => gotoSource(id) });
    answerSlot = h('div', { class: 'answer-slot' });
    endSlot = h('div', { class: 'end-slot' });
    bandSlot = h('div', { class: 'band-slot' });
    costSlot = h('div', { class: 'end-slot' });
    // the answer, its two warnings, then the later-developments box, then the run's cost (the user, round 23)
    thread.append(answerSlot, endSlot, bandSlot, costSlot);
    answerNodes = null;
    bandShown = false;
    bandCap = null;
    leftAlone = false;
    threadScroll.scrollTo(0, 0);
    sourcesPane.scrollTo(0, 0);
    for (const pane of pinned.keys()) pinned.set(pane, true);
    setPane('thread');
  }
  function setQuestion(q) {
    const b = $('.ask-msg', thread);
    if (!b) return;
    if (q == null) { b.remove(); return; }
    $('.bubble', b).textContent = q;
    b.hidden = !q;
  }
  function richParts(parts) {
    return parts.map(p => (typeof p === 'string' ? p : p.i ? h('i', null, p.i) : ''));
  }

  // ---------- one event ----------
  function onEvent(ev, { quiet = false } = {}) {
    setQuiet(quiet);
    const pinThread = pinned.get(threadScroll), pinSources = pinned.get(sourcesPane);
    apply(run, ev);
    steps.sync(run);
    sources.sync(run);
    if (ev.kind === 'answer_block' || ev.kind === 'checks' || ev.kind === 'run_ended' || ev.kind === 'composition_started'
      || ev.kind === 'warning') showAnswer();
    if (ev.kind === 'run_ended') showEnd();
    placeBand(quiet);
    if (ev.kind === 'composition_started') announce(T.runStatus.answer);
    status();
    if (pinThread && !leftAlone) follow(threadScroll, !quiet);
    if (pinSources && (ev.kind === 'tool_result' || ev.kind === 'passage')) follow(sourcesPane, !quiet);
    redraw();
    setQuiet(false);
  }

  const announcer = $('#announce');
  let said = '';
  function announce(text) { if (text && text !== said) { said = text; announcer.textContent = text; } }
  function status(text, working) {
    if (text !== undefined) { statusEl.textContent = text; statusEl.classList.toggle('working', !!working); return; }
    const e = run.ended;
    let s;
    if (e) {
      // "Finished" only where research finished and its answer or reply was written (T5.4 #9)
      const finishedStates = ['answered', 'no_sources', 'step_limit', 'token_ceiling', 'time_limit', 'error_stopped'];
      if (!finishedStates.includes(e.state)) s = T.ENDED_STATUS(run.lastT / 1000);
      else if (e.state === 'no_sources') s = T.finishedReply(e.rounds, run.lastT / 1000);
      else if (run.blocks.length) s = T.finished(e.rounds, run.lastT / 1000);
      else s = T.ENDED_STATUS(run.lastT / 1000);
    } else if (!run.researchDone) s = run.researchStatus ? T.runStatus.research(run.researchStatus) : T.WORKING;
    else if (run.open.composition && run.open.update) s = T.runStatus.both;
    else if (run.open.composition) s = T.runStatus.answer;
    else if (run.open.update) s = run.blocks.length && run.checks ? T.runStatus.update : T.runStatus.updateOnly;
    else s = T.WORKING;
    if (replayDate && !e) s = `${T.REPLAY_STATUS(replayDate)} · ${s}`;
    statusEl.textContent = s;
    statusEl.classList.toggle('working', !e);
    // screen readers hear the start and end of the answer and the run's end, not every step or second
    if (e) announce(s);
  }

  // ---------- later developments: the box under the answer (the user, round 23, Oct 26, 2026) ----------
  // It comes in once both the answer and the web search are done, which is when the run ends, so it never pushes
  // what is being read. While the web search runs on after the answer is written, a quiet line holds its place.
  function placeBand(quiet) {
    if (bandShown) return;
    if (run.ended) {
      clear(bandSlot);
      const b = run.band && renderBand(run.band, cfg, run.limits);
      bandShown = true;
      if (!b) return;
      bandSlot.append(b);
      bandCap = b.querySelector('h3');
      if (!quiet) inkIn(b);
      if (run.band.outcome === 'found') showAnswer();      // the pointer under the answer comes with the box
      return;
    }
    const waiting = webWaiting();
    if (waiting && !bandSlot.firstChild) bandSlot.append(fresh(h('p', { class: 'band-waiting' }, T.BAND_WAITING)));
    else if (!waiting) clear(bandSlot);
  }

  // the answer is written (or none will be) and the web search runs on
  function webWaiting() {
    const answerDone = !run.keepOrder.length || run.checks || run.composition.failed
      || (run.composition.started && !run.open.composition);
    return run.researchDone && run.open.update && answerDone;
  }

  // ---------- the answer ----------
  function showAnswer() {
    const e = run.ended;
    const sec = h('section', { class: 'answer', attrs: { 'aria-label': T.ANSWER_HEADING } });
    // the Voyage warning sits above the answer, like the scope note, never red (T4.4 #7)
    for (const w of run.warnings) sec.append(h('p', { class: 'notice' }, w === 'meaning_search_degraded' ? T.VOYAGE_DEGRADED : T.VOYAGE_UNAVAILABLE));
    if (e && e.state === 'no_sources') {
      sec.append(h('h2', null, T.NO_SOURCES_LABEL),
        h('p', { class: 'standard' }, e.no_sources_reason === 'out_of_scope' ? T.OUT_OF_SCOPE : T.NOTHING_FOUND),
        h('div', { class: 'prose reply' }, ...(e.note || '').split(/\n{2,}/).map(par => h('p', null, ...withheld(par)))));
      clear(answerSlot).append(sec);
      return;
    }
    if (!run.composition.started && !run.blocks.length) { if (run.warnings.length) clear(answerSlot).append(sec); return; }
    const labels = answerLabels(run);
    if (e && e.scope_note) sec.append(h('p', { class: 'notice' }, h('span', { class: 'whose' }, T.WHOSE_NOTE), ...withheld(e.scope_note)));
    if (labels.top) sec.append(h('p', { class: 'stop-label' }, T.stopTop(labels.top, cfg)));
    if (run.blocks.length) {
      sec.append(h('h2', null, T.ANSWER_HEADING), h('p', { class: 'by' }, T.ANSWER_BY),
        h('p', { class: 'key' }, h('span', { class: 'key-cited' }, T.ANSWER_KEY.split(';')[0]), T.ANSWER_KEY.slice(T.ANSWER_KEY.indexOf(';'))));
    }
    const prose = h('div', { class: 'prose' });
    const tags = tagsFor(run, run.blocks.filter(Boolean).flatMap(b => b.citations.map(c => c.passage_id)));
    const laid = layoutAnswer({ md, blocks: run.blocks, flags: run.checks ? run.checks.flags : [], hueOf: id => hueOf(run, id), tagOf: id => tags.get(id) || id });
    prose.append(mount(laid.nodes));
    // each note names the words it is about, and each marked span points to its note for screen readers
    const flags = run.checks ? run.checks.flags : [];
    for (const note of prose.querySelectorAll('.flag-note')) {
      const j = note.dataset.flagNote, f = flags[Number(j)];
      note.id = `flag-note-${j}`;
      note.append(h('strong', null, `\u201c${f ? f.text : ''}\u201d`), ' ',
        note.dataset.kind === 'quotation_not_found' ? T.FLAG_QUOTATION : T.flagCitation(corpus));
    }
    for (const span of prose.querySelectorAll('.flagged')) {
      span.setAttribute('aria-describedby', span.dataset.flag.split(' ').map(j => `flag-note-${j}`).join(' '));
    }
    if (!run.checks && !e && run.blocks.length) prose.lastElementChild?.classList.add('caret-host');
    sec.append(prose);
    answerNodes = prose;
    if (labels.end) sec.append(h('p', { class: 'stop-label end' }, labels.end === 'cut_off' ? T.CUT_OFF : T.INCOMPLETE));
    else if (e && ['failed', 'interrupted', 'abandoned'].includes(e.state) && run.blocks.length) sec.append(h('p', { class: 'stop-label end' }, T.PARTIAL_UNCHECKED));
    if (bandShown && run.band && run.band.outcome === 'found' && run.blocks.length) sec.append(h('p', { class: 'pointer' }, T.BAND_POINTER));
    // no line under the answer for the checks: they are an add-on, shown only as flags when they catch something (P4.34)
    if (!run.blocks.length && (run.composition.failed || (e && e.state === 'failed' && run.keepOrder.length))) {
      sec.append(h('p', { class: 'stop-label' }, T.COMPOSITION_FAILED(T.failureWords(e ? e.failure_reason : run.composition.failed.error_kind))));
    }
    clear(answerSlot).append(sec);
  }

  // ---------- the run's last step and its cost line (T4.4 #5, T4.5) ----------
  function showEnd() {
    const e = run.ended;
    const kept = run.keepOrder.length;
    if (e.state === 'abandoned') steps.last(T.abandoned(cfg));
    else if (e.state === 'interrupted') steps.last(T.INTERRUPTED);
    else if (e.state === 'spend_limit') steps.last(T.SPEND_LIMIT_ENDED);
    else if (e.state === 'refusal') steps.last(T.REFUSAL_ENDED);
    else if (e.state === 'failed' && !kept) steps.last(T.FAILED_NOTHING_KEPT(T.failureWords(e.failure_reason)));
    else if (['step_limit', 'token_ceiling', 'time_limit', 'error_stopped'].includes(e.state) && !run.blocks.length) steps.last(T.stopNothingKept(e.state, cfg));
    // the disclaimers, once under each run's answer rather than always in the dock (the user, Oct 25, 2026); the
    // AI disclosure starts its own line (T4.1)
    clear(endSlot).append(h('div', { class: 'run-fine' }, h('p', null, T.NOT_ADVICE), h('p', null, T.AI_DISCLOSURE)));
    clear(costSlot);
    if (e.totals) {
      const costs = renderCosts(e.totals, replayDate, run.estimated);
      costs.addEventListener('toggle', () => { if (costs.open) requestAnimationFrame(() => revealFold(costs)); });
      costSlot.append(costs);
    }
  }

  // ---------- citations: hover or tap lights the exact sentences, with a connecting line (T4.1) ----------
  const svg = $('#threads');
  let active = null;      // {p, b, ci, pinned}
  function citationAt(b, ci = 0) { const blk = run.blocks[b]; return blk && blk.citations[ci]; }
  function unlight() {
    $$('.lit').forEach(e => e.classList.remove('lit'));
    $$('#passages .card.focus').forEach(unlightSentences);
  }
  function clearThread(force) {
    if (active && active.pinned && !force) return;
    unlight();
    active = null;
    svg.replaceChildren();
  }
  function light(p, b, ci, pinned, drawFresh = true) {
    unlight();
    active = { p, b, ci, pinned };
    const card = document.getElementById(`src-${p}`);
    if (card) {
      card.classList.add('lit');
      if (b != null) {
        const ranges = run.blocks[b].citations.filter(c => c.passage_id === p);
        lightSentences(card, ranges.map(c => [c.first_sentence, c.last_sentence]));
      }
    }
    if (b != null) $$(`.cited[data-b="${b}"]`).forEach(e => e.classList.add('lit'));
    draw(drawFresh);
  }
  function firstCite(p) {
    const list = run.cited.get(p);
    if (!list || !list.length) return null;
    const blk = run.blocks[list[0].block];
    return { b: list[0].block, ci: blk.citations.findIndex(c => c.passage_id === p) };
  }
  function paneTop(pane) { const head = pane.querySelector('.col-head'); return head ? head.getBoundingClientRect().bottom : pane.getBoundingClientRect().top; }
  function inView(e) { const pane = e.closest('.scroller'), r = e.getBoundingClientRect(); return r.top >= paneTop(pane) && r.bottom <= pane.getBoundingClientRect().bottom; }
  function centerIn(e, glide = true) {
    const pane = e.closest('.scroller');
    if (!pane) return;
    const pr = pane.getBoundingClientRect(), er = e.getBoundingClientRect();
    const head = pane.querySelector('.col-head');
    const offset = Math.max((head ? head.offsetHeight : 0) + 12, (pane.clientHeight - er.height) / 2);
    pane.scrollTo({ top: pane.scrollTop + er.top - pr.top - offset, behavior: glide && smooth() ? 'smooth' : 'auto' });
  }
  function target(p) { const card = document.getElementById(`src-${p}`); return card && (card.querySelector('.sb.hit') || card); }
  function visible(e) { return e && e.getClientRects().length > 0; }
  function clampY(y, e) { const pane = e.closest('.scroller'); return Math.min(Math.max(y, paneTop(pane) + 10), pane.getBoundingClientRect().bottom - 10); }
  function curve(x1, y1, x2, y2, hue, drawFresh) {
    const dx = Math.max(40, (x2 - x1) / 2);
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', `M${x1},${y1} C${x1 + dx},${y1} ${x2 - dx},${y2} ${x2},${y2}`);
    path.setAttribute('stroke', hue);
    svg.append(path);
    if (drawFresh) { path.style.setProperty('--len', path.getTotalLength()); path.classList.add('draw'); }
    for (const [x, y] of [[x1, y1], [x2, y2]]) {
      const c = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      c.setAttribute('cx', x); c.setAttribute('cy', y); c.setAttribute('r', 4); c.setAttribute('fill', hue);
      svg.append(c);
    }
  }
  function draw(drawFresh) {
    svg.replaceChildren();
    if (!active || active.b == null || phone()) return;
    const card = document.getElementById(`src-${active.p}`);
    const spans = $$(`.cited[data-b="${active.b}"]`);
    const s = spans[spans.length - 1];
    if (!visible(card) || !visible(s)) return;
    const hue = getComputedStyle(card).getPropertyValue('--hue').trim();
    const cr = card.getBoundingClientRect();
    const hit = card.querySelector('.sb.hit');
    const hr = hit && hit.getClientRects()[0];
    const cy = clampY(hr ? hr.top + hr.height / 2 : cr.top + 22, card);
    const pill = s.querySelector(`.pill[data-ci="${active.ci}"]`) || s.querySelector('.pill') || s;
    const rects = pill.getClientRects();
    const a = rects[rects.length - 1];
    if (!a) return;
    const x0 = (s.closest('.prose') || s).getBoundingClientRect().right + 8;
    curve(x0, clampY(a.top + a.height / 2, s), cr.left, cy, hue, drawFresh);
  }
  let queued = false;
  function redraw() {
    if (queued || !active) return;
    queued = true;
    requestAnimationFrame(() => { queued = false; draw(false); });
  }
  addEventListener('scroll', redraw, true);
  addEventListener('resize', redraw);
  function reveal(p) { const t = target(p); if (t && visible(t) && !inView(t)) centerIn(t); }
  function focusSource(p, b, ci) {
    if (phone()) setPane('sources');
    light(p, b, ci, true);
    const t = target(p);
    if (t) requestAnimationFrame(() => {
      centerIn(t, !phone() && smooth());
      const card = document.getElementById(`src-${p}`);
      if (phone() && card) { card.tabIndex = -1; card.focus({ preventScroll: true }); }
    });
  }
  function gotoSource(id) {
    const fc = firstCite(id);
    if (fc) focusSource(id, fc.b, fc.ci);
    else { if (phone()) setPane('sources'); const card = document.getElementById(`src-${id}`); if (card) requestAnimationFrame(() => centerIn(card)); }
  }

  thread.addEventListener('mouseover', e => {
    const s = e.target.closest('.cited');
    if (!s || (active && active.pinned)) return;
    const b = Number(s.dataset.b);
    const c = citationAt(b);
    if (!c || (active && active.b === b)) return;
    light(c.passage_id, b, 0, false);
    reveal(c.passage_id);
  });
  thread.addEventListener('mouseout', e => {
    const s = e.target.closest('.cited');
    if (s && !s.contains(e.relatedTarget)) clearThread();
  });
  $('#passages').addEventListener('mouseover', e => {
    const card = e.target.closest('.card.kept');
    if (!card || (active && (active.pinned || active.p === card.dataset.id))) return;
    const fc = firstCite(card.dataset.id);
    light(card.dataset.id, fc ? fc.b : null, fc ? fc.ci : 0, false);
  });
  $('#passages').addEventListener('mouseleave', () => clearThread());
  document.addEventListener('click', e => {
    const t = e.target;
    if (t.closest('dialog')) return;
    const pill = t.closest('.cited .pill');
    if (pill) { const b = Number(pill.dataset.b), ci = Number(pill.dataset.ci); const c = citationAt(b, ci); if (c) focusSource(c.passage_id, b, ci); return; }
    const s = t.closest('.cited');
    if (s) { const b = Number(s.dataset.b); const c = citationAt(b); if (c) focusSource(c.passage_id, b, 0); return; }
    if (!t.closest('.card') && !t.closest('[data-goto]')) clearThread(true);
  });
  // keyboard: a cited sentence's pills are buttons, so Tab reaches each citation and Enter follows it; Escape lets go
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && active && !document.querySelector('dialog[open]')) clearThread(true); });

  // a copy of a card for the API window, its cited sentences lit
  function cardCopy(id) {
    const card = document.getElementById(`src-${id}`);
    const copy = card ? card.cloneNode(true) : h('div');
    copy.removeAttribute('id');
    copy.querySelectorAll('.card-actions').forEach(e => e.remove());
    const list = run.cited.get(id);
    if (list && list.length) lightSentences(copy, list.map(c => [c.first, c.last]));
    copy.classList.remove('lit');
    return copy;
  }

  return {
    reset, onEvent, status, setQuestion, steps: () => steps, get run() { return run; },
    clearThread,
    endStep(text) { steps.last(text); announce(text); },
  };
}
