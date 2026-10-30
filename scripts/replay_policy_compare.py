"""Offline comparison of ranking policy v2 and v3 on saved model outputs (no API calls).

For each saved evidence run, the stored extraction records and raw assessor rows are re-verified and re-ranked under both policies.
The model output is held fixed, so the only thing that differs is the ranker (v3: exposure moved to context_only, lists capped at 3).
It isolates the ranker effect; it says nothing about the v3 prompt.  Usage: python scripts/replay_policy_compare.py
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from careerx.evidence import assess, replay  # noqa: E402

RUNS = [
    "career_llm_evidence_nvidia_nemotron-3.5-super-vl_free_tune_pipe2_2026-10-29.json",
    "career_llm_evidence_nvidia_nemotron-3.5-super-vl_free_holdout_v3_pipe2_2026-10-29.json",
    "career_llm_evidence_nvidia_nemotron-3.5-super-vl_free_pipe2_swap_v1_2026-10-30.json",
    "career_llm_evidence_nvidia_nemotron-3.5-super-vl_free_pipe3_holdout_v4_retry_acct2_2026-10-30.json",
    "career_llm_evidence_nvidia_nemotron-3.5-super-vl_free_pipe3_swap_v1_retry_acct2_2026-10-30.json",
    "career_llm_evidence_nvidia_nemotron-3.5-super-vl_free_pipe3_synth_v2_acct2_2026-10-30.json",
]


def load_cases() -> dict:
    out = {}
    for f in glob.glob(str(ROOT / "bench" / "cases" / "career_cases*.yaml")):
        for c in yaml.safe_load(open(f, encoding="utf-8")) or []:
            if isinstance(c, dict) and "traps" in c:
                out.setdefault(c["id"], c)
    return out


def main() -> None:
    defs = assess.load_definitions(ROOT / "data" / "processed" / "area_definitions_v3.yaml")
    reg = assess.load_regulated(ROOT / "data" / "processed" / "regulated_areas_v2.yaml")
    cases = load_cases()
    tot = dict(cases=0, supported_same=0, exposure_in_expl_v2=0, exposure_trap_v2=0, expl_trap_v3=0, ctx_v3=0, cut_supported=0, cut_expl=0, v2_cases_with_exposure=0)
    for name in RUNS:
        run = json.load(open(ROOT / "bench" / "runs" / name, encoding="utf-8"))
        rows = []
        for cid, st in run["stages"].items():
            c = cases.get(cid)
            r2, r3 = (replay.rebuild(st, defs, reg, p) for p in ("v2", "v3"))
            if not (r2["ok"] and r3["ok"]):
                continue
            tot["cases"] += 1
            s2, s3 = [s["area_id"] for s in r2["supported"]], [s["area_id"] for s in r3["supported"]]
            tot["supported_same"] += s2[:3] == s3
            tot["cut_supported"] += len(s2) - len(s3)
            e2 = r2["exploration"]
            expo = [e["area_id"] for e in e2 if e["support_class"] == "domain_exposure_only"]
            traps = set(c["traps"]) if c else set()
            tot["exposure_in_expl_v2"] += len(expo)
            tot["v2_cases_with_exposure"] += bool(expo)
            tot["exposure_trap_v2"] += len([a for a in expo if a in traps])
            tot["expl_trap_v3"] += len([e for e in r3["exploration"] if e["area_id"] in traps])
            tot["ctx_v3"] += len(r3["context_only"])
            tot["cut_expl"] += len([e for e in e2 if e["support_class"] != "domain_exposure_only"]) - len(r3["exploration"])
            if expo:
                rows.append(f"    {cid[:34]:<34} v2 exploration had exposure {expo}")
        print(name[26:90] + "  (%d cases)" % len(run["stages"]))
        print("\n".join(rows) or "    no exposure rows in v2 exploration")
    print("\nTOTAL", json.dumps(tot))


if __name__ == "__main__":
    main()
