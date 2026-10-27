"""Profile -> the user-message JSON of prompt v1, with identifiers removed from the CV text."""
from __future__ import annotations

import re

from ..profile import Profile

EARLY_BELOW_YEARS = 3.0
EDU_LABEL = {3: "degree-level (ISCO skill levels 3-4)", 2: "diploma / vocational / advanced level (skill level 2)",
             1: "school level (skill level 1)"}
_SIDES = {"E": ("extroverted", "introverted"), "N": ("intuition", "sensing"),
          "F": ("feeling", "thinking"), "J": ("judging", "perceiving")}
_KEYS = {"E": "energy", "N": "information", "F": "decisions", "J": "structure"}


def redact(text: str, names: list[str] | None = None) -> str:
    """Remove emails, URLs, phone numbers and the participant's own name tokens. Layout is kept."""
    t = re.sub(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", "[email]", text)
    t = re.sub(r"(?:https?://|www\.)\S+|\b(?:linkedin|github)\.com/\S*", "[link]", t, flags=re.I)
    t = re.sub(r"(?<![\w.])\+?\d[\d ()./-]{7,}\d(?![\w])",
               lambda m: m.group(0) if _looks_like_date(m.group(0)) else "[phone]", t)
    for n in names or []:
        for tok in re.findall(r"[A-Za-z]{3,}", n):
            t = re.sub(rf"\b{re.escape(tok)}\b", "[name]", t, flags=re.I)
    return t


def _looks_like_date(s: str) -> bool:
    return bool(re.fullmatch(r"\d{4}\s*[-/.]\s*\d{4}", s.strip()))


def strength_word(pct_first: float) -> str:
    d = abs(pct_first - 50)
    return "balanced" if d < 5 else "slight" if d < 15 else "moderate" if d < 30 else "strong"


def personality_json(pers: dict | None) -> dict:
    out = {}
    for d in "ENFJ":
        if not pers:
            out[_KEYS[d]] = {"side": "unknown", "strength": "balanced", "note": "no personality data"}
            continue
        v = float(pers[d])
        strength = strength_word(v)
        side = "balanced" if strength == "balanced" else _SIDES[d][0 if v > 50 else 1]
        item = {"side": side, "strength": strength}
        if strength == "balanced":
            item["note"] = "scale is balanced"
        out[_KEYS[d]] = item
    return out


def build_payload(p: Profile, interest_labels: list[str] | None = None, extra_names: list[str] | None = None) -> dict:
    names = [p.name] + (extra_names or [])
    interests = list(interest_labels or [])
    if p.passions_text.strip():
        interests.append(redact(p.passions_text.strip(), names))
    return {"stage": "early" if p.years_experience < EARLY_BELOW_YEARS else "established",
            "education_band": EDU_LABEL.get(p.education_band, "unknown"),
            "years_experience": round(float(p.years_experience), 1),
            "stated_interests": interests,
            "personality": personality_json(p.personality),
            "cv_text": redact(p.cv_text, names)}
