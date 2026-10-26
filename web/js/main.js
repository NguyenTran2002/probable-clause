// Wiring: the landing page, the run screen, one question per run (T4.4 #12), the wake protocol before a live run,
// replays, and a reload going straight back into its run (T3.2, T4.4 #6).

import markdownit from '../vendor/markdown-it/markdown-it.esm.min.mjs';
import { h, $, $$, clear, rich, webLink, siteLink, session } from './dom.js';
import { loadStatic, loadReplays, loadReplay } from './config.js';
import { createWaker } from './wake.js';
import { attach } from './stream.js';
import { playReplay } from './replay.js';
import { createPacer } from './pace.js';
import { createView } from './view.js';
import { makeMarkdown } from './answer.js';
import { createMargin } from './margin.js';
import * as T from './text.js';

const RUN_KEY = 'probable-clause-run';
// until the page is ready, a form must never submit natively (a GET reload with the question in the URL)
for (const f of document.forms) f.addEventListener('submit', e => e.preventDefault());
const body = document.body;

// resolves once the new view is fully in, the transition done (or skipped)
function swap(view) {
  const go = () => { body.dataset.view = view; scrollTo(0, 0); };
  if (document.startViewTransition && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
    const t = document.startViewTransition(go);
    // a transition skipped or aborted by a quick second swap is not an error
    for (const pr of [t.ready, t.finished, t.updateCallbackDone]) pr.catch(() => {});
    return t.finished.catch(() => {});
  }
  go();
  return Promise.resolve();
}

// ---------- the standing lines (T5.1, T5.2, T5.5), filled from corpus.json ----------
function standing(corpus) {
  // the credits and the privacy note are pages of their own, each opened in a new tab, on one line with the source
  // code (the user, Oct 25, 2026): under the landing page, and in the run screen's top bar. The run screen's dock
  // keeps only the status, the composer and the from-scratch line; its disclaimers sit under each answer (view.js).
  const links = () => [siteLink('sources-and-credits', T.CREDITS_SUMMARY), siteLink('privacy', T.PRIVACY_SUMMARY),
    webLink(T.REPO_URL, T.REPO_LINK_TEXT)];
  const pitch = T.pitch(corpus);
  clear($('#pitch')).append(h('p', { class: 'lead' }, pitch.lead), h('p', null, ...rich(pitch.more)));
  // the warnings close the figure; the footer keeps the coverage line, then the affiliation with the links beside it
  $('#limits-title').textContent = T.LIMITS_TITLE;
  clear($('#limits-text')).append(h('p', null, T.NOT_ADVICE), h('p', null, T.AI_DISCLOSURE));
  clear($('#landing-fine')).append(h('p', { class: 'cover' }, T.coverageLine(corpus)), h('p', null, T.AFFILIATION),
    h('p', { class: 'links' }, ...links()));
  clear($('#bar-links')).append(...links());
  $('#trace-caption').textContent = T.TRACE_CAPTION;
  $$('.fig-step').forEach((li, i) => { $('h3', li).textContent = T.FIG_STEPS[i][0]; $('.fig-say p', li).textContent = T.FIG_STEPS[i][1]; });
  $$('.fig-step .cm').forEach(c => { c.textContent = T.FIG_NOTES[Number(c.dataset.note)]; });
  $('#fig-full').textContent = T.FIG_FULL;
  $('#how-title').textContent = T.FIG_TITLE;
  $('#more').textContent = T.HOW_IT_WORKS;
  $('#from-scratch').textContent = T.FROM_SCRATCH;
}

async function boot() {
  let cfg, corpus;
  try { ({ cfg, corpus } = await loadStatic()); } catch {
    $('#pitch').textContent = T.GENERAL_FAILURE;
    return;
  }
  const md = makeMarkdown(markdownit);
  const view = createView({ cfg, corpus, md });
  const waker = createWaker(cfg);
  standing(corpus);
  // the annotated amendment behind the first view (margin.js), running only while the landing shows
  const margin = createMargin($('#landing .first'));
  if (body.dataset.view === 'landing') margin.start();
  for (const id of ['#q', '#q2']) $(id).maxLength = cfg.QUESTION_MAX_CHARS;
  $('#q').placeholder = T.ASK_PLACEHOLDER;
  for (const b of [$('#ask .primary'), $('#send')]) b.textContent = T.SEARCH;

  let live = null;          // the stream of the live run on screen
  let player = null;        // the replay on screen
  let pacer = null;         // the step log's pace for the run on screen (pace.js)
  let token = 0;            // bumps when the screen moves on, so a wake still open starts nothing

  function setPlaying(on, replay = false) {
    body.classList.toggle('playing', on);
    body.classList.toggle('replaying', on && replay);
    const q2 = $('#q2');
    q2.disabled = on;
    $('#send').disabled = on;
    q2.placeholder = on ? T.WORKING : T.ASK_ANOTHER;
  }
  function stopAll() {
    token++;
    if (live) { live.stop(); live = null; }
    if (player) { player.stop(); player = null; }
    if (pacer) { pacer.stop(); pacer = null; }
    setPlaying(false);
  }
  // the landing's exit plays first; the run starts underneath at once, so the show never holds the run up
  function toRun() {
    if (body.dataset.view !== 'landing') { swap('run'); return; }
    const my = token;
    // the landing is cleared only after the transition has taken its picture of "probable clause"
    margin.exit().then(() => { if (my === token) swap('run').then(() => { if (body.dataset.view === 'run') margin.stop(); }); });
  }

  // ---------- replays ----------
  let replays = [];
  const chipList = (cls) => (replays.length ? h('ul', { class: `chiplist ${cls || ''}` }, replays.map(r => h('li', null,
    h('button', { class: 'chip', attrs: { type: 'button' }, on: { click: () => startReplay(r.slug) } }, r.question)))) : null);
  $('#recorded').hidden = true;
  loadReplays().then(list => {
    replays = list;
    if (replays.length) { $('#recorded-label').textContent = T.OR_WATCH; $('#recorded').append(chipList()); $('#recorded').hidden = false; }
  });

  async function startReplay(slug) {
    stopAll();
    session.del(RUN_KEY);
    const my = token;          // stopAll moved the token on; a later click or run moves it again
    let rec;
    try { rec = await loadReplay(slug); } catch { return; }
    if (my !== token) return;
    view.reset({ question: rec.question, replay: rec });
    toRun();
    setPlaying(true, true);
    const pace = pacer = createPacer((ev, o) => { if (my === token) view.onEvent(ev, o); });
    player = playReplay(rec.events, (ev, o) => pace.push(ev, o), () => pace.whenIdle(() => { if (my === token) setPlaying(false); }));
  }
  $('#skip').textContent = T.SKIP;
  $('#skip').addEventListener('click', () => { if (player) player.skip(); if (pacer) pacer.flush(); });

  // ---------- the landing check (brief §2): it shows nothing unless research is paused (T4.4 #2) ----------
  waker.landing().then(health => {
    if (!health) return;
    const note = { paused_day: T.PAUSED_DAY, paused_month: T.PAUSED_MONTH }[health.live_research];
    if (note) {
      $('#q').disabled = true;
      $('#ask button').disabled = true;
      $('#ask-note').textContent = note;
    }
  });

  // ---------- a live run ----------
  async function startLive(question) {
    stopAll();
    session.del(RUN_KEY);
    view.reset({ question });
    toRun();
    setPlaying(true);
    const my = token;
    const steps = view.steps();
    let wakeStep = null;
    const showWake = setTimeout(() => { if (my === token) wakeStep = steps.waking(); }, 800);
    const tick = ({ elapsed, long }) => {
      if (my !== token || !wakeStep) return;
      view.status(T.seconds(elapsed), true);
      if (long) wakeStep.long(chipList('chips-replay'));
    };
    try {
      await waker.wake(tick);
    } catch {
      clearTimeout(showWake);
      if (my !== token) return;
      if (!wakeStep) wakeStep = steps.waking();
      wakeStep.gaveUp(() => startLive(question), chipList('chips-replay'));
      view.status('', false);
      setPlaying(false);
      return;
    }
    clearTimeout(showWake);
    if (my !== token) return;
    if (wakeStep) wakeStep.done();
    view.status(T.WORKING, true);
    // POST /runs only after /health answered our JSON, and never retried automatically (brief §8.5 rule 2)
    let r, j = null;
    try {
      // a timeout so a request that never answers ends the wait; never retried (a run nobody attaches to expires
      // with no spend, T3.1). WAKE_CHECK_TIMEOUT_S: the same placeholder as a health check's wait.
      const ctl = new AbortController();
      const timer = setTimeout(() => ctl.abort(), cfg.WAKE_CHECK_TIMEOUT_S * 1000);
      r = await fetch('api/runs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question }), signal: ctl.signal });
      clearTimeout(timer);
      if (/application\/json/.test(r.headers.get('content-type') || '')) j = await r.json().catch(() => null);
    } catch { r = null; }
    if (my !== token) return;
    if (r && r.status === 201 && j && j.run_id) {
      session.set(RUN_KEY, j.run_id);
      follow(j.run_id, my);
      return;
    }
    refused(j && j.error);
  }

  function refused(code) {
    const words = { busy: T.busy(cfg), paused_day: T.PAUSED_DAY, paused_month: T.PAUSED_MONTH, atlas_unreachable: T.ATLAS_UNREACHABLE,
      question_empty: T.QUESTION_EMPTY, question_too_long: T.questionTooLong(cfg) }[code] || T.GENERAL_FAILURE;
    view.endStep(words);
    view.status('', false);
    setPlaying(false);
  }

  // the stream could not reconnect: the waking step's give-up, whose Try again reattaches, never starts a run
  function gaveUp(runId, my) {
    const s = view.steps().waking();
    s.gaveUp(() => { s.remove(); setPlaying(true); follow(runId, my, view.run.lastN); }, chipList('chips-replay'));
    view.status('', false);
    setPlaying(false);
  }

  function follow(runId, my, lastN = 0) {
    const pace = pacer = createPacer((ev, o) => {
      if (my !== token) return;
      if (ev.kind === 'run_started') view.setQuestion(ev.data.question);
      view.onEvent(ev, o);
    });
    live = attach(runId, cfg, {
      onEvent: ev => {
        if (my !== token) return;
        const behind = Date.now() - Date.parse(ev.at) > 5000;     // a stored event caught up on, not a new one
        pace.push(ev, { quiet: behind });
      },
      onState: st => {
        if (my !== token) return;
        if (st === 'reconnecting') view.status(T.RECONNECTING, true);
        else if (st === 'open') view.status();
        else if (st === 'closed') { live = null; pace.whenIdle(() => { if (my === token) setPlaying(false); }); }
        else if (st === 'expired') { pace.flush(); view.setQuestion(null); view.endStep(T.expired(cfg)); session.del(RUN_KEY); view.status('', false); setPlaying(false); }
        // everything held is shown first, so the reattach starts from the last event on screen
        else if (st === 'gave_up') { pace.flush(); gaveUp(runId, my); }
      },
      wake: () => waker.wake(),
    }, { lastN });
  }

  // ---------- the forms ----------
  $('#ask').addEventListener('submit', e => {
    e.preventDefault();
    const q = $('#q').value.trim();
    if (!q) { $('#ask-note').textContent = T.QUESTION_EMPTY; $('#q').focus(); return; }
    $('#ask-note').textContent = '';
    startLive(q);
  });
  $('#composer').addEventListener('submit', e => {
    e.preventDefault();
    const q = $('#q2').value.trim();
    if (!q || body.classList.contains('playing')) return;
    $('#q2').value = '';
    startLive(q);
  });
  for (const id of ['#q', '#q2']) {
    $(id).addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); e.target.form.requestSubmit(); }
    });
  }
  $('#home').addEventListener('click', () => { stopAll(); session.del(RUN_KEY); view.clearThread(true); swap('landing'); margin.start(); $('#q').focus(); });

  // ---------- a reload goes straight back into its run (T3.2, T4.4 #6) ----------
  const saved = session.get(RUN_KEY);
  if (saved) {
    view.reset({ question: '' });      // the bubble fills from run_started
    body.dataset.view = 'run';
    setPlaying(true);
    follow(saved, token);
  }
}

boot();
