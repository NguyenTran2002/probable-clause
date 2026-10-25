// Replays (brief §7.4, T4.4 #11, T5.6): a recorded run's events, played by the same code as a live run, at their
// recorded pace (t_ms), from a static file on the web service. A replay never calls the API. "Skip to the end"
// plays the rest at once.

export function playReplay(events, onEvent, onDone) {
  let i = 0, skipping = false, stopped = false, timer = null;
  const start = performance.now();
  function next() {
    if (stopped) return;
    while (i < events.length) {
      const ev = events[i];
      const due = ev.t_ms - (performance.now() - start);
      if (!skipping && due > 0) { timer = setTimeout(next, Math.min(due, 1000)); return; }
      i++;
      try { onEvent(ev, { quiet: skipping }); } catch (e) { console.error(e); }   // one event's fault never ends the replay
    }
    onDone();
  }
  next();
  return {
    skip() { if (stopped || skipping) return; skipping = true; clearTimeout(timer); next(); },
    stop() { stopped = true; clearTimeout(timer); },
  };
}
