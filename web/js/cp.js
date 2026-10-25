// Offsets from the backend are Python code points; JavaScript strings count UTF-16 units (frontend brief §5).
// A character outside the Basic Multilingual Plane is one code point and two units, so the two differ after it.

// The UTF-16 index in `s` of code point offset `cp` (clamped to the string's end).
export function cpToUnit(s, cp) {
  let unit = 0, n = 0;
  while (n < cp && unit < s.length) {
    const c = s.charCodeAt(unit);
    unit += c >= 0xd800 && c <= 0xdbff && unit + 1 < s.length ? 2 : 1;
    n++;
  }
  return unit;
}

// [start, end) code point pairs to UTF-16 pairs, in one pass.
export function rangesToUnits(s, ranges) {
  return ranges.map(([a, b]) => [cpToUnit(s, a), cpToUnit(s, b)]);
}
