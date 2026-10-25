// "View API calls" (T4.1, T4.3 #7, T4.5 D): every Messages API exchange that touched one passage, from the exact
// fragments the events carry (never rebuilt on the page), one row each that opens on click, opening at the response
// behind the citation. Each Claude response's exact usage object sits with it; an attempt priced from our estimate
// is labelled as ours. Web results never appear (P1.3). A passage never kept ends with a note that it was not sent
// to the composition call.

import { h, $, jsonNode, clear } from './dom.js';
import { hueOf, cardState } from './model.js';
import * as T from './text.js';

function rowTitle(f) {
  const j = f.json || {};
  if (f.role === 'response' && j.type === 'tool_use') {
    if (j.name === 'keep_passages') return 'Claude kept it';
    if (j.name === 'read_passages') return 'Claude asked to read this part of the opinion';
    return 'Claude asked for the search that returned it';
  }
  if (f.role === 'request' && f.step === 'composition') return 'Sent to the composition call, which has no tools';
  if (f.role === 'request') return 'Our server sent it to Claude';
  if (f.role === 'response' && f.step === 'composition') return 'Claude cited it in the answer';
  return f.role === 'request' ? 'Sent to Claude' : 'Claude’s response';
}
function preview(j) {
  if (!j) return '';
  if (j.type === 'tool_use') return `${j.name}(${JSON.stringify(j.input)})`;
  if (j.type === 'document') return `document: ${(j.source && j.source.content ? j.source.content.length : 0)} text blocks`;
  if (j.type === 'text' && j.citations) return JSON.stringify({ cited_text: j.citations[0] && j.citations[0].cited_text });
  if (j.type === 'text') return JSON.stringify(j.text).slice(0, 160);
  return JSON.stringify(j).slice(0, 160);
}

export function createApiModal(dialog, { cardFor }) {
  const title = $('#api-title', dialog), cardBox = $('#api-card', dialog), steps = $('#api-steps', dialog);

  function open(run, id) {
    title.textContent = T.API_TITLE(id);
    clear(cardBox).append(cardFor(id));
    clear(steps);
    const frags = run.fragments.get(id) || [];
    const rows = [];
    for (const f of frags) {
      const last = rows[rows.length - 1];
      if (last && last.call_no === f.call_no && last.role === f.role) last.parts.push(f);
      else rows.push({ call_no: f.call_no, role: f.role, step: f.step, parts: [f] });
    }
    const cites = run.cited.get(id) || [];
    let opened = null;
    rows.forEach((row, i) => {
      const f0 = row.parts[0];
      const isCite = row.step === 'composition' && row.role === 'response';
      const body = h('div', { class: 'x-body' });
      for (const part of row.parts) {
        body.append(h('p', { class: 'path' }, `${part.role} ${part.call_no}: ${part.path}`));
        const pre = jsonNode(part.json);
        if (isCite) pre.className = `cite ${hueOf(run, id) || ''}`;
        body.append(pre);
      }
      if (row.role === 'response') {
        for (const a of (run.calls.get(row.call_no) || [])) {
          if (a.usage) { body.append(h('p', { class: 'path' }, `${T.API_USAGE} (attempt ${a.attempt})`), jsonNode(a.usage)); }
          else if (a.estimated_usage) { body.append(h('p', { class: 'path' }, `${T.API_ESTIMATED} (attempt ${a.attempt})`), jsonNode(a.estimated_usage)); }
        }
      }
      const where = `${row.role === 'request' ? 'Sent, request' : 'Received, response'} ${row.call_no}`;
      const det = h('details', null,
        h('summary', { class: 'x-head' }, h('b', null, rowTitle(f0)), h('span', null, where), h('code', { class: 'x-preview' }, preview(row.parts[row.parts.length - 1].json))),
        body);
      if (isCite && cites.length) { det.open = true; opened = det; }
      steps.append(h('li', null, det));
      if (i === rows.length - 1 && !opened) opened = det;
    });
    const st = cardState(run, id);
    if (st === 'notkept' || (!run.keeps.has(id) && run.researchDone)) steps.append(h('li', null, h('p', { class: 'x-note' }, T.API_NOT_KEPT)));
    if (!run.ended) steps.append(h('li', null, h('p', { class: 'x-note' }, T.API_STILL)));
    dialog.showModal();
    // open at the exchange that matters: the citation, else the latest (desktop: the traffic column scrolls;
    // a phone: the whole body)
    const wire = $('.dlg-wire', dialog);
    const scroller = [wire, $('.dlg-body', dialog)].find(e => e.scrollHeight > e.clientHeight + 1);
    if (scroller && opened) scroller.scrollTop += opened.closest('li').getBoundingClientRect().top - scroller.getBoundingClientRect().top - 12;
  }
  return { open };
}
