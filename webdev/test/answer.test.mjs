// The answer renderer (frontend brief §6): citations, flags across blocks, code-point offsets, the straddle fallback.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import markdownit from '../../web/vendor/markdown-it/markdown-it.esm.min.mjs';
import { makeMarkdown, layoutAnswer, textOf } from '../../web/js/answer.js';
import { cpToUnit } from '../../web/js/cp.js';

const md = makeMarkdown(markdownit);
const DIR = new URL('../../tests/fixtures/events/', import.meta.url);
const load = name => JSON.parse(readFileSync(new URL(`${name}.json`, DIR), 'utf8'));
const blk = (index, text, ids = []) => ({ index, text, citations: ids.map(id => ({ passage_id: id, first_sentence: 0, last_sentence: 0, cited_text: '' })) });
function find(nodes, pred, out = []) {
  for (const n of nodes) { if (pred(n)) out.push(n); if (n.kids) find(n.kids, pred, out); }
  return out;
}
const isCited = n => n.t === 'el' && /\bcited\b/.test(n.cls || '');
const strip = s => s.replace(/\s+/g, ' ').trim();

test('cited blocks are underlined spans with a pill per citation; synthesis is bare text', () => {
  const { nodes } = layoutAnswer({ md, blocks: [blk(0, 'Synthesis first. '), blk(1, 'A cited sentence.', ['katz-3-p2', 'smith-1-p16']), blk(2, ' More synthesis.')] });
  const c = find(nodes, isCited);
  assert.equal(c.length, 1);
  assert.equal(c[0].attrs['data-b'], '1');
  const pills = find(c, n => n.tag === 'button');
  assert.deepEqual(pills.map(p => textOf(p.kids)), ['katz-3-p2', 'smith-1-p16']);
  assert.equal(strip(textOf(nodes)), 'Synthesis first. A cited sentence. katz-3-p2smith-1-p16 More synthesis.');
});

test('inline Markdown renders inside its citation underline; headings and lists keep their structure', () => {
  const { nodes, straddled } = layoutAnswer({ md, blocks: [
    blk(0, '## What the Court held\n\n'),
    blk(1, 'In *Katz v. United States*, the Court said **this**.', ['katz-1-p1']),
    blk(2, '\n\n- First point, '), blk(3, 'cited here.', ['katz-1-p2']), blk(4, '\n- Second point.\n'),
  ] });
  assert.deepEqual(straddled, []);
  assert.equal(nodes[0].tag, 'h3', '## moves under the answer heading');
  const c = find(nodes, isCited);
  assert.ok(find(c[0].kids, n => n.tag === 'em').length === 1 && find(c[0].kids, n => n.tag === 'strong').length === 1);
  const li = find(nodes, n => n.tag === 'li');
  assert.equal(li.length, 2);
  assert.ok(find(li[0].kids, isCited).length === 1, 'the citation sits inside the list item');
  assert.ok(!find(nodes, n => n.tag === 'p').some(p => find([p], n => n.tag === 'li').length), 'tight list: no <p> around items');
});

test('the straddle fallback: a citation crossing Markdown structure is plain text, underline and pill intact (T1.11)', () => {
  const blocks = [blk(0, 'Before. '), blk(1, 'The end of one paragraph.\n\nThe start of the next.', ['katz-1-p3']), blk(2, ' After.')];
  const { nodes, straddled } = layoutAnswer({ md, blocks });
  assert.deepEqual(straddled, [1]);
  const c = find(nodes, isCited);
  assert.equal(c.length, 1, 'shown once, not once per paragraph');
  assert.match(c[0].cls, /straddle/);
  assert.equal(strip(textOf(c[0].kids)), 'The end of one paragraph. The start of the next. katz-1-p3');
  assert.equal(find(c, n => n.tag === 'button').length, 1);
  assert.ok(strip(textOf(nodes)).includes('After.'));
});

test('a link or raw HTML in Claude\'s text stays text (T3.7)', () => {
  const { nodes } = layoutAnswer({ md, blocks: [blk(0, 'See [this](https://example.com) and <b>bold</b> <script>x</script>.')] });
  assert.equal(find(nodes, n => n.tag === 'a' || n.tag === 'b' || n.tag === 'script').length, 0);
  assert.match(textOf(nodes), /\[this\]\(https:\/\/example\.com\)/);
  assert.match(textOf(nodes), /<b>bold<\/b>/);
});

test('flags mark exactly their text, across blocks, with code points converted to UTF-16', () => {
  // an astral character (one code point, two UTF-16 units) before the flagged words
  const a = 'Emoji \u{1F600} then *Entick v. Carrington* says ';
  const b = '"a quoted line that spans" blocks.';
  const s0 = [...a].indexOf('E', 7);                     // the code point offset of "Entick"
  const flags = [{ block: 0, start: s0, end_block: 0, end: s0 + 20, kind: 'not_in_corpus', text: 'Entick v. Carrington' },
    { block: 0, start: [...a].length - 5, end_block: 1, end: 26, kind: 'quotation_not_found', text: '' }];
  assert.equal(a.slice(cpToUnit(a, s0), cpToUnit(a, s0 + 20)), 'Entick v. Carrington');
  const { nodes, flagged } = layoutAnswer({ md, blocks: [blk(0, a), blk(1, b, ['katz-1-p4'])], flags });
  const f = find(nodes, n => n.cls === 'flagged');
  const byFlag = j => strip(f.filter(n => n.attrs['data-flag'].split(' ').includes(String(j))).map(n => textOf(n.kids)).join(''));
  assert.equal(byFlag(0), 'Entick v. Carrington');
  assert.equal(byFlag(1), 'says "a quoted line that spans"');
  assert.equal(flagged.length, 2);
  assert.equal(find(nodes, n => n.cls === 'flag-note').length, 2, 'one note per flag');
});

test('every fixture answer renders: each cited block once, its text intact, its flags placed', () => {
  for (const name of readdirSync(DIR).filter(f => f.endsWith('.json')).map(f => f.slice(0, -5))) {
    const d = load(name);
    const blocks = d.events.filter(e => e.kind === 'answer_block').map(e => e.data);
    if (!blocks.length) continue;
    const checks = d.events.find(e => e.kind === 'checks');
    const flags = checks ? checks.data.flags : [];
    const { nodes, flagged } = layoutAnswer({ md, blocks, flags });
    const citedBlocks = blocks.filter(b => b.citations.length).map(b => String(b.index));
    const spans = find(nodes, isCited).map(n => n.attrs['data-b']);
    assert.deepEqual([...new Set(spans)].sort(), [...citedBlocks].sort(), `${name}: every cited block has its span`);
    for (const f of flags) {
      const placed = find(nodes, n => n.cls === 'flagged').map(n => strip(textOf(n.kids))).join(' ');
      assert.ok(placed.includes(strip(f.text).slice(0, 12)), `${name}: flag "${f.text}" placed`);
    }
    assert.equal(flagged.length, flags.length, `${name}: every flag has its note`);
  }
});

test('review fixes: a table, an indented block and a fenced block stay text, and a citation in them keeps its underline', () => {
  for (const blocks of [
    [blk(0, 'Intro.\n\n| Case | Year |\n|---|---|\n| Katz | '), blk(1, '1967', ['katz-1-p1']), blk(2, ' |\n')],
    [blk(0, 'Intro.\n\n    '), blk(1, 'The Court said this.', ['katz-1-p1']), blk(2, '\n\nAfter.')],
    [blk(0, 'Intro.\n\n```\n'), blk(1, 'The Court said this.', ['katz-1-p1']), blk(2, '\n```\n')],
  ]) {
    const { nodes } = layoutAnswer({ md, blocks });
    assert.equal(find(nodes, isCited).length, 1);
    assert.equal(find(nodes, n => n.tag === 'table' || n.tag === 'pre' || n.tag === 'code').length, 0);
  }
});

test('review fixes: an entity cannot decode to a sentinel and fake, cut or hide a flag', () => {
  const a = 'He wrote &#xF000;fake&#xF400; and "a search of the home is &#xF400;unreasonable" here.';
  const q = a.indexOf('"a search');
  const flags = [{ block: 0, start: q, end_block: 0, end: a.indexOf(' here'), kind: 'quotation_not_found', text: '' }];
  const { nodes } = layoutAnswer({ md, blocks: [blk(0, a)], flags });
  const f = find(nodes, n => n.cls === 'flagged');
  assert.equal(f.length, 1);
  assert.equal(textOf(f[0].kids), '"a search of the home is &#xF400;unreasonable"');
  assert.ok(textOf(nodes).includes('&#xF000;fake&#xF400;'), 'the entities stay as Claude wrote them');
  assert.doesNotThrow(() => layoutAnswer({ md, blocks: [blk(0, 'x &#xF000; y')] }));
});
