"""ISCO-08 loading: structure/definitions workbook and the skill-level workbook."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import openpyxl
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
STRUCTURE_XLSX = RAW / "ISCO-08 EN Structure and definitions.xlsx"
SKILLS_XLSX = RAW / "ISCO-08 88 EN Skills.xlsx"

LEVEL_NAMES = {1: "major", 2: "sub_major", 3: "minor", 4: "unit"}

# Boilerplate that appears in nearly every ISCO definition and carries no meaning.
_BOILERPLATE = [
    r"Tasks performed by [\w\s\-]+ usually include:?",
    r"Tasks performed usually include:?",
    r"Tasks include\s*-?",
    r"Tasks performed by [\w\s\-]+ include:?",
    r"Examples of the occupations classified here:?",
    r"Occupations in this [\w\-\s]+ are classified into the following [\w\-\s]+:?",
    r"Occupations in this [\w\-\s]+ are classified in the following [\w\-\s]+:?",
]


@lru_cache(maxsize=1)
def load_structure() -> pd.DataFrame:
    """One row per ISCO group (major / sub-major / minor / unit) with all text fields."""
    df = pd.read_excel(STRUCTURE_XLSX, sheet_name=0, dtype=str).fillna("")
    df.columns = ["level", "code", "title", "definition", "tasks", "included", "excluded", "notes"]
    df["level"] = df["level"].astype(int)
    df["code"] = df["code"].str.strip()
    df["title"] = df["title"].str.strip()
    df["level_name"] = df["level"].map(LEVEL_NAMES)
    return df


def clean_text(s: str) -> str:
    s = s or ""
    for pat in _BOILERPLATE:
        s = re.sub(pat, " ", s, flags=re.I)
    s = re.sub(r"\(\w\)", " ", s)          # (a) (b) list markers
    s = re.sub(r"[\r\n\-•]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def example_occupations(included: str) -> list[str]:
    """Pull the bullet list of example occupations out of an 'included' cell."""
    out = []
    for line in (included or "").splitlines():
        line = line.strip()
        if line.startswith("-"):
            out.append(line.lstrip("- ").strip())
    return out


@lru_cache(maxsize=1)
def load_skill_levels() -> pd.DataFrame:
    """ISCO-08 major group -> ISCO skill level, parsed from the ILOSTAT workbook.

    The workbook is a nested (forward-filled) table: skill level -> aggregate -> major -> sub-major.
    Skill 3 = "levels 3 and 4 (high)", 2 = medium, 1 = low, 4 = armed forces / n.e.c.
    """
    ws = openpyxl.load_workbook(SKILLS_XLSX, read_only=True).worksheets[0]
    rows = list(ws.iter_rows(values_only=True))[2:]     # first two rows are headers
    skill = skill_label = major = major_label = None
    recs = []
    for r in rows:
        if r[0] not in (None, ""):
            skill, skill_label = str(r[0]), r[1]
        if r[4] not in (None, ""):
            major, major_label = str(r[4]), r[5]
        if r[6] in (None, ""):
            continue
        recs.append(dict(skill_level=int(skill), skill_label=skill_label, major=major,
                         major_label=major_label, sub_major=str(r[6]), sub_major_label=r[7]))
    return pd.DataFrame(recs)


def major_skill_band() -> dict[str, int]:
    """{'1': 3, '2': 3, ..., '9': 1}. Armed forces ('0') maps to 4 (n.e.c.) and is excluded later."""
    sk = load_skill_levels()
    return sk.drop_duplicates("major").set_index("major")["skill_level"].to_dict()


def minor_groups() -> pd.DataFrame:
    s = load_structure()
    return s[s.level == 3].reset_index(drop=True)


def unit_groups() -> pd.DataFrame:
    s = load_structure()
    return s[s.level == 4].reset_index(drop=True)


def units_of(minor_code: str) -> pd.DataFrame:
    u = unit_groups()
    return u[u.code.str.startswith(minor_code)]
