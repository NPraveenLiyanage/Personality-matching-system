"""Draft data/processed/area_definitions_v1.yaml from the runtime catalogue (ISCO titles, examples, text) with a pinned model.

  python scripts/draft_area_definitions.py --run-live --model anthropic/claude-sonnet-5.5 --provider anthropic

Input is catalogue text only. Benchmark cases are never read or sent. Every entry is saved as status: draft_unreviewed and needs a
human reviewer before the Phase 3 gate can pass.
"""
import argparse
import hashlib
import json
import os
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from careerx import pipeline  # noqa: E402
from careerx.evidence import client  # noqa: E402

OUT = ROOT / "data" / "processed" / "area_definitions_v1.yaml"
_S = {"type": "array", "items": {"type": "string"}}
SCHEMA = {
    "type": "object",
    "properties": {"areas": {"type": "array", "items": {
        "type": "object",
        "properties": {"area_id": {"type": "string"}, "definition": {"type": "string"},
                       "typical_activities": _S, "evidence_examples": _S, "common_contextual_confusions": _S,
                       "qualification_gaps": _S, "formal_qualification_required": {"type": "boolean"}},
        "required": ["area_id", "definition", "typical_activities", "evidence_examples", "common_contextual_confusions",
                     "qualification_gaps", "formal_qualification_required"],
        "additionalProperties": False}}},
    "required": ["areas"], "additionalProperties": False}

SYSTEM = """You write short reference definitions of career areas for a career-exploration tool. Use only the catalogue text supplied for each area.
For each area return:
- definition: at most 40 words, what people in this area do.
- typical_activities: 4 to 6 short phrases of the core day-to-day work.
- evidence_examples: 3 or 4 short examples of CV statements that show a person personally doing this work (what they did, not just where).
- common_contextual_confusions: 2 or 3 situations that can look related on a CV but do not show this work (for example, work done for or near this field by a person in a different occupation).
- qualification_gaps: formal qualifications, registration or licences normally needed to practise, as short phrases; empty list if none.
- formal_qualification_required: true only where practising normally requires a recognised qualification or registration.
Use plain, neutral language. Do not judge competence or suitability of any individual. Return exactly one entry per supplied area_id."""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-live", action="store_true")
    ap.add_argument("--model", required=True)
    ap.add_argument("--provider", required=True)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--data-collection", default="deny", choices=["deny", "allow"],
                    help="allow only for free endpoints; this script sends public catalogue text only")
    a = ap.parse_args()
    if not a.run_live:
        sys.exit("Refusing to call an external API without --run-live.")
    cat = pipeline.get_catalogue()
    fp = hashlib.sha256(json.dumps([(r.area_id, r.name, r.cluster, r.kind) for r in cat.itertuples()]).encode()).hexdigest()[:16]
    cfg = client.settings()
    cfg.update(model=a.model, provider=a.provider, max_tokens=12000, require_zdr=False, temperature="",
               data_collection=a.data_collection, max_price="")
    done: dict = {}
    rows = list(cat.itertuples())
    for i in range(0, len(rows), a.batch):
        chunk = rows[i:i + a.batch]
        user = json.dumps([dict(area_id=r.area_id, name=r.name, cluster=r.cluster, isco_titles=r.isco_titles,
                                example_occupations=list(r.examples)[:12], description=str(r.text)[:700]) for r in chunk],
                          ensure_ascii=False)
        res = client.chat(SYSTEM, user, SCHEMA, cfg)
        if res.finish_reason == "length":
            sys.exit(f"batch {i} truncated")
        got = {x["area_id"]: x for x in json.loads(res.content)["areas"]}
        want = {r.area_id for r in chunk}
        if set(got) != want:
            sys.exit(f"batch {i}: ids differ: missing {sorted(want - set(got))} extra {sorted(set(got) - want)}")
        for r in chunk:
            x = got[r.area_id]
            done[r.area_id] = dict(name=r.name, cluster=r.cluster, status="draft_unreviewed", **{k: v for k, v in x.items() if k != "area_id"})
        print(f"drafted {len(done)}/{len(rows)}  ({res.latency_s}s, {res.usage.get('completion_tokens')} out tokens)", flush=True)
    doc = dict(definitions_version="v1", catalogue_fingerprint=fp, status="draft_unreviewed", drafted_on=str(date.today()),
               drafted_by=dict(model=a.model, provider=a.provider, data_collection=a.data_collection),
               note="LLM-drafted from catalogue ISCO text only; benchmark cases were not used. Needs human review before any gate.",
               areas=done)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8")
    print("wrote", OUT.relative_to(ROOT), "areas:", len(done))


if __name__ == "__main__":
    main()
