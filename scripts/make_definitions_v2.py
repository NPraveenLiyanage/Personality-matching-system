"""Build data/processed/area_definitions_v2.yaml and regulated_areas_v2.yaml from v1 + the reviewer's sections 7d and 7c in docs/PROJECT_REVIEW.md.

v1 files are never edited. v2 keeps every v1 field and adds:
  * area_definitions_v2: `reviewer_scope_note` (the reviewer's corrected text, verbatim) on the 44 areas marked 'edit', and the
    formal-qualification flag where the reviewer corrected it (A018).
  * regulated_areas_v2: the reviewer's "missing words" added to the v1 terms (phrases of up to 4 words only); terms the reviewer calls
    too broad are NOT removed (removing 'nursing' would stop a new-graduate nurse matching), the concern is recorded in `reviewer_concern`.
Status stays 'reviewer_provisional': the review was AI-assisted, not a practitioner's.
"""
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

REVIEW = ROOT / "docs" / "PROJECT_REVIEW.md"


def table_rows(text: str, start: str, end: str | None) -> list[list[str]]:
    sec = text[text.index(start):text.index(end) if end else None]
    return [[c.strip() for c in r.strip().strip("|").split("|")] for r in sec.splitlines() if r.startswith("| A0")]


def main():
    text = REVIEW.read_text(encoding="utf-8")

    defs = yaml.safe_load((ROOT / "data/processed/area_definitions_v1.yaml").read_text(encoding="utf-8"))
    notes, flag_changes = 0, []
    for row in table_rows(text, "### 7d.", None):
        aid = row[0].split()[0]
        verdict, correction, formal = row[3].lower(), row[4], row[2].lower()
        a = defs["areas"][aid]
        if not verdict.startswith("ok"):
            a["reviewer_scope_note"] = correction
            notes += 1
        new_flag = formal.startswith("yes")
        if new_flag != a["formal_qualification_required"]:
            flag_changes.append((aid, a["formal_qualification_required"], new_flag))
            a["formal_qualification_required"] = new_flag
    defs.update(definitions_version="v2", status="reviewer_provisional",
                note="v1 (LLM-drafted) + reviewer scope notes from docs/PROJECT_REVIEW.md 7d. The reviewer was AI-assisted, not a practitioner.")
    (ROOT / "data/processed/area_definitions_v2.yaml").write_text(yaml.safe_dump(defs, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8")
    print("definitions v2:", notes, "scope notes; flag changes:", flag_changes)

    reg = yaml.safe_load((ROOT / "data/processed/regulated_areas_v1.yaml").read_text(encoding="utf-8"))
    added = 0
    for row in table_rows(text, "### 7c.", "### 7d."):
        aid = row[0].split()[0]
        terms = list(reg["areas"][aid])
        for w in re.split(r",|;", row[2]):
            w = w.strip().lower()
            if w and len(w.split()) <= 4 and w not in terms:
                terms.append(w)
                added += 1
        reg["areas"][aid] = terms
        reg.setdefault("reviewer_concern", {})[aid] = row[3]
    reg.update(status="reviewer_provisional", catalogue_version="catalogue_v1",
               note="v1 terms + words the reviewer said were missing. 'Too broad' terms were kept (see reviewer_concern).")
    (ROOT / "data/processed/regulated_areas_v2.yaml").write_text(yaml.safe_dump(reg, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8")
    print("regulated v2:", added, "words added across", len(reg["areas"]), "areas")


if __name__ == "__main__":
    main()
