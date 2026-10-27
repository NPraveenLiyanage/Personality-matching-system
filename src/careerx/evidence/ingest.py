"""CV text -> passages with stable IDs, section, page and a redacted copy; extraction-quality and injection warnings.

Poor extraction and suspicious text only produce warnings. They are never treated as evidence that the participant lacks experience.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..llm.payload import redact
from .schema import Passage

MAX_PASSAGE_CHARS = 700
MIN_TEXT_CHARS = 150

_HEADINGS = [
    ("references", r"references?|referees?"),
    ("experience", r"(?:work |professional |employment |relevant )?(?:experience|history)|employment"),
    ("education", r"education(?: (?:and|&) (?:qualifications?|training))?|academic (?:background|qualifications?)|qualifications?"),
    ("projects", r"(?:personal |academic |key )?projects?"),
    ("skills", r"(?:technical |key |core )?skills?(?: summary)?|competenc(?:y|ies)"),
    ("certifications", r"certifications?|licen[cs]es?|courses|training"),
    ("volunteering", r"volunteer(?:ing)?(?: experience| work)?|community (?:work|service)"),
    ("research", r"research|publications?"),
    ("interests", r"interests?|hobbies|passions?"),
    ("summary", r"summary|profile|objective|about(?: me)?|personal statement"),
]
_HEADING_RES = [(name, re.compile(rf"^(?:{pat})$", re.I)) for name, pat in _HEADINGS]

_INJECTION = re.compile(
    r"ignore (?:all |any |the )?(?:previous|prior|above|earlier)|disregard (?:the |all |any )?(?:previous|above|instructions)|"
    r"system prompt|you are now|new instructions|(?:rank|place|list) me (?:first|top|number one)|"
    r"as an ai|override (?:the )?(?:rules|instructions)|recommend me (?:for|as)\b", re.I)
_MOJIBAKE = re.compile(r"â€|Ã[\x80-\xbf©¨¤]|�|[\x00-\x08\x0b\x0c\x0e-\x1f]")


@dataclass
class Ingest:
    passages: list[Passage]
    warnings: list[dict] = field(default_factory=list)

    def sendable(self) -> list[Passage]:
        """Passages the model may see: references are excluded because referees' titles are not the participant's experience."""
        return [p for p in self.passages if not p.is_reference]


def _heading(line: str) -> str | None:
    s = line.strip().rstrip(":").strip()
    if not s or len(s) > 40:
        return None
    for name, rx in _HEADING_RES:
        if rx.match(s):
            return name
    return None


def _split_long(lines: list[str]) -> list[str]:
    out, cur = [], []
    for ln in lines:
        if cur and sum(len(x) + 1 for x in cur) + len(ln) > MAX_PASSAGE_CHARS:
            out.append("\n".join(cur))
            cur = []
        cur.append(ln)
    if cur:
        out.append("\n".join(cur))
    return out


def ingest_pages(pages: list[str], names: list[str] | None = None) -> Ingest:
    """One string per page (page numbers start at 1). Sections carry over page breaks; passages never span pages."""
    passages: list[Passage] = []
    section = "header"
    for pno, page in enumerate(pages, 1):
        block: list[str] = []

        def flush():
            nonlocal block
            for chunk in _split_long([b for b in block if b.strip()]):
                pid = f"P{len(passages) + 1:03d}"
                passages.append(Passage(pid, section, pno, chunk.strip(), redact(chunk.strip(), names),
                                        is_reference=section == "references"))
            block = []

        for line in page.splitlines():
            h = _heading(line)
            if h:
                flush()
                section = h
            elif not line.strip():
                flush()
            else:
                block.append(line.rstrip())
        flush()
    return Ingest(passages, quality_warnings("\n".join(pages)) + _injection_warnings(passages))


def ingest_text(text: str, names: list[str] | None = None) -> Ingest:
    """Pasted text: no page information (page is None)."""
    ing = ingest_pages([text], names)
    for p in ing.passages:
        p.page = None
    return ing


def ingest_pdf(src, names: list[str] | None = None) -> Ingest:
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz
    doc = fitz.open(str(src)) if isinstance(src, str) or hasattr(src, "__fspath__") else fitz.open(stream=src, filetype="pdf")
    return ingest_pages([pg.get_text() for pg in doc], names)


def quality_warnings(text: str) -> list[dict]:
    out = []
    compact = re.sub(r"\s", "", text)
    if len(compact) < MIN_TEXT_CHARS:
        out.append(dict(code="little_text", message="Very little text was extracted (possibly a scanned or image-only "
                        "document). This is not evidence the participant lacks experience."))
    if compact:
        bad = len(_MOJIBAKE.findall(text))
        letters = sum(c.isalpha() for c in compact)
        if bad / len(compact) > 0.01:
            out.append(dict(code="garbled_text", message="The text contains many broken characters; extraction is unreliable "
                            "and missing evidence must not be read as absence."))
        if letters / len(compact) < 0.5 and len(compact) >= MIN_TEXT_CHARS:
            out.append(dict(code="low_letter_ratio", message="Few letters relative to symbols/digits; the text may be corrupted."))
    return out


def _injection_warnings(passages: list[Passage]) -> list[dict]:
    return [dict(code="possible_instruction_in_cv", passage_id=p.id,
                 message="This passage contains text that looks like an instruction to the system. It is treated as data only.")
            for p in passages if _INJECTION.search(p.text)]
