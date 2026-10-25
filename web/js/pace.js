// The step log's pace (the user, Oct 25, 2026): the tool calls of one round can arrive together, so on screen
// each tool call appears at least gapMs after the one before, in live runs and replays alike. Events keep their
// order: anything behind a held tool call waits with it. A quiet event (a replay skipped to the end, a reload
// catching up on stored events) is never held, and first releases whatever is waiting, quietly.
// No DOM: `now` and the timer functions are seams for Node's tests.

export const TOOL_CALL_GAP_MS = 500;   // the user's figure, Oct 25, 2026

export function createPacer(deliver, { gapMs = TOOL_CALL_GAP_MS, now = () => performance.now(),
  setTimer = (f, ms) => setTimeout(f, ms), clearTimer = t => clearTimeout(t) } = {}) {
  const queue = [];
  let lastCall = -Infinity, timer = null, stopped = false, idle = [];

  function drain(force) {
    if (timer !== null) { clearTimer(timer); timer = null; }
    while (queue.length && !stopped) {
      const [ev, opts] = queue[0];
      if (ev.kind === 'tool_call' && !force) {
        const wait = lastCall + gapMs - now();
        if (wait > 0) { timer = setTimer(() => { timer = null; drain(false); }, wait); return; }
      }
      queue.shift();
      if (ev.kind === 'tool_call') lastCall = now();
      try { deliver(ev, force ? { ...opts, quiet: true } : opts); } catch (e) { console.error(e); }   // one event's fault never stalls the rest
    }
    if (!queue.length) { const cbs = idle; idle = []; for (const cb of cbs) cb(); }
  }

  return {
    push(ev, opts = {}) {
      if (stopped) return;
      queue.push([ev, opts]);
      if (opts.quiet) drain(true);
      else if (timer === null) drain(false);
    },
    flush() { if (!stopped) drain(true); },
    // runs once nothing is waiting: a replay or a run ends on screen only after its last event is shown
    whenIdle(cb) { if (stopped) return; if (queue.length) idle.push(cb); else cb(); },
    stop() { stopped = true; if (timer !== null) clearTimer(timer); timer = null; queue.length = 0; idle = []; },
    get waiting() { return queue.length; },
  };
}
