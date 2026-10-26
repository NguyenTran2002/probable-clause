// Creating elements and setting text (T3.7, T4.2). Nothing from the visitor, Claude, the corpus or the web is ever
// inserted as markup: strings become text nodes, and the only links are built here from fixed or Exa-given URLs.

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

// h('p', {class: 'x', attrs: {...}, on: {click}}, 'text', child, ...)
export function h(tag, props, ...kids) {
  const e = document.createElement(tag);
  if (props) {
    if (props.class) e.className = props.class;
    if (props.attrs) for (const [k, v] of Object.entries(props.attrs)) if (v != null && v !== false) e.setAttribute(k, v === true ? '' : String(v));
    if (props.on) for (const [k, f] of Object.entries(props.on)) e.addEventListener(k, f);
    if (props.text != null) e.textContent = props.text;
  }
  for (const k of kids.flat()) if (k != null && k !== false) e.append(k instanceof Node ? k : document.createTextNode(String(k)));
  return e;
}

// A safe web link: only http and https, opened apart from this page (T3.7).
export function webLink(url, label) {
  let ok = false;
  try { ok = ['http:', 'https:'].includes(new URL(url).protocol); } catch { ok = false; }
  if (!ok) return h('span', null, label);
  return h('a', { attrs: { href: url, target: '_blank', rel: 'noopener noreferrer' } }, label);
}

// A link to one of this site's own pages, relative to this one so it works under any path prefix; a new tab.
export function siteLink(path, label) {
  return h('a', { attrs: { href: path, target: '_blank', rel: 'noopener' } }, label);
}

// Rich text from text.js: strings, {i}, {b}, {a, href}. Every piece is text.
export function rich(parts) {
  return parts.map(p => {
    if (typeof p === 'string') return document.createTextNode(p);
    if (p.i) return h('i', null, p.i);
    if (p.b) return h('strong', null, p.b);
    if (p.a) return webLink(p.href, p.a);
    return null;
  }).filter(Boolean);
}

export function clear(e) { e.replaceChildren(); return e; }

// Only content that just arrived animates; skipping to the end and reattaching must not replay it.
let quiet = false;
export function setQuiet(on) { quiet = on; }
export function fresh(node) {
  if (quiet) return node;
  node.classList.add('fresh');
  setTimeout(() => node.classList.remove('fresh'), 450);
  return node;
}

// sessionStorage holds only the current run's ID (T3.2, T3.7); it may be blocked, and the page works without it.
export const session = {
  get(k) { try { return sessionStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { sessionStorage.setItem(k, v); } catch { /* blocked: reload cannot reattach */ } },
  del(k) { try { sessionStorage.removeItem(k); } catch { /* blocked */ } },
};

// JSON as tokens for "View API calls": pretty-printed, short objects on one line, coloured by kind, all text.
export function jsonNode(v) {
  const pre = h('pre');
  const put = (s, cls) => pre.append(cls ? h('span', { class: cls }, s) : document.createTextNode(s));
  const walk = (x, ind) => {
    const one = JSON.stringify(x);
    if (x === null || typeof x !== 'object' || one.length <= 84) { scalar(one, x); return; }
    const pad = ind + '  ';
    if (Array.isArray(x)) {
      put('[\n');
      x.forEach((y, i) => { put(pad); walk(y, pad); put(i < x.length - 1 ? ',\n' : '\n'); });
      put(ind + ']');
      return;
    }
    const ents = Object.entries(x);
    put('{\n');
    ents.forEach(([k, y], i) => { put(pad); put(JSON.stringify(k), 'k'); put(': '); walk(y, pad); put(i < ents.length - 1 ? ',\n' : '\n'); });
    put(ind + '}');
  };
  // a compact value: colour its strings, numbers and literals
  const scalar = (s) => {
    const re = /("(?:[^"\\]|\\.)*")(\s*:)?|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)|\b(true|false|null)\b/g;
    let at = 0, m;
    while ((m = re.exec(s))) {
      if (m.index > at) put(s.slice(at, m.index));
      if (m[1]) { put(m[1], m[2] ? 'k' : 's'); if (m[2]) put(m[2]); } else put(m[0], 'n');
      at = re.lastIndex;
    }
    if (at < s.length) put(s.slice(at));
  };
  walk(v, '');
  return pre;
}
