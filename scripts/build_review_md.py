"""ONE-OFF generator for the review tables inside docs/PROJECT_REVIEW.md (section 7).

docs/PROJECT_REVIEW.md is hand-edited by the project owner and maintained by edits afterwards. Running this script writes a
fresh copy to docs/PROJECT_REVIEW.generated.md instead, so it can never overwrite reviewer edits. Copy sections across by hand.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from bench import metrics  # noqa: E402
from careerx import pipeline  # noqa: E402
from careerx.evidence import assess  # noqa: E402

CASE_FILES = [("career_cases.yaml", "dev"), ("career_cases_holdout_v2.yaml", "fresh")]


def cell(s) -> str:
    return str(s).replace("|", "/").replace("\n", " ").strip()


def summary_line(cv: str) -> str:
    m = re.search(r"SUMMARY\s*\n\s*(.+)", cv)
    return m.group(1).strip() if m else cv.strip().splitlines()[0]


def main():
    cat = pipeline.get_catalogue()
    nm = dict(zip(cat.area_id, cat.name))
    short = lambda ids: "; ".join(f"{a} {nm[a]}" for a in ids) or "none"      # noqa: E731
    out = ["## 7. Review tables (edit the ✏️ columns)\n"]

    out += ["### 7b. Expected outcomes for each invented CV\n",
            "Full CV text: `bench/cases/*.yaml` or `docs/review/1_case_expectations_review.csv`. Write yes / no / partly and what to change.\n",
            "| Case | Set | What the CV says (summary line) | SHOULD be recommended | Also acceptable | Must NOT be recommended as supported | ✏️ Agree? | ✏️ Changes |",
            "|---|---|---|---|---|---|---|---|"]
    for fn, _ in CASE_FILES:
        for c in metrics.load_cases(ROOT / "bench" / "cases" / fn):
            out.append(f"| {c['id']} | {c['split']} | {cell(summary_line(c['cv_text']))} | {cell(short(c['supported']))} | "
                       f"{cell(short(c.get('acceptable', [])))} | {cell(short(c.get('traps', [])))} |  |  |")

    out += ["\n### 7c. Regulated occupations (need a matching role or qualification to count as genuine practice)\n",
            "| Area | Role / qualification words that count (draft) | ✏️ Missing words | ✏️ Too broad? |", "|---|---|---|---|"]
    for a, t in assess.load_regulated().items():
        out.append(f"| {a} {nm[a]} | {cell(', '.join(t))} |  |  |")

    out += ["\n### 7d. The 94 career-area definitions (AI-drafted, unreviewed)\n",
            "Mark OK / edit / wrong. Full text (activities, examples, confusions): `data/processed/area_definitions_v1.yaml`.\n",
            "| Area | Definition (draft) | Formal qualification required (draft) | ✏️ OK / edit / wrong | ✏️ Corrected text |", "|---|---|---|---|---|"]
    for aid, d in assess.load_definitions()["areas"].items():
        out.append(f"| {aid} {cell(d['name'])} | {cell(d['definition'])} | {'yes' if d['formal_qualification_required'] else 'no'} |  |  |")

    dest = ROOT / "docs" / "PROJECT_REVIEW.generated.md"
    dest.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("wrote", dest.relative_to(ROOT), len(out), "lines")


if __name__ == "__main__":
    main()
