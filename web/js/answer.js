// The answer: Claude's Markdown rendered as elements built from text (T1.11, T3.7, T4.2), with each cited text
// block underlined in its passage's hue and the check flags marked where they fall.
//
// How it fits together. The answer streams as text blocks; each block is one Citations text block, cited or not
// (contract §6). Their texts joined are Claude's Markdown. markdown-it parses the joined text for its block
// structure (paragraphs, headings, lists); each structure's inline text is then cut back into the answer blocks it
// came from, and each piece's inline Markdown is rendered on its own, inside its citation's underline. A cited
// block that crosses Markdown structure (part of it in one paragraph, part in the next) is shown as plain text,
// its underline and pills intact: the straddle fallback (T1.11).
//
// No DOM here: layoutAnswer returns a small tree that mount() turns into elements in the browser, so Node's tests
// read the tree. Nothing is ever inserted as markup: every string becomes a text node.

import { cpToUnit } from './cp.js';

const FLAG_OPEN = 0xf000, FLAG_CLOSE = 0xf400;     // sentinels inside one piece's inline text (private use area)
const PUA = /[\ue000-\uf8ff]/g;
// Claude's headings sit under the answer's own heading, so they move down: ## becomes h3 (T1.11).
const HEADINGS = { h1: 'h3', h2: 'h3', h3: 'h4', h4: 'h5', h5: 'h6', h6: 'h6' };

export function makeMarkdown(markdownit) {
  const md = markdownit('default', { html: false, linkify: false, typographer: false });
  md.disable(['link', 'image', 'autolink', 'html_inline', 'html_block', 'linkify', 'reference'], true);
  // Off as well (the review of step 8): tables and code blocks hold text no citation can sit in, and entities
  // could decode to the private-use sentinels below; all three stay plain text, as Claude wrote it.
  md.disable(['table', 'code', 'fence', 'entity'], true);
  return md;
}

const el = (tag, cls, kids = [], attrs) => ({ t: 'el', tag, cls, kids, attrs });
const text = s => ({ t: 'text', s });

// Where, in the joined source, each character of an inline token's content sits. markdown-it strips each line's
// container markers ("## ", "- ", "> ") and indentation; the content is otherwise a subsequence of the source, so
// it is aligned greedily, starting each line past its markers.
const FIRST_LINE = /^[ \t]*(?:>[ \t]?)*[ \t]*(?:(?:[-*+]|\d{1,9}[.)])(?:[ \t]+|$))?(?:#{1,6}(?:[ \t]+|$))?/;
const NEXT_LINE = /^[ \t>]*/;
function align(src, from, to, content) {
  const map = new Array(content.length);
  let r = from + FIRST_LINE.exec(src.slice(from, to))[0].length;
  for (let i = 0; i < content.length; i++) {
    const c = content[i];
    if (c === '\n') {
      const nl = src.indexOf('\n', r);
      if (nl < 0 || nl >= to) { map[i] = Math.min(r, to - 1); continue; }
      map[i] = nl;
      r = nl + 1 + NEXT_LINE.exec(src.slice(nl + 1, to))[0].length;
      continue;
    }
    let k = r;
    while (k < to && src[k] !== c) k++;
    if (k >= to) { map[i] = Math.min(r, to - 1); r++; continue; }     // degraded: never seen with markdown-it
    map[i] = k;
    r = k + 1;
  }
  return map;
}

function blockOf(starts, pos) {
  let lo = 0, hi = starts.length - 1;
  while (lo < hi) { const mid = (lo + hi + 1) >> 1; if (starts[mid] <= pos) lo = mid; else hi = mid - 1; }
  return lo;
}

// blocks: [{index, text, citations}], in order; flags: CheckResult.flags (code points within each block's text);
// hueOf(passage_id) -> 'h1'...; returns {nodes, straddled: [block index], flagged: [{flag, i}]}
export function layoutAnswer({ md, blocks, flags = [], hueOf = () => 'h1' }) {
  blocks = blocks.filter(Boolean).map(b => ({ ...b, text: b.text.replace(PUA, '\ufffd') }));
  const starts = [];
  let src = '';
  for (const b of blocks) { starts.push(src.length); src += b.text; }
  const blockAt = new Map(blocks.map((b, i) => [b.index, i]));

  // flags in source units
  const fl = flags.map((f, j) => {
    const a = blockAt.get(f.block), z = blockAt.get(f.end_block);
    if (a == null || z == null) return null;
    return { j, f, from: starts[a] + cpToUnit(blocks[a].text, f.start), to: starts[z] + cpToUnit(blocks[z].text, f.end) };
  }).filter(Boolean);

  const tokens = md.parse(src, {});
  const lineStarts = [0];
  for (let i = 0; i < src.length; i++) if (src[i] === '\n') lineStarts.push(i + 1);
  const lineAt = n => (n < lineStarts.length ? lineStarts[n] : src.length);

  // pass 1: each inline token's characters, mapped to the source, and which containers each block touches
  const inl = [], byTok = new Map();
  for (const tok of tokens) {
    if (tok.type !== 'inline' || !tok.map) continue;
    const from = lineAt(tok.map[0]), to = lineAt(tok.map[1]);
    const map = align(src, from, to, tok.content);
    inl.push({ tok, map });
    byTok.set(tok, inl.length - 1);
  }
  const touches = new Map();     // block -> set of inline token numbers holding a non-space character of it
  inl.forEach(({ tok, map }, n) => {
    for (let i = 0; i < map.length; i++) {
      if (/\s/.test(tok.content[i])) continue;
      const b = blockOf(starts, map[i]);
      (touches.get(b) || touches.set(b, new Set()).get(b)).add(n);
    }
  });
  const straddled = new Set();
  for (const [b, set] of touches) if (set.size > 1 && blocks[b].citations.length) straddled.add(b);

  // pass 2: build the tree
  const root = [], stack = [{ kids: root, notes: [] }];
  const placed = new Set();      // straddled blocks already shown as plain text
  const flagged = [];
  for (const tok of tokens) {
    const top = stack[stack.length - 1];
    if (tok.nesting === 1) {
      if (tok.hidden) { stack.push({ kids: top.kids, notes: top.notes, hidden: true }); continue; }   // a tight list's <p>
      const node = el(HEADINGS[tok.tag] || tok.tag, null, [], tok.type === 'ordered_list_open' && tok.attrGet('start') ? { start: tok.attrGet('start') } : undefined);
      top.kids.push(node);
      stack.push({ kids: node.kids, node, notes: [] });
      continue;
    }
    if (tok.nesting === -1) {
      if (top.hidden) { stack.pop(); continue; }
      const done = stack.pop();
      const parent = stack[stack.length - 1];
      // a flag's note goes after the top-level structure that holds the flag (T4.3 #5)
      if (stack.length === 1) { parent.kids.push(...done.notes); } else parent.notes.push(...done.notes);
      continue;
    }
    if (tok.type === 'inline') {
      const n = byTok.get(tok);
      if (n == null) { top.kids.push(text(tok.content.replace(PUA, ''))); continue; }    // no source map: as text
      const { map } = inl[n];
      const pieces = [];
      for (let i = 0; i < tok.content.length;) {
        const b = blockOf(starts, map[i]);
        let k = i;
        while (k < tok.content.length && blockOf(starts, map[k]) === b) k++;
        pieces.push({ b, i, k });
        i = k;
      }
      for (const p of pieces) {
        const blk = blocks[p.b];
        if (straddled.has(p.b)) {
          if (placed.has(p.b)) continue;
          placed.add(p.b);
          top.kids.push(cited(blk, p.b, plainWithFlags(blk.text, starts[p.b], fl, flagged, top.notes), hueOf, true));
          continue;
        }
        const raw = tok.content.slice(p.i, p.k);
        if (blk.citations.length) {
          // the pills follow the cited words; the block's trailing space goes after them, before the next block
          const body = raw.replace(/\s+$/, '');
          const inner = inlinePiece(md, body, map.slice(p.i, p.i + body.length), fl, flagged, top.notes);
          top.kids.push(cited(blk, p.b, inner, hueOf, false));
          if (body.length < raw.length) top.kids.push(text(' '));
        } else top.kids.push(...inlinePiece(md, raw, map.slice(p.i, p.k), fl, flagged, top.notes));
      }
      continue;
    }
    if (tok.type === 'fence' || tok.type === 'code_block') {
      top.kids.push(el('pre', null, [el('code', null, [text(tok.content.replace(PUA, ''))])]));
      continue;
    }
    if (tok.type === 'hr') { top.kids.push(el('hr')); continue; }
  }
  return { nodes: root, straddled: [...straddled].map(b => blocks[b].index), flagged };
}

function cited(blk, b, inner, hueOf, plain) {
  const first = blk.citations[0];
  const pills = blk.citations.map((c, ci) => el('button', `pill ${hueOf(c.passage_id) || ''}`.trim(), [text(c.passage_id)],
    { type: 'button', 'data-b': String(blk.index), 'data-ci': String(ci), 'aria-label': `Source ${c.passage_id}` }));
  return el('span', `cited ${hueOf(first.passage_id) || ''}${plain ? ' straddle' : ''}`.trim(), [...inner, text(' '), ...pills],
    { 'data-b': String(blk.index) });
}

// One piece's inline Markdown, with the flags that fall in it marked by sentinels before parsing.
function inlinePiece(md, raw, map, fl, flagged, notes) {
  const marks = [];
  for (const x of fl) {
    for (let i = 0; i < map.length; i++) {
      const pos = map[i];
      if (pos >= x.from && pos < x.to && (i === 0 || !(map[i - 1] >= x.from && map[i - 1] < x.to))) marks.push([i, FLAG_OPEN + x.j]);
      if (pos >= x.from && pos < x.to && (i === map.length - 1 || !(map[i + 1] >= x.from && map[i + 1] < x.to))) marks.push([i + 1, FLAG_CLOSE + x.j]);
    }
  }
  marks.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  let s = '', at = 0;
  for (const [i, code] of marks) { s += raw.slice(at, i) + String.fromCharCode(code); at = i; }
  s += raw.slice(at);
  const out = [];
  const st = [{ kids: out }];
  const open = new Set();
  const emit = str => {
    const kids = st[st.length - 1].kids;
    let buf = '';
    const flush = () => {
      if (!buf) return;
      const t = text(buf);
      kids.push(open.size ? flagSpan([...open], [t], flagged, fl) : t);
      buf = '';
    };
    for (const ch of str) {
      const c = ch.charCodeAt(0);
      if (c >= FLAG_OPEN && c < FLAG_CLOSE + 0x400) {
        flush();
        if (c < FLAG_CLOSE) {
          const j = c - FLAG_OPEN;
          if (!open.has(j)) { open.add(j); noteOnce(j, fl, flagged, notes); }
        } else open.delete(c - FLAG_CLOSE);
        continue;
      }
      buf += ch;
    }
    flush();
  };
  const [tok] = md.parseInline(s, {});
  for (const c of tok ? tok.children : []) {
    if (c.nesting === 1) { const node = el(c.tag); st[st.length - 1].kids.push(node); st.push({ kids: node.kids }); }
    else if (c.nesting === -1) { if (st.length > 1) st.pop(); }
    else if (c.type === 'text') emit(c.content);
    else if (c.type === 'code_inline') { const node = el('code'); st[st.length - 1].kids.push(node); st.push({ kids: node.kids }); emit(c.content); st.pop(); }
    else if (c.type === 'softbreak') emit('\n');
    else if (c.type === 'hardbreak') st[st.length - 1].kids.push(el('br'));
    else if (c.content) emit(c.content);
  }
  return out;
}

function flagSpan(js, kids, flagged, fl) {
  const kinds = js.map(j => fl.find(x => x.j === j).f.kind);
  return el('span', 'flagged', kids, { 'data-flag': js.join(' '), 'data-kind': kinds.join(' ') });
}
function noteOnce(j, fl, flagged, notes) {
  if (flagged.some(x => x.j === j)) return;
  const x = fl.find(y => y.j === j);
  flagged.push({ j, flag: x.f });
  notes.push(el('p', 'flag-note', [], { 'data-flag-note': String(j), 'data-kind': x.f.kind }));
}

// The straddle fallback's plain text, flags marked by their source offsets.
function plainWithFlags(s, base, fl, flagged, notes) {
  const cuts = new Set([0, s.length]);
  for (const x of fl) {
    if (x.to <= base || x.from >= base + s.length) continue;
    cuts.add(Math.max(0, x.from - base)); cuts.add(Math.min(s.length, x.to - base));
  }
  const pts = [...cuts].sort((a, b) => a - b);
  const out = [];
  for (let k = 0; k + 1 < pts.length; k++) {
    const a = pts[k], z = pts[k + 1];
    const js = fl.filter(x => x.from - base <= a && x.to - base >= z).map(x => x.j);
    const t = text(s.slice(a, z));
    if (js.length) { js.forEach(j => noteOnce(j, fl, flagged, notes)); out.push(flagSpan(js, [t], flagged, fl)); } else out.push(t);
  }
  return out;
}

// Plain text of a tree, for tests and for screen readers' labels.
export function textOf(nodes) {
  return nodes.map(nd => (nd.t === 'text' ? nd.s : textOf(nd.kids || []))).join('');
}

// ---------- the browser: the tree to elements ----------
export function mount(nodes, doc = globalThis.document) {
  const frag = doc.createDocumentFragment();
  for (const nd of nodes) frag.append(mountOne(nd, doc));
  return frag;
}
function mountOne(nd, doc) {
  if (nd.t === 'text') return doc.createTextNode(nd.s);
  const e = doc.createElement(nd.tag);
  if (nd.cls) e.className = nd.cls;
  if (nd.attrs) for (const [k, v] of Object.entries(nd.attrs)) e.setAttribute(k, v);
  for (const k of nd.kids) e.append(mountOne(k, doc));
  return e;
}
