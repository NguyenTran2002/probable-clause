// The cost line (T4.5, T5.2 #5; step 0's split under P4.31): one total for Claude and Exa when the run ends,
// expanding into research, the update check, the answer and Exa. Voyage is carried in the totals for the caps and
// the record, never shown. Replays add the recording date their prices are from.

import { h } from './dom.js';
import * as T from './text.js';

export function renderCosts(totals, replayDate) {
  const d = h('details', { class: 'costs' });
  d.append(h('summary', null, T.costLine(totals)));
  const dl = h('dl', { class: 'params' });
  for (const [label, x] of T.costParts(totals)) dl.append(h('dt', null, label), h('dd', null, T.usd(x)));
  d.append(dl, h('p', null, T.COST_NOTE));
  if (replayDate) d.append(h('p', null, T.COST_REPLAY(replayDate)));
  return d;
}
