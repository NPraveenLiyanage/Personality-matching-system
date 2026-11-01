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


# Words that are also ordinary English. A name token equal to one of these is masked only as part of the full name (or a
# capitalised exact repeat), never everywhere, so "Will" or "Mark" cannot blank ordinary words and "and" is never touched.
_COMMON = frozenset("""and the for with from that this will mark may june april august grace hope joy rose mae art ray bill rob
frank grant hunter major miles page pat sue ted tom van victor wade ward young long strong brown green white black gray king
lane field hall park bank case chance dean earl faith guy jack jay jo june lee max nick pearl rich rock rod sky sunny west""".split())
_LABELLED = re.compile(
    r"(?im)^([ 	]*(?:date of birth|d\.?o\.?b\.?|born|birth ?date|address|home address|permanent address|residential address|"
    r"nic|n\.i\.c\.?|national id(?: card)?(?: no\.?| number)?|id (?:no\.?|number)|passport(?: no\.?| number)?|"
    r"nationality|marital status|gender|age)[ 	]*[:\-–][ 	]*)(.+)$")
_NIC = re.compile(r"(?<![\w])(?:\d{9}[VvXx]|\d{12})(?![\w])")
_PASSPORT = re.compile(r"(?<![\w])[A-Z]{1,2}\d{6,8}(?![\w])")
_HANDLE = re.compile(r"(?<![\w@])@[A-Za-z0-9_.]{3,}|\bskype\s*[:\-]\s*\S+", re.I)
_INSTITUTION = re.compile(
    r"\b(?:(?:University|College|Institute|Academy|School|Polytechnic) of [A-Z][\w&'’-]*(?: (?:of )?[A-Z][\w&'’-]*)*"
    r"|[A-Z][\w&'’-]*(?: [A-Z][\w&'’-]*)* (?:University|College|Institute|Academy|Polytechnic)(?: of [A-Z][\w&'’-]*)?)")
_COMPANY = re.compile(
    r"\b[A-Z][\w&'’-]*(?: [A-Z][\w&'’-]*)*,? (?:\(Pvt\)\.? ?Ltd\.?|Pvt\.? ?Ltd\.?|\(Private\) Limited|Private Limited|"
    r"Limited|Ltd\.?|PLC|Plc|Inc\.?|LLC|Corp\.?|Corporation|GmbH|Co\.)(?=\W|$)")


def _names_phrase(n: str) -> str:
    return r"\s+".join(re.escape(w) for w in n.split())


def redact(text: str, names: list[str] | None = None, hide: list[str] | None = None, orgs: bool = False) -> str:
    """Minimise identifiers before text leaves the machine. Layout is kept. This is NOT anonymisation (see PRIVACY_ROUTING.md).

    Removes emails, links, phone numbers, @handles, national IDs, passport numbers, labelled lines (date of birth, address, NIC,
    passport, nationality, marital status, gender, age), the participant's own name (full name, then each name token; tokens that
    are ordinary words only as part of the full name), anything in `hide` (employers, schools, referees the caller names), and,
    when `orgs` is true (off by default so frozen benchmark text is unchanged; on for real participants), institution names ("... University", "University of ...") and company names ending in Ltd/PLC/Inc etc.
    """
    t = re.sub(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", "[email]", text)
    t = re.sub(r"(?:https?://|www\.)\S+|\b(?:linkedin|github)\.com/\S*", "[link]", t, flags=re.I)
    t = _HANDLE.sub("[handle]", t)
    t = _LABELLED.sub(lambda m: m.group(1) + "[removed]", t)
    t = _NIC.sub("[id]", t)
    t = _PASSPORT.sub("[id]", t)
    t = re.sub(r"(?<![\w.])\+?\d[\d ()./-]{5,}\d(?![\w])",
               lambda m: m.group(0) if _looks_like_date(m.group(0)) else "[phone]", t)
    for h in sorted({x.strip() for x in (hide or []) if x and len(x.strip()) >= 3}, key=len, reverse=True):
        t = re.sub(rf"(?<!\w){_names_phrase(h)}(?!\w)", "[hidden]", t, flags=re.I)
    for n in names or []:
        n = (n or "").strip()
        if not n:
            continue
        if len(n) >= 3:                 # a 1-2 letter "name" must not blank every "a" or "of"
            ci = 0 if any(w.casefold() in _COMMON for w in n.split()) else re.I
            t = re.sub(rf"(?<!\w){_names_phrase(n)}(?!\w)", "[name]", t, flags=ci)
        for tok in re.findall(r"[^\W\d_]{3,}", n):
            if tok.casefold() in _COMMON:
                t = re.sub(rf"(?<!\w){re.escape(tok)}(?!\w)", "[name]", t) if tok[:1].isupper() and tok.casefold() not in {
                    "and", "the", "for", "with", "from", "that", "this"} else t
            else:
                t = re.sub(rf"(?<!\w){re.escape(tok)}(?!\w)", "[name]", t, flags=re.I)
    if orgs:
        t = _COMPANY.sub("[employer]", t)
        t = _INSTITUTION.sub("[institution]", t)
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
