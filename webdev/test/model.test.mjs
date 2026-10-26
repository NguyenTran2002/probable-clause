// The run model over every fixture (frontend plan, step 2). Run: node --test webdev/test/
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { createRun, apply, cardState, callVisible, answerLabels } from '../../web/js/model.js';

const DIR = new URL('../../tests/fixtures/events/', import.meta.url);
const NAMES = readdirSync(DIR).filter(f => f.endsWith('.json')).map(f => f.slice(0, -5));
const load = name => JSON.parse(readFileSync(new URL(`${name}.json`, DIR), 'utf8'));
function play(events) { const run = createRun(); for (const ev of events) apply(run, ev); return run; }
const full = NAMES.filter(n => !/-after-n\d+$/.test(n));

for (const name of full) {
  test(`${name}: every item closed, every result paired, every citation kept`, () => {
    const d = load(name);
    const run = play(d.events);
    assert.ok(run.ended, 'run_ended applied');
    for (const [step, list] of Object.entries(run.lists)) {
      for (const it of list) {
        assert.notEqual(it.state, 'working', `${step} item left working: ${it.type} ${it.name || ''}`);
        if (it.type === 'tool') assert.equal(it.step, step, 'placed by step');
      }
    }
    assert.deepEqual(run.open, { research: false, composition: false, update: false });
    for (const ev of d.events) {
      if (ev.kind === 'tool_result') assert.ok(run.tools.has(ev.data.tool_use_id), 'a result has its call');
    }
    for (const id of run.cards) assert.ok(run.passages.has(id), `card ${id} has its passage`);
    for (const [id, cites] of run.cited) {
      assert.ok(run.keeps.has(id), `${id} is cited, so it was kept (brief §2's invariant)`);
      const n = run.passages.get(id).sentences.length;
      for (const c of cites) assert.ok(c.first >= 0 && c.first <= c.last && c.last < n, `${id} range inside its sentences`);
    }
    for (const id of run.cards) assert.ok(['found', 'kept', 'cited', 'uncited', 'notkept'].includes(cardState(run, id)));
  });
}

test('answered run: nine kept in keep order, the re-keep replaced its reason in place', () => {
  const d = load('answered-phone-location-records');
  const run = play(d.events);
  assert.equal(run.keepOrder.length, 9);
  assert.deepEqual(run.keepOrder, run.update.kept, 'keep order is update_started.kept');
  const rekept = d.events.filter(e => e.kind === 'tool_result' && e.data.name === 'keep_passages')
    .flatMap(e => e.data.kept).filter(k => k.replaced);
  assert.ok(rekept.length >= 1);
  for (const k of rekept) assert.equal(run.keeps.get(k.id).reason, k.reason, 'the latest reason wins');
  assert.equal(run.band.outcome, 'found');
  assert.equal(run.ended.state, 'answered');
  assert.ok(run.lists.update.some(it => it.type === 'tool' && it.name === 'search_web_updates'));
  assert.ok(run.lists.composition.some(it => it.type === 'composition' && it.state === 'done'));
  assert.ok(run.lists.composition.some(it => it.type === 'checks'));
  // cards end cited, kept-not-cited or not kept, and the count reads "N found, K kept"
  const states = run.cards.map(id => cardState(run, id));
  assert.ok(states.includes('cited') && states.includes('notkept'));
  assert.ok(!states.includes('found') && !states.includes('kept'));
});

test('events are placed by step, not position: regrouping the stream by step gives the same lists', () => {
  const d = load('answered-phone-location-records');
  const a = play(d.events);
  const rank = e => ({ research: 0, update: 2, composition: 1 }[e.data.step] ?? (e.kind === 'run_ended' ? 9 : 0));
  // move every update-step event after the composition's, keeping each step's own order
  const firstAfter = d.events.findIndex(e => e.kind === 'update_started');
  const head = d.events.slice(0, firstAfter + 1);
  const tail = d.events.slice(firstAfter + 1);
  const reordered = [...head, ...tail.filter(e => rank(e) !== 2 && e.kind !== 'run_ended' && !e.kind.startsWith('update_')),
    ...tail.filter(e => rank(e) === 2 || e.kind.startsWith('update_')), ...tail.filter(e => e.kind === 'run_ended')];
  const b = play(reordered);
  const shape = run => Object.fromEntries(Object.entries(run.lists).map(([k, l]) => [k, l.filter(it => it.type !== 'paused' && it.type !== 'resumed')
    .map(it => `${it.type}:${it.name || ''}:${it.state}`)]));
  assert.deepEqual(shape(b), shape(a));
  assert.deepEqual(b.band, a.band);
});

test('a cancelled update branch: its search has no result and is closed on run_ended', () => {
  const run = play(load('update-branch-cancelled').events);
  assert.equal(run.ended.state, 'failed');
  const search = run.lists.update.find(it => it.type === 'tool' && it.name === 'search_web_updates');
  assert.ok(search && !search.result);
  assert.equal(search.state, 'stopped');
  assert.equal(run.band, null);
  assert.equal(run.update.ended, null);
});

test('interrupted: the stored steps stay, no band, closed', () => {
  const run = play(load('interrupted-run').events);
  assert.equal(run.ended.state, 'interrupted');
  assert.equal(run.band, null);
});

test('pause and resume are steps, run-wide', () => {
  const run = play(load('pause-and-resume').events);
  const all = Object.values(run.lists).flat();
  assert.equal(all.filter(it => it.type === 'paused').length, 1);
  assert.equal(all.filter(it => it.type === 'resumed').length, 1);
});

test('retries are lines inside their step, and a call out of retries fails its step', () => {
  const run = play(load('retries-anthropic-and-voyage-recovered').events);
  const all = Object.values(run.lists).flat();
  assert.ok(all.some(it => it.type === 'call' && it.lines.some(l => l.kind === 'retry') && it.state === 'done' && callVisible(it)));
  assert.ok(run.composition.item.lines.some(l => l.kind === 'retry'));
  assert.ok(all.some(it => it.type === 'tool' && it.name === 'search_meaning' && it.lines.some(l => l.kind === 'retry')));
  const ex = play(load('error-stopped-loop-retries-exhausted').events);
  assert.ok(ex.lists.research.some(it => it.type === 'call' && it.state === 'failed' && it.lines.some(l => l.kind === 'failed')));
  assert.equal(answerLabels(ex).top, 'error_stopped');
});

test('a call that waits is shown; one that answered at once is not', () => {
  const run = createRun();
  const d = load('answered-phone-location-records');
  apply(run, d.events[0]); apply(run, d.events[1]);
  assert.ok(callVisible(run.lists.research[0]));
  apply(run, d.events[2]);
  assert.ok(!callVisible(run.lists.research[0]));
});

test('wrong-step calls are refused items in the step they were made in', () => {
  const s = play(load('step-limit-stop').events);
  const w = s.lists.research.find(it => it.wrongStep);
  assert.equal(w.name, 'search_web_updates');
  assert.equal(w.state, 'rejected');
  const u = play(load('update-refused-calls-withheld').events);
  const r = u.lists.update.find(it => it.wrongStep);
  assert.equal(r.name, 'submit_answer');
  assert.match(JSON.stringify(r.input), /statement withheld/);
});

test('the band comes at once when the update step does not start', () => {
  for (const name of ['out-of-scope-reply', 'band-unavailable-credit-flag-at-start', 'step-limit-stop']) {
    const d = load(name);
    const bandAt = d.events.findIndex(e => e.kind === 'update_band');
    const compAt = d.events.findIndex(e => e.kind === 'composition_started');
    assert.ok(bandAt > 0);
    if (compAt > 0) assert.ok(bandAt < compAt);
    const run = play(d.events);
    assert.equal(run.update.started, false);
  }
});

test('the reconnect fixture continues the same run exactly', () => {
  const src = load('answered-phone-location-records');
  const tail = load('answered-phone-location-records-after-n185');
  const a = play(src.events);
  const b = play([...src.events.filter(e => e.n <= tail.after), ...tail.events]);
  assert.deepEqual([...b.keeps], [...a.keeps]);
  assert.deepEqual(b.band, a.band);
  assert.equal(b.blocks.length, a.blocks.length);
});

test('stop labels: limits at the top, cut off and incomplete at the end', () => {
  assert.equal(answerLabels(play(load('step-limit-stop').events)).top, 'step_limit');
  assert.equal(answerLabels(play(load('time-limit-stop').events)).top, 'time_limit');
  assert.equal(answerLabels(play(load('answer-cut-off-length-limit').events)).end, 'cut_off');
  assert.equal(answerLabels(play(load('composition-incomplete-stream-broken').events)).end, 'incomplete');
  const f = play(load('composition-failed-before-first-block').events);
  assert.equal(f.composition.item.state, 'failed');
  assert.ok(f.band, 'the update step beside a failed composition still ends with its band');
});

test('estimated attempts are counted for the cost note, Claude and Exa only (P5.4)', () => {
  for (const name of full) {
    const d = load(name);
    const run = play(d.events);
    const want = d.events.filter(e => e.kind === 'paid_call' && e.data.estimated && e.data.service !== 'voyage').length;
    assert.equal(run.estimated, want, name);
  }
  assert.ok(play(load('composition-failed-before-first-block').events).estimated > 0, 'a fixture with an estimate');
  assert.equal(play(load('answered-phone-location-records').events).estimated, 0, 'an ordinary run has none');
});

test('the estimate note counts attempts (P5.4)', async () => {
  const { COST_ESTIMATED } = await import('../../web/js/text.js');
  assert.equal(COST_ESTIMATED(1), 'Includes this site’s estimate for 1 attempt that reported no usage.');
  assert.equal(COST_ESTIMATED(3), 'Includes this site’s estimate for 3 attempts that reported no usage.');
});
