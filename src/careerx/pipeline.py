"""Convenience wiring shared by the notebook, the app and the tests.

Real participants are never built in. The app ships three made-up demo people (data/demo); real CVs and
PersonaMap reports only enter through an upload in the app or a local path passed to `private_profile`
(the git-ignored `private_data/` folder is the conventional place).
"""
from __future__ import annotations

import json
from datetime import date
from functools import lru_cache
from pathlib import Path

import pandas as pd

from . import catalogue, isco, narrowing, scoring
from .lexicon import CONCEPTS
from .profile import Profile, build_profile, extract_pdf_text

ROOT = isco.ROOT
DEMO_DIR = ROOT / "data" / "demo"
PRIVATE_DIR = ROOT / "private_data"          # git-ignored; local real data only
# "Present" in a CV is evaluated at this date so tests and the notebook give the same numbers every run.
REFERENCE_DATE = date(2026, 10, 15)


@lru_cache(maxsize=1)
def get_catalogue() -> pd.DataFrame:
    return catalogue.build_catalogue()


@lru_cache(maxsize=4)
def get_scorer(lexicon: str = "v2") -> scoring.Scorer:
    return scoring.Scorer(get_catalogue(), lexicon=lexicon)


# ---------------------------------------------------------------- demo people (made up)
@lru_cache(maxsize=1)
def _demo_spec() -> list[dict]:
    return json.loads((DEMO_DIR / "demo_profiles.json").read_text(encoding="utf-8"))["people"]


def demo_specs() -> list[dict]:
    """Demo people as plain input specs (the same shape the app stores for uploaded participants)."""
    return [dict(id=p["id"], name=p["name"], cv_text=(DEMO_DIR / p["cv_file"]).read_text(encoding="utf-8"),
                 pm_text=None, personality=p["personality"], demo=True, ref_date=REFERENCE_DATE)
            for p in _demo_spec()]


def profile_from_spec(spec: dict, lexicon: str = "v2", **kw) -> Profile:
    """Build a Profile from an input spec. Extra kwargs: interest_ids, passions_text, education_band, ..."""
    return build_profile(spec["name"], spec["cv_text"], spec.get("pm_text") or None, personality=spec.get("personality"),
                         today=spec.get("ref_date"), lexicon=lexicon, **kw)


def demo_ids() -> list[str]:
    return [p["id"] for p in _demo_spec()]


def demo_names() -> dict[str, str]:
    return {p["id"]: p["name"] for p in _demo_spec()}


def demo_profile(which: str = "demo_b", interest_ids: list[str] | None = None, passions_text: str = "",
                 lexicon: str = "v2") -> Profile:
    spec = next(p for p in _demo_spec() if p["id"] == which)
    cv = (DEMO_DIR / spec["cv_file"]).read_text(encoding="utf-8")
    return build_profile(spec["name"], cv, personality=spec["personality"], interest_ids=interest_ids,
                         passions_text=passions_text, today=REFERENCE_DATE, lexicon=lexicon)


# ---------------------------------------------------------------- real people (local only)
def private_profile(cv_path, personamap_path=None, name: str = "Participant", lexicon: str = "v2",
                    today: date | None = None, **kw) -> Profile:
    """Build a profile from real PDFs at the given paths. Nothing is copied or stored."""
    cv = extract_pdf_text(cv_path)
    pm = extract_pdf_text(personamap_path) if personamap_path else None
    return build_profile(name, cv, pm, lexicon=lexicon, today=today, **kw)


def private_files() -> dict[str, Path]:
    """Real files present in the local, git-ignored private_data folder (empty on a fresh clone)."""
    return {p.name: p for p in PRIVATE_DIR.glob("*.pdf")} if PRIVATE_DIR.exists() else {}


def interest_options() -> dict[str, str]:
    """concept id -> label, for the interests intake."""
    return {c.id: c.label for c in CONCEPTS}


def run(profile: Profile, lexicon: str | None = None) -> dict:
    sc = get_scorer(lexicon or getattr(profile, "lexicon", "v2"))
    df = sc.score(profile)
    gate = scoring.sanity_gate(df)
    sl = narrowing.shortlist(df)
    return dict(scores=df, gate=gate, shortlist=sl)


def profile_to_json(p: Profile, path) -> None:
    d = p.summary()
    d["cv_concepts"] = p.cv_concepts
    d["interests"] = p.interests
    d["education_note"] = p.education_note
    with open(path, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2)
