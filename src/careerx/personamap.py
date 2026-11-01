"""PersonaMap report -> structured, minimal data for the work-style fit step.

Only the parts the fit step needs are kept. The cover page, the running page header (which carries the participant's name),
the report date and the explanatory boilerplate are dropped by construction, and the participant's own name is removed from what
remains. Nothing is guessed: whatever cannot be parsed is reported in `warnings` and left out.

The report is about preferences and behavioural tendencies. It describes how a person likes to work, never ability, and it must
never be treated as professional evidence (docs/RUBRIC.md section 6).
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .llm.payload import personality_json, redact
from .profile import parse_personamap as parse_preferences

# Section heading line (exact, whole line) -> key. Order of appearance in the report is not assumed.
HEADINGS = {
    "Personality profile summary": "summary",
    "Your profile": "profile",
    "Your two readings": "readings",
    "What stands out most about you": "stands_out",
    "What sets you apart": "sets_apart",
    "Your strengths": "strengths",
    "Under pressure": "pressure",
    "How you solve problems": "problem_solving",
    "How you would be likely to lead": "leading",
    "Working with others": "working_with_others",
    "Your development priorities": "priorities",
    "In summary": "summary_list",
    "Does this fit?": "fit_note",
}
# What the fit step may read. The two-readings table repeats the profile and the fit note is a prompt to the reader.
SEND = ("summary", "profile", "stands_out", "sets_apart", "strengths", "pressure", "problem_solving", "leading",
        "working_with_others", "priorities", "summary_list")
SECTION_LABEL = {"summary": "Personality profile summary", "profile": "Your profile", "stands_out": "What stands out most",
                 "sets_apart": "What sets you apart", "strengths": "Strengths, effort and drains", "pressure": "Under pressure",
                 "problem_solving": "How you solve problems", "leading": "How you would be likely to lead",
                 "working_with_others": "Working with others", "priorities": "Development priorities",
                 "summary_list": "Summary"}

_STEP_RX = re.compile(r"^([1-4])\.\s+(.+)$")
_STEP_LABELS = re.compile(r"^(fastest step|strong|moderate|slower step|slowest step|most-skipped step|developing|steady|"
                          r"weakest step|least natural step)$", re.I)
_READING_RX = re.compile(r"\b([EI][SN][TF][JP])\s*[—–-]\s*([A-Z][A-Za-z' ]+?)(?=\s{2,}|\s*/|$)")


@dataclass
class PersonaMap:
    preferences: dict | None                       # {"E","N","F","J"} as % of the first pole, plus code/balanced/found
    readings: list[dict] = field(default_factory=list)       # [{"type": "ENFJ", "label": "Connection Builder"}, ...]
    steps: list[dict] | None = None                # [{"step": "Read the situation", "rating": "Fastest step"}, ...]
    sections: dict[str, str] = field(default_factory=dict)   # key -> cleaned text (name removed)
    warnings: list[dict] = field(default_factory=list)

    def has(self, key: str) -> bool:
        return bool(self.sections.get(key, "").strip())

    def report_text(self, keys: tuple[str, ...] = SEND) -> str:
        """Exactly the text the fit step may see. Quotes from the model are validated against this string."""
        return "\n\n".join(f"## {SECTION_LABEL[k]}\n{self.sections[k]}" for k in keys if self.has(k))

    def payload(self) -> dict:
        """Compact structured view for the prompt. Bands come from the same function as the older engines."""
        pers = None
        if self.preferences:
            pers = {d: self.preferences[d] for d in "ENFJ"}
        return {"preferences": personality_json(pers), "balanced": (self.preferences or {}).get("balanced", []),
                "readings": self.readings, "problem_solving_steps": self.steps, "report_text": self.report_text()}


def _drop_running_lines(pages: list[list[str]]) -> list[list[str]]:
    """Lines repeated on many pages (page header and footer) are removed. The header carries the participant's name."""
    n = len(pages)
    if n < 3:
        return pages
    need = max(3, math.ceil(n * 0.5))
    seen = Counter(ln for pg in pages for ln in set(pg))
    return [[ln for ln in pg if seen[ln] < need and not re.fullmatch(r"\d{1,3}", ln)] for pg in pages]


def _cover_facts(first_page: list[str]) -> tuple[str | None, list[dict]]:
    name = None
    for i, ln in enumerate(first_page):
        if ln.lower() == "prepared for" and i + 1 < len(first_page):
            name = first_page[i + 1]
            break
    readings = []
    for i, ln in enumerate(first_page):
        if ln.lower() == "your two readings" and i + 1 < len(first_page):
            readings = [dict(type=m.group(1), label=m.group(2).strip()) for m in _READING_RX.finditer(first_page[i + 1])]
            break
    return name, readings


def _steps(lines: list[str]) -> tuple[list[dict] | None, str | None]:
    """The four problem-solving steps and the rating the report gives each, matched in order. None when it does not add up."""
    titles = [m.group(2).strip() for ln in lines if (m := _STEP_RX.match(ln))]
    if len(titles) != 4:
        return None, f"found {len(titles)} numbered steps, expected 4"
    last = max(i for i, ln in enumerate(lines) if _STEP_RX.match(ln))
    labels = [ln for ln in lines[last + 1:] if _STEP_LABELS.match(ln)]
    if len(labels) != 4:
        return None, f"found {len(labels)} recognised step ratings, expected 4"
    return [dict(step=t, rating=r) for t, r in zip(titles, labels)], None


def parse_pages(pages: list[str]) -> PersonaMap:
    warns: list[dict] = []
    raw = "\n".join(pages)
    prefs = parse_preferences(raw)
    if not prefs:
        warns.append(dict(code="no_preferences", message="No preference percentages were found."))
    lines = _drop_running_lines([[ln.strip() for ln in pg.splitlines() if ln.strip()] for pg in pages]) if pages else []
    name, readings = _cover_facts([ln.strip() for ln in pages[0].splitlines() if ln.strip()]) if pages else (None, [])

    sections: dict[str, list[str]] = {}
    key = None
    for ln in (l for pg in lines for l in pg):
        k = HEADINGS.get(ln)
        if k and k not in sections:
            key = k
            sections[key] = []
            continue
        if key is not None:           # everything before the first heading is the cover and is dropped
            sections[key].append(ln)
    steps = None
    if "problem_solving" in sections:
        steps, why = _steps(sections["problem_solving"])
        if why:
            warns.append(dict(code="steps_not_parsed", message=why))
    else:
        warns.append(dict(code="missing_section", message="problem_solving"))

    out: dict[str, str] = {}
    for k, body in sections.items():
        text = "\n".join(body)
        out[k] = redact(text, [name]) if name else text
    for k in SEND:
        if k not in out and k != "problem_solving":
            warns.append(dict(code="missing_section", message=k))
    return PersonaMap(prefs, readings, steps, out, warns)


def parse_text(text: str) -> PersonaMap:
    """Plain text with pages separated by form feeds (the format of pdf text dumps and of the test fixtures)."""
    return parse_pages(text.split("\f"))


def parse_pdf(path) -> PersonaMap:
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz
    doc = fitz.open(str(path)) if isinstance(path, (str, Path)) else fitz.open(stream=path, filetype="pdf")   # path or raw bytes
    return parse_pages([pg.get_text() for pg in doc])
