// The wake protocol (brief §8.5, T3.6, contract §5.1), on the page.
// 1. One /health check in flight at a time, each waiting up to WAKE_CHECK_TIMEOUT_S, WAKE_CHECK_GAP_S apart.
// 2. Any answer that isn't our JSON means the server is still starting: Cloud Run's plain text, goodnight's HTML,
//    a network error or a timeout all lead to the next serial check.
// 3. The landing check is fire and forget; a wake for a run joins it while it is open.
// 4. A run's own wake starts a fresh check when none is open, so POST /runs follows a /health that just answered.
// 5. The long wait: the elapsed time from the start, LONG_WAIT_S, then WAKE_GIVE_UP_S, where checking stops.
// No DOM: the caller is told what to show. `fetchFn` and `now` are seams for Node's tests.

export function isOurHealth(status, contentType, body) {
  if (status !== 200 || !/application\/json/.test(contentType || '')) return null;
  try {
    const j = JSON.parse(body);
    return j && j.app === 'probable-clause' && j.ready === true ? j : null;
  } catch { return null; }
}

export function createWaker(cfg, { fetchFn = (...a) => fetch(...a), now = () => Date.now(), sleep } = {}) {
  sleep = sleep || (ms => new Promise(r => setTimeout(r, ms)));
  let open = null;            // the wake in progress: {promise, started, listeners}
  let checks = 0;             // for tests: how many /health requests were made, never two at once
  let inFlight = 0, maxInFlight = 0;

  async function oneCheck() {
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), cfg.WAKE_CHECK_TIMEOUT_S * 1000);
    checks++; inFlight++; maxInFlight = Math.max(maxInFlight, inFlight);
    try {
      const r = await fetchFn('api/health', { cache: 'no-store', signal: ctl.signal });
      const body = await r.text();
      return isOurHealth(r.status, r.headers.get('content-type'), body);
    } catch { return null; } finally { clearTimeout(timer); inFlight--; }
  }

  function start() {
    const w = { started: now(), listeners: new Set(), gaveUp: false, long: false };
    w.promise = (async () => {
      for (;;) {
        const health = await oneCheck();
        if (health) return health;
        const waited = (now() - w.started) / 1000;
        if (waited >= cfg.WAKE_GIVE_UP_S) { w.gaveUp = true; throw new Error('gave_up'); }
        await sleep(cfg.WAKE_CHECK_GAP_S * 1000);
      }
    })().finally(() => { if (open === w) open = null; });
    open = w;
    return w;
  }

  return {
    // fire and forget, on landing (brief §2): the result only tells the landing whether research is paused
    landing() { const w = open || start(); return w.promise.catch(() => null); },
    // a wake someone waits on: joins the open check, or starts a fresh one (rule 4)
    wake(onTick) {
      const w = open || start();
      let timer = null;
      if (onTick) {
        const tick = () => {
          const s = (now() - w.started) / 1000;
          onTick({ elapsed: s, long: s >= cfg.LONG_WAIT_S });
        };
        tick();
        timer = setInterval(tick, 1000);
      }
      return w.promise.finally(() => clearInterval(timer));
    },
    get busy() { return !!open; },
    stats() { return { checks, maxInFlight }; },
  };
}
