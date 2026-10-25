// The wake protocol and the stream client (frontend brief §6): one check at a time, anything not our JSON means
// still starting; events in order, reconnect from Last-Event-ID with nothing lost or repeated, the watchdog.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createWaker, isOurHealth } from '../../web/js/wake.js';
import { attach, createParser } from '../../web/js/stream.js';

const HTTP = new URL('../../tests/fixtures/http/', import.meta.url);
const http = name => JSON.parse(readFileSync(new URL(`${name}.json`, HTTP), 'utf8'));
const response = f => new Response(f.body, { status: f.status, headers: f.headers });

test('only our JSON counts as awake: Cloud Run\'s plain text and goodnight\'s HTML mean still starting', () => {
  for (const name of ['cloud-run-429', 'cloud-run-500', 'cloud-run-503', 'gateway-502']) {
    const f = http(name);
    assert.equal(isOurHealth(f.status, f.headers['Content-Type'], f.body), null, name);
  }
  const ok = http('health-ready');
  assert.equal(isOurHealth(ok.status, ok.headers['Content-Type'], ok.body).ready, true);
  for (const name of ['health-paused-day', 'health-paused-month', 'health-unknown']) {
    const f = http(name);
    assert.ok(isOurHealth(f.status, f.headers['Content-Type'], f.body), `${name} is our JSON`);
  }
});

test('the wake: serial checks, the landing check and a run\'s wake share one, give up at WAKE_GIVE_UP_S', async () => {
  let clock = 0;
  const cfg = { WAKE_CHECK_TIMEOUT_S: 60, WAKE_CHECK_GAP_S: 1, LONG_WAIT_S: 90, WAKE_GIVE_UP_S: 300 };
  const answers = ['cloud-run-503', 'gateway-502', 'cloud-run-429', 'health-ready'];
  let calls = 0;
  const fetchFn = async () => { calls++; clock += 5000; return response(http(answers[Math.min(calls - 1, answers.length - 1)])); };
  const w = createWaker(cfg, { fetchFn, now: () => clock, sleep: async ms => { clock += ms; } });
  const landing = w.landing();
  const run = w.wake();
  const [a, b] = await Promise.all([landing, run]);
  assert.equal(a.ready, true);
  assert.equal(b.ready, true);
  assert.equal(calls, 4, 'one chain of checks, not two');
  assert.equal(w.stats().maxInFlight, 1, 'never two checks at once');
  // a later wake starts a fresh check (the /health right before POST /runs)
  await w.wake();
  assert.equal(calls, 5);

  let c2 = 0;
  const never = createWaker(cfg, { fetchFn: async () => { clock += 10_000; c2++; return response(http('cloud-run-503')); }, now: () => clock, sleep: async ms => { clock += ms; } });
  await assert.rejects(never.wake(), /gave_up/);
  assert.ok(c2 >= 20 && c2 <= 40, 'stopped near the five minutes, not forever');
});

// a fake events endpoint: each connection gets the events after its Last-Event-ID; the first drops partway
function sse(events) {
  return events.map(e => `id: ${e.n}\nevent: ${e.kind}\ndata: ${JSON.stringify(e)}\n\n`).join('');
}
function streamOf(text, { stall = false } = {}) {
  const enc = new TextEncoder();
  return new ReadableStream({
    start(c) {
      c.enqueue(enc.encode(': keep-alive\n\n'));
      for (let i = 0; i < text.length; i += 97) c.enqueue(enc.encode(text.slice(i, i + 97)));   // split mid-frame
      if (!stall) c.close();
    },
  });
}

test('the stream: in order, reconnects from Last-Event-ID, nothing lost or repeated, ends on run_ended', async () => {
  const d = JSON.parse(readFileSync(new URL('../../tests/fixtures/events/answered-phone-location-records.json', import.meta.url), 'utf8'));
  const evs = d.events;
  const asked = [];
  let conn = 0;
  const fetchFn = async (url, opts = {}) => {
    if (url.endsWith('/alive')) return new Response(null, { status: 204 });
    const last = Number(opts.headers['Last-Event-ID']);
    asked.push(last);
    conn++;
    // the first connection drops after n = 100; the second replays one event the page already holds
    const from = conn === 2 ? last - 1 : last;
    const part = evs.filter(e => e.n > from && (conn > 1 || e.n <= 100));
    return new Response(streamOf(sse(part)), { status: 200, headers: { 'Content-Type': 'text/event-stream' } });
  };
  const got = [];
  const states = [];
  await new Promise(resolve => {
    attach('run1', { HEARTBEAT_INTERVAL_S: 10, PAGE_WATCHDOG_S: 45 }, {
      onEvent: ev => got.push(ev.n),
      onState: s => { states.push(s); if (s === 'closed') resolve(); },
      wake: async () => {},
    }, { fetchFn });
  });
  assert.deepEqual(asked, [0, 100]);
  assert.deepEqual(got, evs.map(e => e.n), 'every event once, in order');
  assert.ok(states.includes('reconnecting'));
});

test('the stream: a 404 run_unknown is expired; the watchdog drops a silent stream and reattaches', async () => {
  const f = http('get-events-404-run-unknown');
  const states = [];
  await new Promise(resolve => {
    attach('gone', { HEARTBEAT_INTERVAL_S: 10, PAGE_WATCHDOG_S: 45 }, {
      onEvent: () => {}, onState: s => { states.push(s); if (s === 'expired') resolve(); }, wake: async () => {},
    }, { fetchFn: async () => response(f) });
  });
  assert.deepEqual(states, ['expired']);

  let conn = 0;
  const ev = { v: 2, run: 'r', n: 1, t_ms: 0, at: '2026-10-24T22:00:00.000-05:00', kind: 'run_ended', data: {} };
  const handle = await new Promise(resolve => {
    const h = attach('quiet', { HEARTBEAT_INTERVAL_S: 10, PAGE_WATCHDOG_S: 0.05 }, {
      onEvent: () => {}, onState: s => { if (s === 'closed') resolve(h); }, wake: async () => {},
    }, { fetchFn: async (url, opts) => {
      if (url.endsWith('/alive')) return new Response(null, { status: 204 });
      conn++;
      // the first connection goes silent (no event, no keep-alive); the second finishes the run
      const body = conn === 1 ? streamOf('', { stall: true }) : streamOf(sse([ev]));
      return new Response(body, { status: 200, headers: { 'Content-Type': 'text/event-stream' } });
    } });
  });
  assert.equal(conn, 2, 'the watchdog reconnected once');
  handle.stop();
});

test('the SSE parser: frames split anywhere, comments, CRLF', () => {
  const frames = [], comments = [];
  const feed = createParser(f => frames.push(f), c => comments.push(c));
  const text = ': hi\r\nid: 7\r\nevent: x\r\ndata: {"a":1}\r\n\r\nid: 8\nevent: y\ndata: {"b":2}\n\n';
  for (const ch of text) feed(ch);
  assert.deepEqual(frames.map(f => [f.id, f.event, f.data]), [['7', 'x', '{"a":1}'], ['8', 'y', '{"b":2}']]);
  assert.equal(comments.length, 1);
});

test('review fix: an error while drawing an event is not a dropped stream, and run_ended still closes it', async () => {
  const evs = [1, 2, 3].map(n => ({ v: 2, run: 'r', n, t_ms: n, at: '2026-10-24T22:00:00.000-05:00', kind: n === 3 ? 'run_ended' : 'x', data: {} }));
  let gets = 0;
  const states = [];
  await new Promise(resolve => {
    attach('r', { HEARTBEAT_INTERVAL_S: 10, PAGE_WATCHDOG_S: 45 }, {
      onEvent: () => { throw new Error('a drawing bug'); },
      onState: s => { states.push(s); if (s === 'closed') resolve(); },
      wake: async () => {},
    }, { fetchFn: async url => {
      if (url.endsWith('/alive')) return new Response(null, { status: 204 });
      gets++;
      return new Response(streamOf(sse(evs)), { status: 200, headers: { 'Content-Type': 'text/event-stream' } });
    } });
  });
  assert.equal(gets, 1);
  assert.ok(!states.includes('reconnecting'));
});

test('review fix: reconnects that bring nothing back off instead of looping', async () => {
  let gets = 0;
  const waits = [];
  const h = attach('r', { HEARTBEAT_INTERVAL_S: 10, PAGE_WATCHDOG_S: 45 }, {
    onEvent: () => {}, onState: () => {}, wake: async () => {},
  }, { fetchFn: async url => {
    if (url.endsWith('/alive')) return new Response(null, { status: 204 });
    gets++;
    return new Response(streamOf(''), { status: 200, headers: { 'Content-Type': 'text/event-stream' } });
  }, sleep: async ms => { waits.push(ms); if (waits.length >= 4) h.stop(); } });
  await new Promise(r => setTimeout(r, 50));
  assert.deepEqual(waits.slice(0, 4), [1000, 2000, 4000, 8000]);
  assert.ok(gets <= 5);
});

test('review fix: the watchdog also covers a request whose headers never come', async () => {
  let conn = 0;
  const ev = { v: 2, run: 'r', n: 1, t_ms: 0, at: '2026-10-24T22:00:00.000-05:00', kind: 'run_ended', data: {} };
  await new Promise(resolve => {
    attach('hung', { HEARTBEAT_INTERVAL_S: 10, PAGE_WATCHDOG_S: 0.05 }, {
      onEvent: () => {}, onState: s => { if (s === 'closed') resolve(); }, wake: async () => {},
    }, { fetchFn: (url, opts) => {
      if (url.endsWith('/alive')) return Promise.resolve(new Response(null, { status: 204 }));
      conn++;
      if (conn === 1) return new Promise((_, reject) => opts.signal.addEventListener('abort', () => reject(new Error('aborted'))));
      return Promise.resolve(new Response(streamOf(sse([ev])), { status: 200, headers: { 'Content-Type': 'text/event-stream' } }));
    } });
  });
  assert.equal(conn, 2);
});
