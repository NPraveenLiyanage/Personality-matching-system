"""Profile builder: CV text + PersonaMap report + intake -> structured Profile."""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .lexicon import CONCEPTS, CONCEPT_BY_ID

POLE_TO_DIM = {  # label -> (dimension, is_first_pole)
    "extroverted": ("E", True), "introverted": ("E", False),
    "intuition": ("N", True), "sensing": ("N", False),
    "feeling": ("F", True), "thinking": ("F", False),
    "judging": ("J", True), "perceiving": ("J", False),
}
DIM_NAMES = {"E": "Extroversion", "N": "Intuition", "F": "Feeling", "J": "Judging"}


@dataclass
class Profile:
    name: str
    cv_text: str = ""
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
    import fitz
    if isinstance(src, (str, Path)):
        doc = fitz.open(str(src))
    else:
        doc = fitz.open(stream=src, filetype="pdf")
    return "\n".join(p.get_text() for p in doc)


# ---------------------------------------------------------------- CV -> concepts
def detect_concepts(text: str, weight: float = 1.0) -> dict:
    """Which lexicon concepts the text evidences, with strength 0..1 and the phrases that triggered it.

    raw      = distinct_triggers_hit + 0.3 * extra_occurrences
    strength = raw / (raw + 4)          # saturating but graded: 1 hit ~0.20, 3 hits ~0.43, 6 hits ~0.60
    """
    out = {}
    for c in CONCEPTS:
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
    r"(?:(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{4})|(present|current|now))",
    re.I)


def estimate_years(text: str, today: date | None = None) -> float:
    """Sum of month-ranges inside the WORK EXPERIENCE section (projects are not counted)."""
    today = today or date.today()
    m = re.search(r"(work experience|professional experience|employment|experience)\s*\n", text, re.I)
    seg = text
    if m:
        rest = text[m.end():]
        end = re.search(r"\n\s*(technical skills|skills|projects|education|references|certifications)\s*\n",
                        rest, re.I)
        seg = rest[:end.start()] if end else rest
    months = 0
    for r in _RANGE.finditer(seg):
        m1, y1 = _MONTHS[r.group(1).lower()[:3]], int(r.group(2))
        if r.group(5):
            m2, y2 = today.month, today.year
        else:
            m2, y2 = _MONTHS[r.group(3).lower()[:3]], int(r.group(4))
        months += max(0, (y2 - y1) * 12 + (m2 - m1) + 1)
    return round(months / 12, 1)


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
    dims: dict[str, float] = {}
    balanced: list[str] = []
    for m in re.finditer(r"(\d{1,3})\s*%\s*(Extroverted|Introverted|Intuition|Sensing|Feeling|Thinking|"
                         r"Judging|Perceiving)\b", text, re.I):
        dim, first = POLE_TO_DIM[m.group(2).lower()]
        pct = float(m.group(1))
        dims.setdefault(dim, pct if first else 100 - pct)
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
                  today: date | None = None) -> Profile:
    cv_text = strip_references(cv_text)
    p = Profile(name=name, cv_text=cv_text)
    p.cv_concepts = detect_concepts(cv_text)
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

    ints = {i: 1.0 for i in (interest_ids or []) if i in CONCEPT_BY_ID}
    if passions_text.strip():
        for cid, v in detect_concepts(passions_text).items():
            ints[cid] = max(ints.get(cid, 0.0), min(1.0, v["strength"] + 0.4))   # stated, so boosted
    p.interests = ints
    p.passions_text = passions_text
    p.interests_known = bool(ints)
    return p
