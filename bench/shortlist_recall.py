"""Would a keyword shortlist keep the expected areas? Local only: no model, synthetic cases only.

For each labelled case the local keyword engine ranks all 94 areas from the CV text. We report the share of expected (supported) areas
that fall inside the top K, per case file. Also reports the share of cases where EVERY expected area is inside the top K, which is what
matters for a shortlist: one missed area means the model can never see it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from careerx import pipeline as PL  # noqa: E402

KS = (10, 20, 30, 40)
FILES = ["career_cases.yaml", "career_cases_holdout_v2.yaml", "career_cases_holdout_v3.yaml", "career_cases_holdout_v4.yaml",
         "career_cases_swap_v1.yaml", "career_cases_synth_v1.yaml", "career_cases_synth_v2.yaml"]


def main() -> dict:
    out, misses = {}, []
    for f in FILES:
        cases = yaml.safe_load((ROOT / "bench/cases" / f).read_text(encoding="utf-8"))
        n_areas, hit, full, n_cases, ranks = 0, {k: 0 for k in KS}, {k: 0 for k in KS}, 0, []
        for c in cases:
            exp = list(c.get("supported") or [])
            if not exp:
                continue
            prof = PL.build_profile("Participant", c["cv_text"], today=PL.REFERENCE_DATE)
            order = list(PL.run(prof)["scores"].sort_values("score", ascending=False)["area_id"])
            n_cases += 1
            pos = {a: (order.index(a) + 1 if a in order else 999) for a in exp}
            ranks += list(pos.values())
            n_areas += len(exp)
            for k in KS:
                hit[k] += sum(p <= k for p in pos.values())
                full[k] += all(p <= k for p in pos.values())
            late = {a: p for a, p in pos.items() if p > 30}
            if late:
                misses.append(dict(file=f, case=c["id"], beyond_top30=late))
        out[f] = dict(cases=n_cases, expected_areas=n_areas,
                      area_recall={k: round(hit[k] / n_areas, 3) if n_areas else None for k in KS},
                      cases_fully_covered={k: f"{full[k]}/{n_cases}" for k in KS}, median_rank=sorted(ranks)[len(ranks) // 2] if ranks else None)
    tot_a = sum(v["expected_areas"] for v in out.values())
    tot_c = sum(v["cases"] for v in out.values())
    allrec = {k: round(sum(v["area_recall"][k] * v["expected_areas"] for v in out.values()) / tot_a, 3) for k in KS}
    allfull = {k: f"{sum(int(v['cases_fully_covered'][k].split('/')[0]) for v in out.values())}/{tot_c}" for k in KS}
    return dict(per_file=out, overall=dict(cases=tot_c, expected_areas=tot_a, area_recall=allrec, cases_fully_covered=allfull),
                misses_beyond_top30=misses)


if __name__ == "__main__":
    r = main()
    p = ROOT / "bench/runs/shortlist_recall_2026-11-01.json"
    p.write_text(json.dumps(r, indent=1), encoding="utf-8")
    print(json.dumps(r["overall"], indent=1))
    for k, v in r["per_file"].items():
        print(k.ljust(34), v["cases"], v["expected_areas"], v["area_recall"], v["cases_fully_covered"])
    print(len(r["misses_beyond_top30"]), "cases with an expected area beyond rank 30")
    for m in r["misses_beyond_top30"][:12]:
        print("  ", m["file"], m["case"], m["beyond_top30"])
