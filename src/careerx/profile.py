"""Profile builder: CV text + PersonaMap report + intake -> structured Profile."""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .lexicon import DEFAULT_LEXICON, get_concepts

POLE_TO_DIM = {  # label -> (dimension, is_first_pole)
    "extroverted": ("E", True), "introverted": ("E", False),
    "intuition": ("N", True), "sensing": ("N", False),
    "feeling": ("F", True), "thinking": ("F", False),
    "judging": ("J", True), "perceiving": ("J", False),
}
DIM_NAMES = {"E": "Extroversion", "N": "Intuition", "F": "Feeling", "J": "Judging"}
POLE_NAMES = {"E": ("Extroversion", "Introversion"), "N": ("Intuition", "Sensing"),
              "F": ("Feeling", "Thinking"), "J": ("Judging", "Perceiving")}


def dominant_pole(dim: str, pct_first: float) -> tuple[str, float]:
    """The side the person leans to, with its strength: (E, 30) -> ('Introversion', 70). 50 -> ('Balanced', 50)."""
    if abs(pct_first - 50) < 1:
        return f"{POLE_NAMES[dim][0]} / {POLE_NAMES[dim][1]} (balanced)", 50.0
    return (POLE_NAMES[dim][0], pct_first) if pct_first > 50 else (POLE_NAMES[dim][1], 100 - pct_first)


@dataclass
class Profile:
    name: str
    cv_text: str = ""                                     # references section removed
    raw_cv_text: str = ""                                 # as provided (session memory only, never stored)
    lexicon: str = DEFAULT_LEXICON
    cv_concepts: dict = field(default_factory=dict)      # id -> {"strength": float, "hits": [str]}
    interests: dict = field(default_factory=dict)         # id -> strength (stated passions)
    passions_text: str = ""
    personality: dict | None = None                       # {"E":50,"N":70,"F":55,"J":65}  % of first pole
    personality_code: str = ""
    education_band: int = 2                               # ISCO skill level 1..3 (3 = degree)
    education_note: str = ""
    years_experience: float = 0.0
    interests_known: bool = False

    def summary(self) -> dict:
        return dict(name=self.name, education_band=self.education_band, years_experience=self.years_experience,
                    concepts=len(self.cv_concepts), interests=len(self.interests),
                    personality=self.personality, personality_code=self.personality_code)


# ---------------------------------------------------------------- text extraction
def extract_pdf_text(src) -> str:
    """Text of a PDF given a path or raw bytes (PyMuPDF)."""
    try:
        import pymupdf as fitz            # current name; `import fitz` is deprecated
    except ImportError:                   # older PyMuPDF
        import fitz
    if isinstance(src, (str, Path)):
        doc = fitz.open(str(src))
    else:
        doc = fitz.open(stream=src, filetype="pdf")
    return "\n".join(p.get_text() for p in doc)


# ---------------------------------------------------------------- CV -> concepts
def detect_concepts(text: str, weight: float = 1.0, lexicon: str = DEFAULT_LEXICON) -> dict:
    """Which lexicon concepts the text evidences, with strength 0..1 and the phrases that triggered it.

    raw      = distinct_triggers_hit + 0.3 * extra_occurrences
    strength = raw / (raw + 4)          # saturating but graded: 1 hit ~0.20, 3 hits ~0.43, 6 hits ~0.60
    """
    out = {}
    for c in get_concepts(lexicon):
        distinct, total, hits = 0, 0, []
        for pat in c.triggers:
            ms = list(re.finditer(pat, text, flags=re.I))
            if ms:
                distinct += 1
                total += len(ms)
                hits.append(ms[0].group(0).strip().lower())
        if distinct:
            raw = distinct + 0.3 * (total - distinct)
            strength = raw / (raw + 4) * weight
            out[c.id] = dict(strength=round(strength, 3), hits=hits[:5], n_hits=total)
    return out


def strip_references(text: str) -> str:
    """Drop the REFERENCES section: referees' job titles are not the candidate's experience."""
    m = re.search(r"\n\s*references?\s*\n", text, re.I)
    return text[: m.start()] if m else text


_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_RANGE = re.compile(
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{4})\s*[^\w\s]+\s*"
    r"(?:(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{4})|(present|current|now)|(\d{4}))",
    re.I)


def month_ranges(text: str, today: date | None = None) -> list[tuple[int, int]]:
    """Dated roles in the WORK EXPERIENCE section as (start, end) month indices (year * 12 + month - 1).

    Projects and education are not counted. A year-only end ("Jun 2010 - 2014") is read as December.
    """
    today = today or date.today()
    m = re.search(r"(work experience|professional experience|employment|experience)\s*\n", text, re.I)
    seg = text
    if m:
        rest = text[m.end():]
        end = re.search(r"\n\s*(technical skills|skills|projects|education|references|certifications)\s*\n",
                        rest, re.I)
        seg = rest[:end.start()] if end else rest
    out = []
    for r in _RANGE.finditer(seg):
        m1, y1 = _MONTHS[r.group(1).lower()[:3]], int(r.group(2))
        if r.group(5):
            m2, y2 = today.month, today.year
        elif r.group(6):
            m2, y2 = 12, int(r.group(6))
        else:
            m2, y2 = _MONTHS[r.group(3).lower()[:3]], int(r.group(4))
        start, end = y1 * 12 + m1 - 1, y2 * 12 + m2 - 1
        if end >= start:
            out.append((start, end))
    return out


def estimate_years(text: str, today: date | None = None) -> float:
    """Calendar time covered by dated roles.

    Roles that overlap (a founder who runs several ventures at once, part-time appointments) are merged,
    so the result is years with at least one dated role, never the sum of the individual role lengths.
    """
    covered: set[int] = set()
    for start, end in month_ranges(text, today):
        covered.update(range(start, end + 1))
    return round(len(covered) / 12, 1)


def detect_education(text: str) -> tuple[int, str]:
    """Return (ISCO skill band 1..3, note)."""
    if re.search(r"\bb\.?\s?sc\b|\bbachelor|\bb\.?a\.?\b|\bb\.?eng|\bm\.?sc\b|\bmaster|\bph\.?d|\bmba\b|\bhonou?rs\b|"
                 r"\bundergraduate|\bdegree\b|\buniversity\b", text, re.I):
        return 3, "Tertiary / degree-level education found in CV"
    if re.search(r"\bdiploma|\bhnd\b|\bnvq\b|\ba/?l\b|advanced level|certificate", text, re.I):
        return 2, "Diploma / vocational / advanced-level qualification found in CV"
    return 2, "No clear education found, assumed band 2 (edit if wrong)"


# ---------------------------------------------------------------- PersonaMap
def parse_personamap(text: str) -> dict | None:
    """Pull the four preference percentages out of a PersonaMap report.

    Returns {"E":..,"N":..,"F":..,"J":..} as % of the first pole (Extroverted / iNtuition / Feeling /
    Judging) plus 'code' and 'balanced' (dimensions the report calls evenly balanced), or None.
    """
    poles = r"(Extroverted|Extraverted|Introverted|Intuition|Intuitive|Sensing|Feeling|Thinking|Judging|Perceiving)"
    pole_key = {"extraverted": "extroverted", "intuitive": "intuition"}
    cands: list[tuple[int, str, float]] = []                    # (position in text, dimension, % of first pole)
    layouts = (r"(\d{1,3}(?:\.\d+)?)[ \t]*%[ \t]*" + poles + r"\b",                    # "70% Introverted"
               r"\b" + poles + r"\b[ \t]*[(:\u2013\u2014\-]{0,2}[ \t]*(\d{1,3}(?:\.\d+)?)\s*%")  # "Introverted (70%)"
    for i, rx in enumerate(layouts):
        for m in re.finditer(rx, text, re.I):
            pct, label = (m.group(1), m.group(2)) if i == 0 else (m.group(2), m.group(1))
            label = label.lower()
            dim, first = POLE_TO_DIM[pole_key.get(label, label)]
            v = float(pct)
            if 0 <= v <= 100:
                cands.append((m.start(), dim, v if first else 100 - v))
    dims: dict[str, float] = {}
    balanced: list[str] = []
    for _, dim, v in sorted(cands):                             # first mention in the report wins
        dims.setdefault(dim, v)
    for m in re.finditer(r"(\d{1,3})\s*%\s*[—–\-]+\s*evenly balanced", text, re.I):
        nxt = re.search(r"(Extroverted|Introverted|Intuition|Sensing|Feeling|Thinking|Judging|Perceiving)",
                        text[m.end(): m.end() + 80], re.I)
        if nxt:
            dim, first = POLE_TO_DIM[nxt.group(1).lower()]
            dims.setdefault(dim, 50.0)
            balanced.append(dim)
    if not dims:
        return None
    code = re.search(r"Profile code\s*\n\s*([XEIN SFTJP ]{4,8})", text)
    out = {d: dims.get(d, 50.0) for d in "ENFJ"}
    out["code"] = re.sub(r"\s+", "", code.group(1)) if code else ""
    out["balanced"] = sorted(set(balanced))
    out["found"] = sorted(dims)
    return out


# ---------------------------------------------------------------- assembly
def build_profile(name: str, cv_text: str, personamap_text: str | None = None, personality: dict | None = None,
                  interest_ids: list[str] | None = None, passions_text: str = "",
                  education_band: int | None = None, years_experience: float | None = None,
                  today: date | None = None, lexicon: str = DEFAULT_LEXICON,
                  keep_references: bool = False) -> Profile:
    """keep_references=True is only for the 'what broke' demo: referees' job titles then leak into the evidence."""
    raw_text = cv_text
    cv_text = cv_text if keep_references else strip_references(cv_text)
    p = Profile(name=name, cv_text=cv_text, raw_cv_text=raw_text, lexicon=lexicon)
    p.cv_concepts = detect_concepts(cv_text, lexicon=lexicon)
    band, note = detect_education(cv_text)
    p.education_band = education_band if education_band else band
    p.education_note = note if not education_band else "Set manually"
    p.years_experience = years_experience if years_experience is not None else estimate_years(cv_text, today)

    pm = parse_personamap(personamap_text) if personamap_text else None
    if pm:
        p.personality = {d: pm[d] for d in "ENFJ"}
        p.personality_code = pm.get("code", "")
    elif personality:
        p.personality = {d: float(personality[d]) for d in "ENFJ"}

    known = {c.id for c in get_concepts(lexicon)}
    ints = {i: 1.0 for i in (interest_ids or []) if i in known}
    if passions_text.strip():
        for cid, v in detect_concepts(passions_text, lexicon=lexicon).items():
            ints[cid] = max(ints.get(cid, 0.0), min(1.0, v["strength"] + 0.4))   # stated, so boosted
    p.interests = ints
    p.passions_text = passions_text
    p.interests_known = bool(ints)
    return p
