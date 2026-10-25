"""The sentence splitter (contract §4.A, T1.9).

Claude cites runs of these sentences, so the splitter is conservative: it
splits only where a sentence plainly ends, and in doubt it does not split. A
wrong split cuts a citation in half; a missed split only makes a citation a
little longer.

A sentence ends at ".", "?" or "!" (closing quotation marks or brackets may
follow it), then whitespace, then a capital letter (opening quotation marks or
brackets may come before it), when the token before the stop is:
  - a lowercase word of two or more letters that is not an abbreviation;
  - a number;
  - a closing bracket or quotation mark;
  - a capitalised word of five or more letters that is not an abbreviation.
"\n\n" always ends a sentence. Whitespace after a sentence belongs to it.

Beyond T1.9's rule, in doubt (each declines a split, never adds one):
  - a capitalised word before "?" or "!" may end a title inside a citation
    ("Colb, What Is a Search? Two Conceptual Flaws ..."): no split;
  - no split inside a parenthetical or bracket that closes in the same
    paragraph, which keeps a citation's quoted parenthetical whole;
  - no split before "Cert.", which only continues a citation (the corpus has
    "Pet. for. Cert." once);
  - a lone quotation mark between the stop and the next word (".' \" 3 Wigmore")
    is not taken as a sentence start;
  - a number that opens its sentence, or follows only a section or case label
    ("1. We hold", "\"SEC. 5. That", "No. 82-15. Acting"), labels what follows.

Abbreviations match in any case ("AMEND.", "Paras."), except that a lowercase
word matches only a lowercase entry: "me." is a word, "Me." is Maine.
"""

import re

# T1.9: the legal abbreviations, written as they appear in the corpus. The rule
# reads the last word of each entry, without its period ("U. S." gives "S"),
# in any case, except as the module notes for lowercase words.
# Only lowercase words and capitalised words of five or more letters can end a
# sentence, so those are the entries that change a split; the rest are listed
# for scripts/check_sentences.py's report of splits after an abbreviation.
LEGAL_ABBREVIATIONS: frozenset[str] = frozenset({
    # Signals, references and Latin
    "U. S.", "e. g.", "i. e.", "et al.", "et seq.", "sub nom.", "ex rel.", "op. cit.", "loc. cit.",
    "v.", "vs.", "ads.", "cf.", "Cf.", "id.", "Id.", "ibid.", "Ibid.", "supra", "infra", "etc.", "viz.", "ca.", "approx.",
    # Lowercase parts of a citation
    "n.", "nn.", "p.", "pp.", "c.", "cc.", "ch.", "chs.", "cl.", "cls.", "art.", "arts.", "sec.", "secs.",
    "subd.", "subch.", "subsec.", "pt.", "pts.", "vol.", "vols.", "ed.", "eds.", "ff.", "fol.", "ser.",
    "eff.", "cert.", "reh.", "mem.", "ex.", "repr.", "esp.", "amend.", "para.", "paras.",
    # Reporters, codes and court names
    "How.", "Wall.", "Pet.", "Dall.", "Wheat.", "Johns.", "Cowp.", "Burr.", "Wils.", "Doug.", "Atk.", "Ves.",
    "Salk.", "Mod.", "Raym.", "Stra.", "Taunt.", "Eng.", "Rep.", "St.", "Tr.", "Rptr.", "Supp.", "Ct.", "Cir.",
    "App.", "Div.", "Dist.", "Sup.", "Super.", "Jud.", "Judic.", "Gen.", "Rev.", "Ann.", "Civ.", "Crim.",
    "Proc.", "Prac.", "Evid.", "Stat.", "Stats.", "Pen.", "Tit.", "Art.", "Ch.", "Cl.", "Sec.", "Vol.", "Pt.",
    "Repl.", "Ed.", "Cong.", "Sess.", "Doc.", "Misc.", "Reg.", "Regs.", "Fed.", "Pub.", "Cert.", "Arg.", "Exh.",
    "Pp.", "No.", "Nos.", "Const.", "Amend.", "Amdt.", "Admin.", "Legis.", "Treas.", "Vict.", "Interp.",
    "Contemp.", "Probs.", "Juris.", "Jurid.", "Envtl.", "Regul.", "Transp.", "Constr.", "Prelim.", "Prosec.",
    "Sched.",
    # Firms, offices and titles
    "Co.", "Corp.", "Inc.", "Ltd.", "Bros.", "Ry.", "Ins.", "Mfg.", "Tel.", "Assn.", "Ass'n", "Assoc.", "Dept.",
    "Dep't", "Govt.", "Gov't", "Natl.", "Nat'l", "Intl.", "Int'l", "Univ.", "Mut.", "Comm.", "Comm'n", "Commn.",
    "Commr.", "Comp.", "Indus.", "Invest.", "Equip.", "Pharm.", "Prods.", "Servs.", "Publg.", "Reorg.",
    "Telecomm.", "Phila.", "Mr.", "Mrs.", "Ms.", "Messrs.", "Dr.", "Hon.", "Sen.", "Jr.", "Sr.", "Atty.", "Gov.",
    # Months
    "Jan.", "Feb.", "Mar.", "Apr.", "Aug.", "Sept.", "Oct.", "Nov.", "Dec.",
    # States
    "Ala.", "Ariz.", "Ark.", "Cal.", "Calif.", "Colo.", "Conn.", "Del.", "Fla.", "Ga.", "Haw.", "Ill.", "Ind.",
    "Kan.", "Kans.", "Ky.", "La.", "Md.", "Mass.", "Me.", "Mich.", "Minn.", "Miss.", "Mo.", "Mont.", "Neb.",
    "Nebr.", "Nev.", "Okla.", "Ore.", "Pa.", "Penn.", "Tenn.", "Tex.", "Va.", "Vt.", "Wash.", "Wis.", "Wisc.",
    "Wyo.",
})

_ABBREVIATION_WORDS = frozenset(entry.split()[-1].removesuffix(".") for entry in LEGAL_ABBREVIATIONS)
_ABBREVIATIONS_FOLDED = frozenset(w.lower() for w in _ABBREVIATION_WORDS)
_DASHED_WORD = re.compile(r"[^\W\d_]+(?:[-–—][^\W\d_]+)*")   # letters, joined by hyphens or dashes
_WORDS = re.compile(r"\S+")
_CLOSERS = "\"')]"
_OPENERS = "\"'(["
_NEVER_FIRST = ("Cert.",)        # continues a citation, never begins a sentence
_ROMAN = frozenset("IVXLCDM")
_CANDIDATE = re.compile(r"[.?!][\"')\]]*\s+")
_NUMBER = re.compile(r"\$?\d+(?:[.,:\-–]\d+)*%?")
_LABELS = frozenset({"§", "§§", "SEC.", "Sec.", "SECTION", "Section", "No.", "Nos.", "APPENDIX"})


def split_sentences(text: str) -> list[tuple[int, int]]:
    """[start, end) spans that tile `text` exactly (no gap, no overlap, in order).
    Whitespace after a sentence belongs to that sentence. "\n\n" always ends one."""
    if not text:
        return []
    blank_lines = _blank_lines(text)                                         # cut: where the gap begins
    stops = {m.end(): m.start() for m in _CANDIDATE.finditer(text)}          # cut: the stop's index
    inside = _inside_brackets(text)
    spans, start = [], 0
    for cut in sorted(blank_lines.keys() | stops.keys()):
        if not 0 < cut < len(text):
            continue
        if cut in blank_lines:
            ends = not text[start:blank_lines[cut]].isspace() and blank_lines[cut] > start
        else:
            ends = (_starts_sentence(text, cut) and not text.startswith(_NEVER_FIRST, cut)
                    and not inside[cut] and _ends_sentence(text, stops[cut], start))
        if ends:
            spans.append((start, cut))
            start = cut
    spans.append((start, len(text)))
    return spans


def _blank_lines(text: str) -> dict[int, int]:
    """Each whitespace run holding "\n\n", as {end: start}. Linear: a regex here backtracks on long runs."""
    runs, k = {}, text.find("\n\n")
    while k >= 0:
        a, b = k, k + 2
        while a > 0 and text[a - 1].isspace():
            a -= 1
        while b < len(text) and text[b].isspace():
            b += 1
        runs[b] = a
        k = text.find("\n\n", b)
    return runs


def _is_abbreviation(word: str) -> bool:
    if word.islower():
        return word in _ABBREVIATION_WORDS
    return word.lower() in _ABBREVIATIONS_FOLDED


def _starts_sentence(text: str, k: int) -> bool:
    """A capital letter, perhaps after opening quotation marks or brackets."""
    while k < len(text) and text[k] in _OPENERS:
        k += 1
    return k < len(text) and text[k].isupper()


def _ends_sentence(text: str, i: int, start: int) -> bool:
    """Whether the stop at text[i] ends the sentence begun at `start`, read from the token before it (T1.9)."""
    if i == 0 or text[i - 1].isspace() or text[i - 1] == ".":   # ellipsis rows, ". . ." and "..."
        return False
    j = i
    while j > 0 and not text[j - 1].isspace():
        j -= 1
    token = text[j:i]
    if token[-1] in _CLOSERS:
        return any(ch.isalnum() for ch in token)
    word = token.lstrip(_OPENERS).replace("[", "").replace("]", "")   # "[p]roperty" is "property"
    if _NUMBER.fullmatch(word):   # unless it labels what follows: "1. We hold", "SEC. 5. That"
        before = (m.group(0).strip(_OPENERS + _CLOSERS) for m in _WORDS.finditer(text, start, j))
        return not all(w in _LABELS for w in before if w)
    piece = word
    if _DASHED_WORD.fullmatch(word.replace("'", "")):
        piece = re.split(r"[-–—]", word)[-1]   # "Minneapolis-St" reads as "St"
    if not piece or _is_abbreviation(piece):
        return False
    letters = piece.replace("'", "")
    if not letters.isalpha():
        return False
    if letters.islower():
        return len(letters) >= 2   # a single letter is an abbreviation: "e. g.", "n.", "p.", "c."
    if text[i] != "." or not piece[0].isupper() or len(letters) < 5:
        return False
    return not (letters.isupper() and set(letters) <= _ROMAN)   # "CCLXII" is a numeral


def _inside_brackets(text: str) -> list[bool]:
    """For each position, whether it lies inside a ( ) or [ ] pair that closes before the next blank line."""
    depth = [0] * (len(text) + 2)
    for opening, closing in ("()", "[]"):
        stack = []
        for k, ch in enumerate(text):
            if ch == opening:
                stack.append(k)
            elif ch == closing and stack:
                o = stack.pop()
                depth[o + 1] += 1
                depth[k + 1] -= 1
            elif ch == "\n" and text.startswith("\n\n", k):
                stack.clear()
    inside, level = [], 0
    for d in depth:
        level += d
        inside.append(level > 0)
    return inside
