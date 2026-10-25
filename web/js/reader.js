// "View source" (T4.1, T4.3 #6, T5.1 #7, T5.2 #6): the whole opinion, fetched from the web service as
// opinions/<opinion_id>.json (never from the API), U.S. Reports page numbers in the margin (above their line on a
// phone), opening with the excerpt centred and its cited sentences lit, with "Back to the excerpt". The reader's
// credit line names the case's actual text source. Offsets in the file are Python code points (contract §11.1).

import { h, $, clear } from './dom.js';
import { cpToUnit, rangesToUnits } from './cp.js';
import { hueOf } from './model.js';
import * as T from './text.js';

const cache = new Map();
async function opinion(id) {
  if (!cache.has(id)) {
    cache.set(id, fetch(`opinions/${encodeURIComponent(id)}.json`, { cache: 'no-cache' }).then(r => {
      if (!r.ok) throw new Error(String(r.status));
      return r.json();
    }).catch(e => { cache.delete(id); throw e; }));
  }
  return cache.get(id);
}

// A paragraph's text cut at sentence boundaries, page breaks and footnote markers, all as text and elements.
function paragraphNodes(text, { sentences = null, breaks = [], refs = [], slip, onRef }) {
  const cuts = new Map();      // unit offset -> [marker nodes]
  const at = (u, node) => { (cuts.get(u) || cuts.set(u, []).get(u)).push(node); };
  for (const b of breaks) at(cpToUnit(text, b.offset), anchor(b.page, slip));
  for (const r of refs) {
    at(cpToUnit(text, r.offset), h('sup', { class: 'fnref' }, h('button', { attrs: { type: 'button', 'aria-label': `Footnote ${r.label}` },
      on: { click: () => onRef(r.footnote_id) } }, r.label)));
  }
  const spans = sentences ? rangesToUnits(text, sentences) : [[0, text.length]];
  const out = [];
  spans.forEach(([a, z], i) => {
    // a marker at a sentence's first character belongs to that sentence (the first sentence's offset 0 is below)
    const points = [...cuts.keys()].filter(u => (u > a || (u === a && i > 0)) && u < z).sort((x, y) => x - y);
    const kids = [];
    let from = a;
    if (i === 0 && cuts.has(0)) kids.push(...cuts.get(0));
    for (const u of points) { kids.push(text.slice(from, u), ...cuts.get(u)); from = u; }
    kids.push(text.slice(from, z));
    if (i === spans.length - 1 && cuts.has(text.length) && text.length > 0) kids.push(...cuts.get(text.length));
    out.push(sentences ? h('span', { class: 'sb', attrs: { 'data-s': i } }, ...kids) : kids);
  });
  return out.flat();
}
// A page marker: an anchor in the text, labelled in the margin by layout() (desktop) or shown inline (phone).
function anchor(page, slip) {
  return h('span', { class: 'pgb', attrs: { 'data-page': page } }, h('span', { class: 'pg-word' }, `${T.PAGE_WORD(slip)} ${page}`));
}

export function createReader(dialog) {
  const title = $('#reader-title', dialog), sub = $('#reader-sub', dialog), body = $('#reader-body', dialog);
  $('#reader-jump', dialog).addEventListener('click', () => toExcerpt(true));
  let opened = null;
  addEventListener('resize', () => { if (dialog.open) layout(); });

  function toExcerpt(smooth) {
    const ex = $('#reader-excerpt', body);
    if (!ex) return;
    body.scrollTo({ top: ex.offsetTop - Math.max(24, (body.clientHeight - ex.offsetHeight) / 2), behavior: smooth ? 'smooth' : 'auto' });
  }

  // margin page numbers, each level with the line its page starts on
  function layout() {
    const col = $('.reader-text', body);
    if (!col) return;
    col.querySelectorAll('.pg').forEach(e => e.remove());
    const top = col.getBoundingClientRect().top;
    let lastY = -Infinity;
    for (const a of col.querySelectorAll('.pgb')) {
      const r = a.getClientRects()[0];
      if (!r) continue;
      const y = r.top - top;
      if (y - lastY < 18) continue;             // two breaks on one line: the first label stands
      lastY = y;
      col.append(h('span', { class: 'pg', attrs: { style: `top:${y}px`, 'aria-hidden': 'true' } }, a.dataset.page));
    }
  }

  async function open(run, id) {
    const p = run.passages.get(id);
    if (!p) return;
    opened = id;
    clear(title).append(h('i', null, p.case_name), `, ${p.citation}`);
    sub.textContent = `${T.typeLabel(p.opinion_type)}. ${T.decided(p.decided)} Opened at ${id}.`;
    clear(body).append(h('p', { class: 'reader-wait' }, T.READER_LOADING));
    dialog.showModal();
    let op;
    try { op = await opinion(p.opinion_id); } catch { clear(body).append(h('p', { class: 'reader-wait' }, T.READER_FAILED)); return; }
    if (opened !== id) return;
    const slip = op.case.slip_opinion;
    const hits = run.cited.get(id) || [];
    const hue = hueOf(run, id);
    const col = h('div', { class: 'reader-text' });
    col.append(h('h3', null, T.typeLabel(op.type)), h('p', { class: 'byline' }, op.heading || T.lineup({ ...op, opinion_type: op.type })));
    let page = null;
    const goRef = fid => { const e = $(`#rd-${CSS.escape(fid)}`, body); if (e) body.scrollTo({ top: e.offsetTop - 24, behavior: 'smooth' }); };
    const excerptOf = (text, nodesFn) => {
      const same = text === p.text;
      const nodes = nodesFn(same ? p.sentences : null);
      const box = h('div', { class: `excerpt${hue ? ' ' + hue : ''}${same && hits.length ? ' focus' : ''}`, attrs: { id: 'reader-excerpt' } },
        h('p', { class: 'ex-label' }, T.EXCERPT(id, same && hits.length > 0)), h('p', { class: 'ex-text' }, ...nodes));
      if (same) for (const sb of box.querySelectorAll('.sb')) { const i = Number(sb.dataset.s); if (hits.some(c => i >= c.first && i <= c.last)) sb.classList.add('hit'); }
      return box;
    };
    for (const para of op.paragraphs) {
      if (para.id === null) { col.append(h('h4', { class: 'section' }, para.text)); continue; }
      const breaks = [];
      if (para.page_start !== page) breaks.push({ offset: 0, page: para.page_start });
      breaks.push(...para.page_breaks);
      page = breaks.length ? breaks[breaks.length - 1].page : page;
      const nodesFn = sentences => paragraphNodes(para.text, { sentences, breaks, refs: para.footnote_refs, slip, onRef: goRef });
      col.append(para.id === id ? excerptOf(para.text, nodesFn) : h('p', null, ...nodesFn(null)));
    }
    if (op.footnotes.length) {
      col.append(h('h4', { class: 'section' }, T.FOOTNOTES_HEADING));
      for (const fn of op.footnotes) {
        const paras = fn.paragraphs.map((t, k) => {
          const breaks = [{ offset: 0, page: fn.page_starts[k] }, ...(fn.page_breaks[k] || [])];
          return { t, nodesFn: sentences => paragraphNodes(t, { sentences, breaks: k === 0 ? breaks : (fn.page_breaks[k] || []), slip, onRef: goRef }) };
        });
        const label = h('span', { class: 'fn-label' }, `${fn.label} `);
        if (fn.id === id) {
          const joined = fn.paragraphs.join('\n\n');
          const box = excerptOf(joined, sentences => {
            if (sentences && paras.length === 1) return [label, ...paras[0].nodesFn(sentences)];
            if (sentences) {
              // several paragraphs: sentence spans over the joined text (each join is a sentence boundary, contract
              // §3), shown with its paragraph breaks; page breaks shifted to the joined text's offsets
              const breaks = [];
              let base = 0;
              fn.paragraphs.forEach((t, k) => {
                if (k === 0) breaks.push({ offset: 0, page: fn.page_starts[0] });
                for (const b of fn.page_breaks[k] || []) breaks.push({ offset: base + b.offset, page: b.page });
                base += [...t].length + 2;
              });
              return [label, ...paragraphNodes(joined, { sentences, breaks, slip, onRef: goRef })];
            }
            return [label, ...paras.flatMap((x, k) => [k ? h('br') : null, ...x.nodesFn(null)])];
          });
          if (paras.length > 1) box.querySelector('.ex-text').classList.add('pre-line');
          box.id = 'reader-excerpt';
          col.append(h('div', { class: 'fnote', attrs: { id: `rd-${fn.id}` } }, box));
        } else {
          col.append(h('div', { class: 'fnote', attrs: { id: `rd-${fn.id}` } }, ...paras.map((x, k) => h('p', null, k === 0 ? label : null, ...x.nodesFn(null)))));
        }
      }
    }
    const foot = h('div', { class: 'reader-foot' }, h('p', null, T.READER_CREDIT[op.case.credit] || ''), h('p', null, T.TEXT_STATUS));
    clear(body).append(col, foot);
    requestAnimationFrame(() => { layout(); toExcerpt(false); });
  }
  return { open };
}
