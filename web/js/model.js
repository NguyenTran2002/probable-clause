// The run's state, built from its events (contract v2.1 §6) and nothing else. No DOM: Node's tests drive it over
// every fixture. Events are placed by their `step`, never by their position in the stream.
//
// The step log is three lists: research's, then the composition's and the update step's, side by side in time.
// Each item is one thing the visitor watches happen: a Claude call waiting for its reply (shown only while it waits
// or when it needed a retry), a tool call with its result, a pause or a resume.

import { passageTag, pageTarget, SHORT_NAMES } from './text.js';

export const HUES = ['h1', 'h2', 'h3', 'h4'];
const SEARCHES = new Set(['search_meaning', 'search_exact']);

export function createRun() {
  return {
    id: null, question: null, startedAt: null, limits: null, coverage: null, models: null, corpusLabel: 'full',
    updateAvailable: true,
    lastN: 0, lastT: 0,
    lists: { research: [], composition: [], update: [] },
    open: { research: true, composition: false, update: false },   // a group's spinner
    current: { research: null, update: null },                     // the Claude call each step is waiting on
    tools: new Map(),           // tool_use_id -> the step-log item
    passages: new Map(),        // id -> the passage (§6.1)
    cards: [],                  // ids with their own card, in order of first appearance (T4.3 #1)
    foundBy: new Map(),         // id -> [tool_use_id], every search or read that returned it
    keeps: new Map(),           // id -> {reason, order}
    keepOrder: [],
    fragments: new Map(),       // passage id -> [api_fragment data]
    calls: new Map(),           // call_no -> [paid_call data], every attempt of one Claude call
    estimated: 0,               // Claude and Exa attempts priced from this site's estimate (P5.4); Voyage is not in the shown total
    update: { started: false, kept: null, ended: null },
    composition: { started: false, callNo: null, documents: [], item: null, failed: null },
    blocks: [],
    cited: new Map(),           // passage id -> [{block, first, last}]
    checks: null, checksItem: null,
    band: null,
    warnings: [],
    ended: null,
    researchDone: false,
  };
}

function item(run, list, it) { it.list = list; run.lists[list].push(it); return it; }

// Where a run-wide item (a pause, a resume) goes: research's list while research runs, then the update step's
// while it runs (its calls are the ones a pause holds back), else the composition's.
function runWideList(run) {
  if (!run.researchDone) return 'research';
  if (run.update.started && !run.update.ended && run.open.update) return 'update';
  return 'composition';
}

function seen(run, id, toolUseId) {
  const by = run.foundBy.get(id) || [];
  if (toolUseId && !by.includes(toolUseId)) by.push(toolUseId);
  run.foundBy.set(id, by);
}
function addCard(run, id) { if (!run.cards.includes(id)) run.cards.push(id); }

export function hueOf(run, id) {
  const k = run.keeps.get(id);
  return k ? HUES[k.order % HUES.length] : null;
}

// A passage's tag (P4.35), at the lowest level that keeps it apart from the others in `ids`: the answer's tags go up a
// level only when two in the answer would read the same. An unknown passage keeps its ID.
export function tagsFor(run, ids, minLevel = 0) {
  const ps = [...new Set(ids)].map(id => run.passages.get(id) || { id });
  const level = new Map(ps.map(p => [p.id, minLevel]));
  const label = p => (p.case_name ? passageTag(p, level.get(p.id)) : p.id);
  for (let round = 0; round < 3; round++) {
    const seen = new Map();
    for (const p of ps) { const l = label(p); seen.set(l, [...(seen.get(l) || []), p]); }
    let bumped = false;
    for (const group of seen.values()) if (group.length > 1) for (const p of group) if (level.get(p.id) < 2) { level.set(p.id, level.get(p.id) + 1); bumped = true; }
    if (!bumped) break;
  }
  return new Map(ps.map(p => [p.id, label(p)]));
}
// a read's target: a passage ID, a case and page ("katz:351") or, in Chatrie, an opinion and page ("chatrie-1:12")
export function readTarget(run, target) {
  const p = run.passages.get(target);
  if (p) return { tag: tagOf(run, target), footnote: p.kind === 'footnote' };
  const m = /^([a-z_]+)(-\d+)?:(\d+)$/.exec(target);
  if (m && SHORT_NAMES[m[1]]) {
    const opinion = m[2] ? [...run.passages.values()].find(q => q.opinion_id === m[1] + m[2]) || { opinion_type: 'majority' } : null;
    return { tag: pageTarget(m[1], Number(m[3]), opinion), footnote: false };
  }
  return { tag: null, raw: target, footnote: false };
}
// the cards and the step log list many passages from the same pages, so theirs always carry the paragraph (level 1),
// and the author when even that is shared
export function tagOf(run, id) {
  const p = run.passages.get(id);
  if (!p) return id;
  const same = [...run.passages.values()].filter(q => q.case_key === p.case_key && q.page_start === p.page_start);
  return tagsFor(run, same.map(q => q.id), 1).get(id);
}

// What each card shows once the run is over (T4.3 #1), or now while it runs.
export function cardState(run, id) {
  const kept = run.keeps.has(id);
  const answered = run.blocks.length > 0;
  if (kept) {
    if (run.cited.has(id)) return 'cited';
    return answered && run.ended ? 'uncited' : 'kept';
  }
  return run.ended ? 'notkept' : 'found';
}

export function apply(run, ev) {
  const d = ev.data;
  run.lastN = ev.n;
  run.lastT = ev.t_ms;
  switch (ev.kind) {
    case 'run_started':
      run.id = ev.run; run.question = d.question; run.startedAt = ev.at; run.limits = d.limits;
      run.coverage = d.coverage; run.models = d.models; run.corpusLabel = d.corpus_label;
      run.updateAvailable = d.update_check_available;
      break;

    case 'round_started': {
      const step = d.step;
      const it = item(run, step, { type: 'call', step, round: d.round, statusLine: d.status_line, lines: [],
        state: 'working', tools: [] });
      run.current[step] = it;
      if (step === 'research') run.researchStatus = d.status_line; else run.updateStatus = d.status_line;
      break;
    }

    case 'paid_call': {
      if (d.estimated && d.service !== 'voyage') run.estimated += 1;
      if (d.service === 'anthropic') {
        const list = run.calls.get(d.call_no) || [];
        list.push(d);
        run.calls.set(d.call_no, list);
      }
      const target = paidTarget(run, d);
      if (!target) break;
      if (d.outcome === 'retrying') target.lines.push({ kind: 'retry', pc: d });
      else if (d.outcome === 'failed') {
        if (d.error_kind === 'refusal') target.lines.push({ kind: 'refusal' });
        else if (d.service !== 'exa') target.lines.push({ kind: 'failed', pc: d });
        if (d.service === 'anthropic') {
          target.state = 'failed';
          if (target.type === 'composition') { run.composition.failed = d; run.open.composition = false; }
        }
      } else if (d.service === 'anthropic' && target.type === 'call') {
        target.state = 'done';
      }
      break;
    }

    case 'tool_call': {
      const call = run.current[d.step];
      const it = item(run, d.step, { type: 'tool', step: d.step, round: d.round, id: d.tool_use_id, name: d.name,
        input: d.input, result: null, state: 'working', lines: [] });
      if (call) call.tools.push(d.tool_use_id);
      run.tools.set(d.tool_use_id, it);
      break;
    }

    case 'passage':
      run.passages.set(d.id, d);
      break;

    case 'tool_result': {
      const it = run.tools.get(d.tool_use_id);
      if (!it) break;
      it.result = d;
      const refused = d.wrong_step || (d.submit && !d.submit.accepted) || d.is_error;
      it.state = refused ? 'rejected' : 'done';
      if (d.wrong_step) it.wrongStep = true;
      if (SEARCHES.has(d.name)) {
        for (const id of d.found || []) { seen(run, id, d.tool_use_id); addCard(run, id); }
        for (const id of d.matched_again || []) seen(run, id, d.tool_use_id);
        if (d.not_reranked) it.lines.push({ kind: 'not_reranked' });
      } else if (d.name === 'read_passages') {
        for (const id of d.read || []) { seen(run, id, d.tool_use_id); addCard(run, id); }
      } else if (d.name === 'keep_passages') {
        for (const k of d.kept || []) {
          const prev = run.keeps.get(k.id);
          run.keeps.set(k.id, { reason: k.reason, order: prev ? prev.order : run.keepOrder.length });
          if (!prev) run.keepOrder.push(k.id);
          addCard(run, k.id);
        }
      }
      break;
    }

    case 'api_fragment': {
      const list = run.fragments.get(d.passage_id) || [];
      list.push(d);
      run.fragments.set(d.passage_id, list);
      break;
    }

    case 'paused':
      item(run, runWideList(run), { type: 'paused', sinceMs: d.since_ms, state: 'done', lines: [] });
      break;
    case 'resumed':
      item(run, runWideList(run), { type: 'resumed', sinceMs: d.since_ms, state: 'done', lines: [] });
      break;

    case 'warning':
      if (!run.warnings.includes(d.code)) run.warnings.push(d.code);
      break;

    case 'update_started':
      endResearch(run);
      run.update.started = true;
      run.update.kept = d.kept;
      run.open.update = true;
      break;

    case 'update_ended':
      run.update.ended = d;
      run.open.update = false;
      closeWorking(run.lists.update, 'stopped');
      // an update step that did not submit says how it ended, in its own group
      if (d.end !== 'submitted') item(run, 'update', { type: 'update_end', end: d.end, state: d.end === 'abandoned' ? 'stopped' : 'rejected', lines: [] });
      break;

    case 'composition_started':
      endResearch(run);
      run.composition.started = true;
      run.composition.callNo = d.call_no;
      run.composition.documents = d.documents;
      run.open.composition = true;
      run.composition.item = item(run, 'composition', { type: 'composition', state: 'working', lines: [],
        documents: d.documents.length });
      break;

    case 'answer_block':
      run.blocks[d.index] = d;
      for (const c of d.citations) {
        const list = run.cited.get(c.passage_id) || [];
        list.push({ block: d.index, first: c.first_sentence, last: c.last_sentence });
        run.cited.set(c.passage_id, list);
      }
      break;

    case 'checks':
      run.checks = d;
      if (run.composition.item) run.composition.item.state = 'done';
      run.open.composition = false;
      run.checksItem = item(run, 'composition', { type: 'checks', state: 'done', lines: [] });
      break;

    case 'update_band':
      endResearch(run);
      run.band = d;
      break;

    case 'run_ended':
      run.ended = d;
      endResearch(run);
      for (const list of Object.values(run.lists)) closeWorking(list, 'stopped');
      if (run.composition.item && run.composition.item.state === 'working') {
        run.composition.item.state = run.blocks.length ? 'done' : 'stopped';
      }
      run.open.research = run.open.update = run.open.composition = false;
      break;
  }
  return ev;
}

// Research ends at its accepted submit; a run whose band or composition comes first ended research then (a limit,
// a stop, an out-of-scope reply).
function endResearch(run) {
  if (run.researchDone) return;
  run.researchDone = true;
  run.open.research = false;
  // a Claude call that answered with no tool call (the reply that ended research) needs no item of its own
  for (const it of run.lists.research) if (it.type === 'call' && it.state === 'working') it.state = 'done';
}

// Anything still working when its part of the run ends is closed, never left as a spinner (contract §6): a call
// cancelled mid-flight, a search with no result.
function closeWorking(list, state) {
  for (const it of list) if (it.state === 'working') it.state = it.type === 'call' && !it.lines.length ? 'done' : state;
}

// Which step-log item a paid call's retry or failure line belongs to (T4.4 #4).
function paidTarget(run, d) {
  if (d.purpose === 'composition') return run.composition.item;
  if (d.purpose === 'loop' || d.purpose === 'update') return run.current[d.step];
  if (d.purpose === 'embed' || d.purpose === 'rerank') {
    const list = run.lists.research;
    for (let i = list.length - 1; i >= 0; i--) if (list[i].type === 'tool' && list[i].name === 'search_meaning') return list[i];
    return null;
  }
  if (d.purpose === 'update_search') {
    const list = run.lists.update;
    for (let i = list.length - 1; i >= 0; i--) if (list[i].type === 'tool' && list[i].name === 'search_web_updates') return list[i];
  }
  return null;
}

// Is a Claude-call item worth showing? While it waits, yes; afterwards only if it carries a retry or failure line.
export function callVisible(it) { return it.state === 'working' || it.lines.length > 0; }

// The answer's state for its labels (T4.4 #8, T5.4 #6).
export function answerLabels(run) {
  const e = run.ended;
  if (!e) return { top: null, end: null };
  const top = ['step_limit', 'token_ceiling', 'time_limit', 'error_stopped'].includes(e.state) && run.blocks.length ? e.state : null;
  const end = e.answer_end === 'cut_off' ? 'cut_off' : e.answer_end === 'incomplete' ? 'incomplete' : null;
  return { top, end };
}

// Totals for "View API calls": each response's exact usage, keyed by its call number (T4.5 D).
export function usageOf(run, callNo) {
  const attempts = run.calls.get(callNo) || [];
  return attempts.filter(a => a.outcome === 'ok' || a.usage || a.estimated_usage);
}

// Seconds the run has taken, from its own clock (t_ms).
export function elapsedS(run) { return Math.round(run.lastT / 1000); }
