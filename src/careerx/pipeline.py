"""Convenience wiring shared by the notebook, the app and the tests."""
from __future__ import annotations

import json
from datetime import date
from functools import lru_cache

import pandas as pd

from . import catalogue, isco, narrowing, scoring
from .lexicon import CONCEPTS
from .profile import Profile, build_profile, extract_pdf_text

SAMPLE_CV = isco.RAW / "thilakshana_cv.pdf"
SAMPLE_PM = isco.RAW / "thilakshana_personamap.pdf"
# "Present" in the sample CV is evaluated at this date so tests and the notebook give the same numbers every run.
SAMPLE_REFERENCE_DATE = date(2026, 10, 15)


@lru_cache(maxsize=1)
def get_catalogue() -> pd.DataFrame:
    return catalogue.build_catalogue()


@lru_cache(maxsize=1)
def get_scorer() -> scoring.Scorer:
    return scoring.Scorer(get_catalogue())


def sample_profile(interest_ids: list[str] | None = None, passions_text: str = "") -> Profile:
    """Thilakshana R: built from the real CV and PersonaMap PDFs in data/raw."""
    return build_profile("Thilakshana R", extract_pdf_text(SAMPLE_CV), extract_pdf_text(SAMPLE_PM),
                         interest_ids=interest_ids, passions_text=passions_text, today=SAMPLE_REFERENCE_DATE)


def interest_options() -> dict[str, str]:
    """concept id -> label, for the interests intake."""
    return {c.id: c.label for c in CONCEPTS}


def run(profile: Profile) -> dict:
    sc = get_scorer()
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
