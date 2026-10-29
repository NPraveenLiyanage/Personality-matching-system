"""Generate CSV review sheets (open in Excel) for an independent reviewer. All content is synthetic or public catalogue text.

Output: docs/review/*.csv. The answer key for the calibration pairs is written to a separate file the reviewer should not open first.
"""
import csv
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from bench import metrics  # noqa: E402
from careerx import pipeline  # noqa: E402
from careerx.evidence import assess  # noqa: E402

OUT = ROOT / "docs" / "review"
CASE_FILES = ["career_cases.yaml", "career_cases_holdout_v2.yaml"]
CLASSES = "direct | transferable | domain_exposure_only | interest_only | unsupported | insufficient_info"

PAIRS = [  # (snippet, area name, author's class)
    ("Built a hospital patient-management web application using Python, SQL and React (own work, final-year project).", "Nursing & midwifery", "domain_exposure_only"),
    ("Built a hospital patient-management web application using Python, SQL and React (own work, final-year project).", "Software & applications development", "direct"),
    ("Staff Nurse, Lakeview General Hospital (2019 - 2024). Administered medication and monitored patients on a surgical ward. Diploma in Nursing, 2018.", "Nursing & midwifery", "direct"),
    ("PROJECTS: Our team of five built a loan approval web application for a bank. (No personal role described.)", "Software & applications development", "insufficient_info"),
    ("SKILLS: Python, SQL, Machine Learning, TensorFlow. (Nothing else; school leaver.)", "Data science & analytics", "insufficient_info"),
    ("SUMMARY: Interested in becoming a teacher one day. No other experience listed.", "Secondary school teaching", "interest_only"),
    ("Senior Accountant, Crestline Audit Partners (2020 - 2026). Prepared monthly financial statements, led year-end audit fieldwork. Chartered Accountant, 2022.", "Finance, accounting & financial analysis", "direct"),
    ("Software Engineer (2021 - 2026). Built REST APIs in Java for a retail bank's customer accounts platform.", "Finance, accounting & financial analysis", "domain_exposure_only"),
    ("Restaurant Supervisor (2018 - 2026). Earlier: Accounts Clerk, bank branch (2005 - 2009), posted ledger entries and reconciled daily cash.", "Numerical & accounting clerks", "direct"),
    ("SUMMARY: I have no clinical experience and have never worked as an accountant. Operations coordinator in logistics (2020 - 2026).", "Nursing & midwifery", "unsupported"),
]


def write(name: str, header: list[str], rows: list[list]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / name).open("w", newline="", encoding="utf-8-sig") as f:      # utf-8-sig so Excel shows accents correctly
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print("wrote", (OUT / name).relative_to(ROOT), len(rows), "rows")


def main():
    cat = pipeline.get_catalogue()
    nm = dict(zip(cat.area_id, cat.name))

    rows = []
    for fn in CASE_FILES:
        for c in metrics.load_cases(ROOT / "bench" / "cases" / fn):
            fmt = lambda ids: "; ".join(f"{a} {nm[a]}" for a in ids)           # noqa: E731
            rows.append([c["id"], c["split"], ", ".join(c["categories"]), c["cv_text"].strip(), fmt(c["supported"]),
                         fmt(c.get("acceptable", [])), fmt(c.get("traps", [])), c.get("notes", ""), "", "", "", ""])
    write("1_case_expectations_review.csv",
          ["case_id", "split", "categories", "cv_text (invented)", "SHOULD be recommended (author)", "also acceptable (author)",
           "must NOT be recommended as supported (author)", "author notes",
           "REVIEWER: agree with 'should be recommended'? (yes/no/partly)", "REVIEWER: areas to add/remove (supported)",
           "REVIEWER: agree with 'must not' list? (yes/no/partly)", "REVIEWER: comments"], rows)

    defs = assess.load_definitions()
    rows = [[aid, d["name"], d["cluster"], d["definition"], " | ".join(d["typical_activities"]), " | ".join(d["evidence_examples"]),
             " | ".join(d["common_contextual_confusions"]), " | ".join(d["qualification_gaps"]), d["formal_qualification_required"],
             "", "", ""] for aid, d in defs["areas"].items()]
    write("2_area_definitions_review.csv",
          ["area_id", "name", "cluster", "definition (AI draft)", "typical activities", "example CV evidence", "common confusions",
           "qualification gaps", "formal qualification required", "REVIEWER: definition OK? (yes/edit/wrong)",
           "REVIEWER: corrected text or comment", "REVIEWER: formal qualification/registration really required? (yes/no)"], rows)

    reg = assess.load_regulated()
    write("3_regulated_terms_review.csv",
          ["area_id", "name", "role/qualification terms that count as genuine practice (draft)", "REVIEWER: terms missing?",
           "REVIEWER: terms too broad?", "REVIEWER: comments"],
          [[a, nm[a], "; ".join(t), "", "", ""] for a, t in reg.items()])

    write("4_rubric_calibration_pairs.csv",
          ["pair_no", "cv_snippet (invented)", "career_area", f"REVIEWER: choose one: {CLASSES}", "REVIEWER: comment"],
          [[i, s, a, "", ""] for i, (s, a, _) in enumerate(PAIRS, 1)])
    write("answer_key_do_not_open_first.csv", ["pair_no", "career_area", "author_class"],
          [[i, a, k] for i, (_, a, k) in enumerate(PAIRS, 1)])


if __name__ == "__main__":
    main()
