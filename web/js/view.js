// The run screen: the conversation (the question, the step log, the update-check band, the answer) and the sources
// panel, fed one event at a time through the run model. Live runs, reattached runs and replays all play here.

import { h, $, $$, clear, fresh, setQuiet } from './dom.js';
import { createRun, apply, answerLabels, hueOf } from './model.js';
import { createSteps } from './steps.js';
import { createSources, lightSentences, unlightSentences } from './sources.js';
import { renderBand } from './band.js';
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
    d.addEventListener('click', e => { if (e.target === d) d.close(); });
  }

  let run = createRun(), steps = null, bandSlot = null, answerSlot = null, endSlot = null, replayDate = null;
  let answerNodes = null;
  const phone = () => matchMedia('(max-width: 759px)').matches;

  // ---------- panes ----------
  function setPane(p) { document.body.dataset.pane = p; redraw(); }
  $$('.tabs button[data-pane]').forEach(b => b.addEventListener('click', () => setPane(b.dataset.pane)));
  function near(pane) { return pane.scrollHeight - pane.scrollTop - pane.clientHeight < 260; }
  function follow(pane, smooth = true) { pane.scrollTo({ top: pane.scrollHeight, behavior: smooth ? 'smooth' : 'auto' }); }

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
    thread.append(h('div', { class: 'ask-msg' }, h('p', { class: 'bubble' }, question)));
    const stepsBox = h('div', { class: 'steps-box' });
    thread.append(stepsBox);
    steps = createSteps(stepsBox, { cfg, onGoto: id => gotoSource(id) });
    bandSlot = h('div', { class: 'band-slot' });
    answerSlot = h('div', { class: 'answer-slot' });
    endSlot = h('div', { class: 'end-slot' });
    thread.append(bandSlot, answerSlot, endSlot);
    answerNodes = null;
    threadScroll.scrollTo(0, 0);
    sourcesPane.scrollTo(0, 0);
    document.body.dataset.pane = 'thread';
  }
  function richParts(parts) {
    return parts.map(p => (typeof p === 'string' ? p : p.i ? h('i', null, p.i) : ''));
  }

  // ---------- one event ----------
  function onEvent(ev, { quiet = false } = {}) {
    setQuiet(quiet);
    const pinThread = near(threadScroll), pinSources = near(sourcesPane);
    apply(run, ev);
    steps.sync(run);
    sources.sync(run);
    if (ev.kind === 'update_band') showBand();
    if (ev.kind === 'answer_block' || ev.kind === 'checks' || ev.kind === 'run_ended' || ev.kind === 'composition_started'
      || ev.kind === 'warning') showAnswer();
    if (ev.kind === 'run_ended') showEnd();
    status();
    if (pinThread) follow(threadScroll, !quiet);
    if (pinSources && (ev.kind === 'tool_result' || ev.kind === 'passage')) follow(sourcesPane, !quiet);
    redraw();
    setQuiet(false);
  }

  function status(text, working) {
    if (text !== undefined) { statusEl.textContent = text; statusEl.classList.toggle('working', !!working); return; }
    const e = run.ended;
    let s;
    if (e) {
      s = e.state === 'answered' || run.blocks.length || e.state === 'no_sources'
        ? T.finished(e.rounds, T.num(run.lastT / 1000)) : T.ENDED_STATUS(run.lastT / 1000);
      if (e.state === 'no_sources') s = s.replace(' and the answer', ' and Claude’s reply');
    } else if (!run.researchDone) s = run.researchStatus ? T.runStatus.research(run.researchStatus) : T.WORKING;
    else if (run.open.composition && run.open.update) s = T.runStatus.both;
    else if (run.open.update) s = T.runStatus.update;
    else s = T.runStatus.answer;
    if (replayDate && !e) s = `${T.REPLAY_STATUS(replayDate)} · ${s}`;
    statusEl.textContent = s;
    statusEl.classList.toggle('working', !e);
  }

  // ---------- the band, above the answer (T4.3 #4) ----------
  function showBand() { const b = renderBand(run.band, cfg); clear(bandSlot); if (b) bandSlot.append(fresh(b)); }

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
    sec.append(h('h2', null, T.ANSWER_HEADING), h('p', { class: 'by' }, T.ANSWER_BY),
      h('p', { class: 'key' }, h('span', { class: 'key-cited' }, T.ANSWER_KEY.split(';')[0]), T.ANSWER_KEY.slice(T.ANSWER_KEY.indexOf(';'))));
    const prose = h('div', { class: 'prose' });
    const laid = layoutAnswer({ md, blocks: run.blocks, flags: run.checks ? run.checks.flags : [], hueOf: id => hueOf(run, id) });
    prose.append(mount(laid.nodes));
    for (const note of prose.querySelectorAll('.flag-note')) {
      const kind = note.dataset.kind;
      note.textContent = kind === 'quotation_not_found' ? T.FLAG_QUOTATION : T.flagCitation(corpus);
    }
    if (!run.checks && !e && run.blocks.length) prose.lastElementChild?.classList.add('caret-host');
    sec.append(prose);
    answerNodes = prose;
    if (labels.end) sec.append(h('p', { class: 'stop-label end' }, labels.end === 'cut_off' ? T.CUT_OFF : T.INCOMPLETE));
    if (run.band && run.band.outcome === 'found' && run.blocks.length) sec.append(h('p', { class: 'pointer' }, T.BAND_POINTER));
    if (run.checks) {
      const c = run.checks;
      const line = h('p', { class: 'checks' }, T.CHECKS_PREFIX, T.checksParts(c).join(' · '));
      if (c.not_in_corpus.length) {
        line.append(` · ${T.CHECKS_NOT_IN_CORPUS(c.not_in_corpus.length)}`);
        c.not_in_corpus.forEach((name, i) => line.append(i ? ', ' : '', h('i', null, name)));
        line.append('.');
      }
      else if (!/\.$/.test(line.textContent)) line.append('.');
      line.append(` ${T.CHECKS_SHORT_NAMES}`);
      sec.append(line);
    }
    if (run.composition.failed || (e && e.state === 'failed' && !run.blocks.length && run.keepOrder.length)) {
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
    if (e.totals) clear(endSlot).append(renderCosts(e.totals, replayDate));
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
  function centerIn(e, smooth = true) {
    const pane = e.closest('.scroller');
    if (!pane) return;
    const pr = pane.getBoundingClientRect(), er = e.getBoundingClientRect();
    const head = pane.querySelector('.col-head');
    const offset = Math.max((head ? head.offsetHeight : 0) + 12, (pane.clientHeight - er.height) / 2);
    pane.scrollTo({ top: pane.scrollTop + er.top - pr.top - offset, behavior: smooth ? 'smooth' : 'auto' });
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
    if (t) requestAnimationFrame(() => centerIn(t, !phone()));
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
  // keyboard: a cited sentence's pills are buttons, so Tab reaches each citation and Enter follows it

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
    reset, onEvent, status, steps: () => steps, get run() { return run; },
    clearThread,
    endStep(text) { steps.last(text); },
  };
}
