// The step log's pace (pace.js): research's tool calls at least the gap apart on screen (1 s here),
// every event in order, quiet events
// never held, and a skip shows everything at once.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { createPacer, TOOL_CALL_GAP_MS } from '../../web/js/pace.js';

// a fake clock whose timers fire only when advanced
function clock() {
  let t = 0, timers = [];
  return {
    now: () => t,
    setTimer: (f, ms) => { const id = { at: t + ms, f }; timers.push(id); return id; },
    clearTimer: id => { timers = timers.filter(x => x !== id); },
    advance(ms) {
      const end = t + ms;
      for (;;) {
        timers.sort((a, b) => a.at - b.at);
        const next = timers[0];
        if (!next || next.at > end) break;
        timers.shift();
        t = next.at;
        next.f();
      }
      t = end;
    },
  };
}
const ev = (n, kind, step = 'research') => ({ n, kind, data: { step } });

test('tool calls that arrive together appear 1 s apart, everything in order', () => {
  const c = clock();
  const shown = [];
  const p = createPacer((e, o) => shown.push([e.n, c.now(), !!o.quiet]), { ...c, gapMs: 1000 });
  p.push(ev(1, 'round_started'));
  p.push(ev(2, 'tool_call'));
  p.push(ev(3, 'tool_result'));
  p.push(ev(4, 'tool_call'));
  p.push(ev(5, 'tool_result'));
  p.push(ev(6, 'tool_call'));
  assert.deepEqual(shown.map(s => s[0]), [1, 2, 3], 'the first call shows at once; the rest wait behind the second');
  c.advance(999);
  assert.equal(shown.length, 3);
  c.advance(1);
  assert.deepEqual(shown.map(s => [s[0], s[1]]), [[1, 0], [2, 0], [3, 0], [4, 1000], [5, 1000]]);
  c.advance(1000);
  assert.deepEqual(shown.at(-1), [6, 2000, false]);
  assert.equal(p.waiting, 0);
});

test('a tool call already 1 s after the last one is not delayed', () => {
  const c = clock();
  const shown = [];
  const p = createPacer(e => shown.push([e.n, c.now()]), { ...c, gapMs: 1000 });
  p.push(ev(1, 'tool_call'));
  c.advance(1200);
  p.push(ev(2, 'tool_call'));
  assert.deepEqual(shown, [[1, 0], [2, 1200]]);
});

test('a quiet event releases whatever waits, quietly; flush does the same for a skip', () => {
  const c = clock();
  const shown = [];
  const p = createPacer((e, o) => shown.push([e.n, !!o.quiet]), { ...c, gapMs: 1000 });
  p.push(ev(1, 'tool_call'));
  p.push(ev(2, 'tool_call'));
  p.push(ev(3, 'tool_result'));
  p.push(ev(4, 'tool_call'), { quiet: true });
  assert.deepEqual(shown, [[1, false], [2, true], [3, true], [4, true]]);

  const q = createPacer((e, o) => shown.push([e.n, !!o.quiet]), { ...c, gapMs: 1000 });
  shown.length = 0;
  q.push(ev(1, 'tool_call'));
  q.push(ev(2, 'tool_call'));
  q.flush();
  assert.deepEqual(shown, [[1, false], [2, true]]);
});

test('whenIdle waits for the last held event; stop drops everything; a drawing fault never stalls the queue', () => {
  const c = clock();
  const shown = [];
  let ended = false;
  const p = createPacer(e => { shown.push(e.n); if (e.n === 2) throw new Error('a drawing bug'); }, { ...c, gapMs: 1000 });
  const err = console.error; console.error = () => {};
  try {
    p.push(ev(1, 'tool_call'));
    p.push(ev(2, 'tool_call'));
    p.push(ev(3, 'run_ended'));
    p.whenIdle(() => { ended = true; });
    assert.equal(ended, false);
    c.advance(1000);
    assert.deepEqual(shown, [1, 2, 3]);
    assert.equal(ended, true);
  } finally { console.error = err; }

  const s = createPacer(e => shown.push(e.n), { ...c, gapMs: 1000 });
  shown.length = 0;
  s.push(ev(1, 'tool_call'));
  s.push(ev(2, 'tool_call'));
  s.stop();
  c.advance(1000);
  s.push(ev(3, 'tool_call'));
  assert.deepEqual(shown, [1]);
});

test('every fixture, paced: each event once, in order, and research\'s tool calls never closer than the page\'s gap', () => {
  const dir = new URL('../../tests/fixtures/events/', import.meta.url);
  const files = readdirSync(dir).filter(f => f.endsWith('.json'));
  assert.ok(files.length >= 30);
  for (const name of files) {
    const { events } = JSON.parse(readFileSync(new URL(name, dir), 'utf8'));
    const c = clock();
    const shown = [];
    const p = createPacer(e => shown.push([e.n, e.kind, c.now()]), c);
    // events arrive at their recorded times, as a replay plays them
    for (const e of events) { c.advance(Math.max(0, e.t_ms - c.now())); p.push(e); }
    c.advance(60_000);
    assert.deepEqual(shown.map(s => s[0]), events.map(e => e.n), name);
    const step = new Map(events.map(e => [e.n, e.data.step]));
    const paced = shown.filter(s => s[1] === 'tool_call' && step.get(s[0]) === 'research').map(s => s[2]);
    for (let i = 1; i < paced.length; i++) assert.ok(paced[i] - paced[i - 1] >= TOOL_CALL_GAP_MS, `${name}: paced item ${i}`);
  }
});

test('only research is paced: the answer, the update check and their tool calls are never held', () => {
  const c = clock();
  const shown = [];
  const p = createPacer(e => shown.push([e.n, c.now()]), { ...c, gapMs: 1000 });
  p.push(ev(1, 'tool_call'));                   // keep_passages
  c.advance(200);
  p.push(ev(2, 'tool_call'));                   // submit_answer: held until 1 s after step 4
  p.push(ev(3, 'update_started'));
  p.push(ev(4, 'composition_started'));
  p.push(ev(5, 'tool_call', 'update'));          // the update check's submit
  assert.deepEqual(shown.map(s => s[0]), [1]);
  c.advance(800);
  assert.deepEqual(shown.slice(1), [[2, 1000], [3, 1000], [4, 1000], [5, 1000]], 'everything after step 5 arrives with it');
  p.push(ev(6, 'tool_call', 'update'));
  assert.deepEqual(shown.at(-1), [6, 1000]);
});
