"""Parse and validate one model answer against the prompt's hard rules (backend step 1)."""
from __future__ import annotations

import json
import re

STYLES = {"fits", "neutral", "stretch"}
LEVELS = {"ok", "needs_track_record", "below_level"}
BANNED = re.compile(r"\bMBTI\b|Myers[- ]Briggs", re.I)


def norm(s: str) -> str:
    """Whitespace-collapsed text: models rarely reproduce PDF line breaks, so quotes are compared on this form."""
    return re.sub(r"\s+", " ", s).strip()


def extract_json(text: str) -> dict:
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        return json.loads(t)
    except ValueError:
        a, b = t.find("{"), t.rfind("}")
        if a < 0 or b <= a:
            raise ValueError("no JSON object in the answer")
        return json.loads(t[a:b + 1])


def validate(data: dict, cv_text: str) -> tuple[list[str], list[str]]:
    """Return (fatal, quote_problems). Fatal = structure broken: retry. Quote problems can be repaired."""
    fatal, quotes = [], []
    scores = data.get("scores")
    if not isinstance(scores, list):
        return ["`scores` missing"], []
    ids = []
    for s in scores:
        try:
            i = int(s["id"])
            cv = float(s["cv"])
        except (KeyError, TypeError, ValueError):
            fatal.append(f"bad score row {s!r:.80}")
            continue
        if not 1 <= i <= 94:
            fatal.append(f"id {i} outside 1-94")
        if not 0 <= cv <= 100:
            fatal.append(f"cv out of range for id {i}")
        if s.get("style") not in STYLES:
            fatal.append(f"bad style for id {i}")
        if s.get("level") not in LEVELS:
            fatal.append(f"bad level for id {i}")
        ids.append(i)
    if len(set(ids)) != len(ids):
        fatal.append("duplicate ids")
    miss = sorted(set(range(1, 95)) - set(ids))
    if miss:
        fatal.append(f"missing ids {miss[:8]}{'...' if len(miss) > 8 else ''}")
    if not isinstance(data.get("top10_detail"), list):
        fatal.append("`top10_detail` missing")
        return fatal, quotes
    cv_n = norm(cv_text)
    for d in data["top10_detail"]:
        for ev in d.get("evidence") or []:
            q = norm(str(ev.get("quote", "")))
            if not q or q not in cv_n or len(q.split()) > 15:
                quotes.append(f"area {d.get('id')}: quote not an exact substring (or >15 words): {q[:60]!r}")
    if BANNED.search(json.dumps(data)):
        fatal.append("banned term in answer")
    return fatal, quotes


def repair_quotes(data: dict, cv_text: str) -> dict:
    """Drop quotes that are not in the CV; an area left without evidence is capped at 49 (prompt rule 2)."""
    cv_n = norm(cv_text)
    keep = {}
    for d in data.get("top10_detail", []):
        d["evidence"] = [e for e in d.get("evidence") or []
                         if (q := norm(str(e.get("quote", "")))) and q in cv_n and len(q.split()) <= 15]
        keep[int(d["id"])] = len(d["evidence"])
    for s in data["scores"]:
        if float(s["cv"]) >= 50 and keep.get(int(s["id"]), 0) == 0:
            s["cv"] = 49
    return data
