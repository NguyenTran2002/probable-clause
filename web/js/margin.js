// The landing's annotated amendment (the user, Oct 25, 2026). The Fourth Amendment sits large and pale behind the first
// view; margin notes, each the Court's reading of a word (text.js MARGIN_NOTES), write themselves beside the words the
// hero leaves visible, at most two at once, each held and then erased, with a leader to its word's underline. When a
// run starts, the notes erase, the words fall away but "probable cause", which takes the missing "l", and the page moves
// to the run. Reduced motion: two still notes, no exit. The pure parts (the amendment's pieces, where a note fits, its
// leader) take no DOM, for Node's tests.
import * as T from './text.js';

const SVG = 'http://www.w3.org/2000/svg';
// pacing: the user's mock, Oct 25, 2026 (placeholders until the user says otherwise)
const NEW_NOTE_MS = 3600;      // a new note every 3.6 s; the older of two is erased as it starts
const WRITE_MS_PER_CHAR = 45;  // the hand's speed
const EXIT_MS = 2900;          // from a run's start to the run screen: "probable clause" holds about 1.15 s once its "l" lands (1.75 s)

// [words|key] an anchor, {words} the exit's phrase (also an anchor, "probable"), anything else plain text
export function parseAmendment(src) {
  const out = [];
  for (const m of src.matchAll(/\[([^\]|]+)(?:\|([^\]]+))?\]|\{([^}]+)\}|([^[{]+)/g)) {
    if (m[4]) out.push({ text: m[4], key: null });
    else if (m[3]) out.push({ text: m[3], key: 'probable', exit: true });
    else out.push({ text: m[1], key: m[2] || m[1] });
  }
  return out;
}

export const hit = (a, b, pad = 0) => a.x < b.x + b.w + pad && a.x + a.w + pad > b.x && a.y < b.y + b.h + pad && a.y + a.h + pad > b.y;

// The free spot nearest the word on a 16px grid: inside the bounds, clear of the hero, the word, the things to avoid
// and every note on screen (and its word); notes may sit over the pale print. null when nothing is near enough.
export function findSpot(word, size, { bounds, hero, avoid = [], notes = [], step = 16, margin = 12 }) {
  let best = null, bd = Infinity;
  for (let y = bounds.y + margin; y + size.h <= bounds.y + bounds.h - margin; y += step) {
    for (let x = bounds.x + margin; x + size.w <= bounds.x + bounds.w - margin; x += step) {
      const r = { x, y, w: size.w, h: size.h };
      if (hit(r, hero, 10) || hit(r, word, 6) || avoid.some(a => hit(r, a, 10))) continue;
      if (notes.some(o => hit(r, o.r, 20) || hit(r, o.w, 6))) continue;
      const d = Math.hypot(x + size.w / 2 - (word.x + word.w / 2), y + size.h / 2 - (word.y + word.h / 2));
      if (d < bd) { bd = d; best = r; }
    }
  }
  return best && bd <= Math.max(260, size.w * 1.4) ? best : null;
}

// The leader, from the note's nearest edge: from below or beside it ends on the underline's middle (y = u), from
// above just over the word's ascenders; it meets the word square on (upright from above or below, level from the side).
export function leaderPath(r, w, u, fs) {
  const cx = Math.min(Math.max(w.x + w.w / 2, r.x + 8), r.x + r.w - 8);
  const cy = Math.min(Math.max(w.y + w.h / 2, r.y + 8), r.y + r.h - 8);
  const x1 = r.x + r.w <= w.x ? r.x + r.w + 4 : r.x >= w.x + w.w ? r.x - 4 : cx;
  const y1 = r.y + r.h <= w.y ? r.y + r.h + 2 : r.y >= w.y + w.h ? r.y - 2 : cy;
  const above = y1 < w.y, below = y1 > w.y + w.h;
  const x2 = above || below ? Math.min(Math.max(x1, w.x + 4), w.x + w.w - 4) : x1 < w.x ? w.x : w.x + w.w;
  const y2 = above ? u - fs * 0.95 : u;
  const qx = above || below ? x2 : (x1 + x2) / 2, qy = above || below ? (y1 + y2) / 2 : y2;
  return `M${x1},${y1} Q${qx},${qy} ${x2},${y2}`;
}

export function createMargin(first, { notes = T.MARGIN_NOTES } = {}) {
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const hero = first.querySelector('.hero'), more = first.querySelector('.more');
  const amend = document.createElement('div');
  amend.className = 'amend';
  amend.setAttribute('aria-hidden', 'true');
  const para = amend.appendChild(document.createElement('p'));
  const leads = document.createElementNS(SVG, 'svg');
  leads.setAttribute('class', 'leads');
  leads.setAttribute('aria-hidden', 'true');
  first.prepend(amend, leads);
  const motion = document.createElement('button');
  motion.type = 'button';
  motion.className = 'motion';
  motion.hidden = reduce;
  first.append(motion);

  let timers = [], loop = null, live = [], going = [], paused = false, visible = true, exiting = null;
  const later = (f, ms) => { const t = setTimeout(f, reduce ? 0 : ms); timers.push(t); return t; };
  const box = el => { const a = el.getBoundingClientRect(), b = first.getBoundingClientRect(); return { x: a.left - b.left, y: a.top - b.top, w: a.width, h: a.height }; };
  const heroBox = () => { const b = box(hero), s = getComputedStyle(hero); const px = parseFloat(s.paddingLeft), py = parseFloat(s.paddingTop); return { x: b.x + px, y: b.y + py, w: b.w - 2 * px, h: b.h - 2 * py }; };

  function render() {
    para.replaceChildren();
    for (const seg of parseAmendment(T.AMENDMENT)) {
      const host = seg.key ? para.appendChild(Object.assign(document.createElement('span'), { className: seg.exit ? 'kw pc' : 'kw' })) : para;
      if (seg.key) host.dataset.k = seg.key;
      for (const part of seg.text.split(/(\s+)/)) {
        if (!part) continue;
        if (/^\s+$/.test(part)) host.append(part);
        else host.append(Object.assign(document.createElement('span'), { className: 'wd', textContent: part }));
      }
    }
  }

  function show(note) {
    const span = para.querySelector(`.kw[data-k="${note.at}"]`);
    if (!span) return null;
    const w = box(span), H = heroBox();
    // a word counts as hidden when its middle is under the hero
    if (hit({ x: w.x + w.w * 0.2, y: w.y + w.h * 0.3, w: w.w * 0.6, h: w.h * 0.4 }, H)) return null;
    const n = document.createElement('div');
    n.className = 'note';
    n.setAttribute('aria-hidden', 'true');
    const words = T.noteQuote(note.quote).split(' ').map(t => Object.assign(document.createElement('span'), { textContent: t }));
    const text = n.appendChild(document.createElement('span'));
    text.className = 'nt';
    words.forEach((s, i) => { if (i) text.append(' '); text.append(s); });
    n.append(Object.assign(document.createElement('span'), { className: 'src', textContent: note.cite }));
    if (note.quoting) n.append(Object.assign(document.createElement('span'), { className: 'src', textContent: note.quoting }));
    n.style.visibility = 'hidden';
    first.append(n);
    // the browser's own line breaks become the lines the hand writes, one after another
    const lines = [];
    for (const s of words) { const top = s.offsetTop; if (!lines.length || lines.at(-1).top !== top) lines.push({ top, words: [] }); lines.at(-1).words.push(s.textContent); }
    text.replaceChildren(...lines.map(l => Object.assign(document.createElement('span'), { className: 'ln', textContent: l.words.join(' ') })));
    const r0 = box(n);
    const r = findSpot(w, { w: r0.w, h: r0.h }, { bounds: { x: 0, y: 0, w: first.clientWidth, h: first.clientHeight }, hero: H,
      avoid: [box(more), box(motion)].filter(a => a.w), notes: live });
    if (!r) { n.remove(); return null; }
    n.style.left = `${r.x}px`;
    n.style.top = `${r.y}px`;
    n.style.visibility = '';
    // the underline is 2px tall at 88% down each word's box (the .kw .wd rule)
    const wd = box(span.querySelector('.wd')), fs = parseFloat(getComputedStyle(span).fontSize);
    const p = leads.appendChild(document.createElementNS(SVG, 'path'));
    p.setAttribute('d', leaderPath(r, w, wd.y + (wd.h - 2) * 0.88 + 1, fs));
    const len = p.getTotalLength();
    p.style.strokeDasharray = len;
    p.style.strokeDashoffset = reduce ? 0 : len;
    const o = { note, n, p, span, r, w };
    live.push(o);
    span.classList.add('on');
    let t = 0;
    for (const l of n.querySelectorAll('.ln')) {
      const d = reduce ? 0 : l.textContent.length * WRITE_MS_PER_CHAR;
      l.style.transitionDuration = `${d}ms`;
      later(() => l.classList.add('go'), t);
      t += d + 60;
    }
    later(() => { p.style.strokeDashoffset = 0; n.classList.add('cited'); }, t);
    return o;
  }

  function erase(o, fast) {
    live = live.filter(x => x !== o);
    if (!going.includes(o)) going.push(o);
    o.span.classList.remove('on');
    o.n.classList.remove('cited');
    o.p.style.opacity = 0;
    [...o.n.querySelectorAll('.ln')].reverse().forEach((l, i) => {
      l.style.transitionDuration = `${fast ? 220 : 380}ms`;
      later(() => l.classList.remove('go'), i * (fast ? 120 : 260));
    });
    later(() => { o.n.remove(); o.p.remove(); going = going.filter(x => x !== o); }, fast ? 700 : 1500);
  }

  // on a phone the hero fills the first view, so there is no room for notes and no control to show (style.css)
  const narrow = matchMedia('(max-width: 759px)');
  function tick() {
    if (exiting || paused || !visible || document.hidden || narrow.matches) return;
    if (live.length >= 2) erase(live[0]);
    const free = notes.filter(n => !live.some(o => o.note.at === n.at)).sort(() => Math.random() - 0.5);
    for (const n of free) if (show(n)) break;
  }

  function clearAll() {
    timers.forEach(clearTimeout); timers = [];
    clearInterval(loop); loop = null;
    for (const o of live) { o.n.remove(); o.p.remove(); }
    live = []; going = [];
    first.querySelectorAll('.note, .ins').forEach(e => e.remove());
    leads.replaceChildren();
  }

  function setPaused(on) {
    paused = on;
    motion.textContent = on ? T.MOTION_PLAY : T.MOTION_PAUSE;
    motion.setAttribute('aria-pressed', String(on));
  }
  motion.addEventListener('click', () => setPaused(!paused));
  new IntersectionObserver(([e]) => { visible = e.isIntersecting; }, { threshold: 0.35 }).observe(first);
  let resizing = null;
  addEventListener('resize', () => {
    clearTimeout(resizing);
    resizing = setTimeout(() => { if (!exiting) { for (const o of live.slice()) { o.n.remove(); o.p.remove(); o.span.classList.remove('on'); } live = []; } }, 150);
  });

  return {
    start() {
      clearAll();
      exiting = null;
      first.classList.remove('leaving');
      render();
      setPaused(paused);
      if (reduce) { tick(); tick(); return; }
      later(tick, 600);
      later(tick, 2800);
      loop = setInterval(tick, NEW_NOTE_MS);
    },
    stop() { clearAll(); },
    // a run starts: resolves when the run screen should show (at once with reduced motion)
    exit() {
      if (exiting) return exiting;
      clearInterval(loop); loop = null;
      if (reduce) return (exiting = Promise.resolve());
      // nothing more is written once a run starts: drop every pending line, citation and tick, then erase every note
      // still on the page, those already erasing too (their own removal was one of the dropped timers)
      timers.forEach(clearTimeout); timers = [];
      [...live, ...going].forEach(o => erase(o, true));
      first.classList.add('leaving');
      const pc = para.querySelector('.pc');
      for (const w of para.querySelectorAll('.wd')) {
        if (pc && pc.contains(w)) continue;
        const r = Math.random();
        later(() => { w.style.opacity = 0; w.style.transform = `translateY(${10 + r * 16}px)`; }, 250 + r * 650);
      }
      if (pc) {
        later(() => pc.classList.add('lit'), 500);
        // the missing "l" slides into "c|ause" in the page's green, as in the wordmark: the amendment reads "probable clause"
        later(() => {
          const c = pc.querySelectorAll('.wd')[1];
          if (!c || !c.textContent.startsWith('c')) return;
          const ins = Object.assign(document.createElement('span'), { className: 'ins', textContent: 'l' });
          c.replaceChildren('c', ins, c.textContent.slice(1));
          const w = ins.offsetWidth;
          ins.style.width = '0px';
          requestAnimationFrame(() => requestAnimationFrame(() => { ins.style.width = `${w}px`; ins.classList.add('go'); }));
        }, 1150);
      }
      return (exiting = new Promise(res => later(res, EXIT_MS)));
    },
  };
}
