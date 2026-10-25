// The run's event stream (contract §5, §5.1; T3.1, T3.2), read with fetch so the page sees status codes and sets
// Last-Event-ID itself. One connection at a time. While it is open, a heartbeat every HEARTBEAT_INTERVAL_S tells the
// server the page is here; PAGE_WATCHDOG_S of silence (no event, no keep-alive line) means the connection is gone.
// A dropped stream runs the wake protocol, then reattaches from the last event held, so no step is lost or repeated.
// No DOM. `fetchFn` is a seam for Node's tests.

// Server-Sent Events, parsed incrementally: feed text, get {id, event, data} frames and keep-alive comments.
export function createParser(onFrame, onComment) {
  let buf = '', id = null, event = 'message', data = [];
  const line = l => {
    if (l === '') {
      if (data.length) onFrame({ id, event, data: data.join('\n') });
      id = null; event = 'message'; data = [];
      return;
    }
    if (l[0] === ':') { onComment(l); return; }
    const c = l.indexOf(':');
    const field = c < 0 ? l : l.slice(0, c);
    let val = c < 0 ? '' : l.slice(c + 1);
    if (val[0] === ' ') val = val.slice(1);
    if (field === 'id') id = val; else if (field === 'event') event = val; else if (field === 'data') data.push(val);
  };
  return chunk => {
    buf += chunk;
    let i;
    while ((i = buf.search(/\r\n|\r|\n/)) >= 0) {
      const l = buf.slice(0, i);
      buf = buf.slice(i + (buf[i] === '\r' && buf[i + 1] === '\n' ? 2 : 1));
      line(l);
    }
  };
}

// handlers: onEvent(envelope), onState('open' | 'reconnecting' | 'expired' | 'closed'), wake() -> Promise
export function attach(runId, cfg, handlers, { fetchFn = (...a) => fetch(...a), lastN = 0 } = {}) {
  let last = lastN, done = false, stopped = false, ctl = null, beat = null, watchdog = null;
  const base = `api/runs/${encodeURIComponent(runId)}`;

  const stopBeats = () => { clearInterval(beat); beat = null; clearTimeout(watchdog); watchdog = null; };
  const heartbeat = async () => {
    try {
      const r = await fetchFn(`${base}/alive`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ last_event: last }) });
      if (r.status === 404) { /* the run is gone; the stream will say so */ }
    } catch { /* a missed heartbeat is the server's to notice (T3.2) */ }
  };
  const arm = () => {
    clearTimeout(watchdog);
    watchdog = setTimeout(() => { if (ctl) ctl.abort(); }, cfg.PAGE_WATCHDOG_S * 1000);
  };

  async function connect() {
    ctl = new AbortController();
    let r;
    try {
      r = await fetchFn(`${base}/events`, { headers: { 'Last-Event-ID': String(last), Accept: 'text/event-stream' },
        cache: 'no-store', signal: ctl.signal });
    } catch { return 'dropped'; }
    if (r.status === 404) {
      const ct = r.headers.get('content-type') || '';
      if (/application\/json/.test(ct)) { try { const j = await r.json(); if (j.error === 'run_unknown') return 'expired'; } catch { /* not ours */ } }
      return 'dropped';
    }
    if (r.status !== 200 || !/text\/event-stream/.test(r.headers.get('content-type') || '')) return 'dropped';
    handlers.onState('open');
    heartbeat();
    beat = setInterval(heartbeat, cfg.HEARTBEAT_INTERVAL_S * 1000);
    arm();
    const parse = createParser(f => {
      arm();
      let ev;
      try { ev = JSON.parse(f.data); } catch { return; }
      if (!ev || ev.v !== 2 || typeof ev.n !== 'number' || ev.n <= last) return;   // the page plays only v2 (§6)
      last = ev.n;
      handlers.onEvent(ev);
      if (ev.kind === 'run_ended') { done = true; ctl.abort(); }
    }, () => arm());
    const reader = r.body.getReader();
    const dec = new TextDecoder();
    try {
      for (;;) {
        const { value, done: end } = await reader.read();
        if (end) break;
        parse(dec.decode(value, { stream: true }));
      }
    } catch { /* aborted by the watchdog or the end */ }
    stopBeats();
    return done ? 'ended' : 'dropped';
  }

  (async () => {
    for (;;) {
      const how = await connect();
      if (stopped) return;
      if (how === 'ended') { handlers.onState('closed'); return; }
      if (how === 'expired') { handlers.onState('expired'); return; }
      handlers.onState('reconnecting');
      try { await handlers.wake(); } catch { handlers.onState('gave_up'); return; }
      if (stopped) return;
    }
  })();

  return {
    stop() { stopped = true; done = true; stopBeats(); if (ctl) ctl.abort(); },
    get last() { return last; },
  };
}
