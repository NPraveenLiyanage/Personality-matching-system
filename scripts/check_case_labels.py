"""Mechanical cross-check of case labels against the frozen catalogue (no model calls, no judgment about CV meaning).

For every case with an ISCO-08 code in `refs` (synth_v2), find which catalogue areas contain that unit group and compare with the
case's supported / acceptable / exploration_only / trap lists. Also checks IDs, overlaps and duplicate IDs across all case files (career_cases_v3.yaml re-versions earlier ids on purpose and is excluded from the duplicate check).
Findings are PROMPTS for a human reviewer, not corrections. Usage: python scripts/check_case_labels.py
"""
from __future__ import annotations

import csv
import glob
import re
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    cat = {r["area_id"]: r for r in csv.DictReader(open(ROOT / "data/processed/career_area_catalogue.csv", encoding="utf-8"))}
    by_unit: dict[str, list[str]] = {}
    for aid, r in cat.items():
        for u in re.findall(r"\d{4}", r["isco_units"] or ""):
            by_unit.setdefault(u, []).append(aid)
    files = sorted(glob.glob(str(ROOT / "bench/cases/career_cases*.yaml")))
    ids = Counter()
    flags = []
    n = 0
    for f in files:
        for c in yaml.safe_load(open(f, encoding="utf-8")) or []:
            if not isinstance(c, dict) or "traps" not in c:
                continue
            n += 1
            if not f.endswith("career_cases_v3.yaml"):    # cases v3 intentionally re-versions c*/v2_* ids with revised expectations
                ids[c["id"]] += 1
            lab = {k: set(c.get(k, [])) for k in ("supported", "acceptable", "exploration_only", "traps")}
            for k, v in lab.items():
                for a in v:
                    if a not in cat:
                        flags.append((c["id"], "unknown area id", a))
            for a in lab["supported"] & lab["traps"]:
                flags.append((c["id"], "supported and trap", a))
            for r in c.get("refs", []):
                m = re.search(r"ISCO-08 (\d{4})", r)
                if not m:
                    continue
                unit = m.group(1)
                areas = set(by_unit.get(unit, []))
                if not areas:
                    flags.append((c["id"], f"ISCO {unit} is in no catalogue area", ""))
                    continue
                want = lab["supported"] | lab["acceptable"]
                if lab["supported"] and not (areas & want):
                    flags.append((c["id"], f"ISCO {unit} maps to {sorted(areas)} but supported={sorted(lab['supported'])}", ""))
                if areas & lab["traps"]:
                    flags.append((c["id"], f"ISCO {unit} maps to a trap area {sorted(areas & lab['traps'])}", ""))
                if areas & lab["exploration_only"] and lab["supported"]:
                    flags.append((c["id"], f"ISCO {unit} maps to exploration-only area {sorted(areas & lab['exploration_only'])}", ""))
    dup = [k for k, v in ids.items() if v > 1]
    print(f"{n} cases in {len(files)} files; duplicate ids across files: {dup or 'none'}")
    for cid, msg, a in flags:
        print(f"  {cid:<44} {msg} {a}")
    print(f"{len(flags)} flag(s)")


if __name__ == "__main__":
    main()
