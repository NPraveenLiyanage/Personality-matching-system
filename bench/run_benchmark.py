"""Engine-agnostic benchmark runner.

  python bench/run_benchmark.py --engine rule
  python bench/run_benchmark.py --engine llm_direct --model anthropic/claude-haiku-5.5 --run-live   (synthetic text only, costs tokens)

Writes bench/runs/career_<engine>_<date>.json with per-case top-k, metrics and run metadata. Never prints the key or CV text.
`llm_direct` is the frozen careerx.llm matcher (direct prompt) run with ONE pinned model and NO fallback chain, one run per case.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from bench import metrics  # noqa: E402
from careerx import pipeline  # noqa: E402


def catalogue_fingerprint(cat) -> str:
    rows = [(r.area_id, r.name, r.cluster, r.kind) for r in cat.itertuples()]
    return hashlib.sha256(json.dumps(rows).encode()).hexdigest()[:16]


def rank_rule(case: dict, cat) -> list[dict]:
    p = pipeline.build_profile("Participant", case["cv_text"], today=pipeline.REFERENCE_DATE)
    sc = pipeline.run(p)["scores"].sort_values("score", ascending=False)
    return [dict(area_id=r.area_id, name=r.name, score=round(float(r.score), 1)) for r in sc.itertuples()]


def rank_llm_direct(case: dict, cat) -> list[dict]:
    from careerx.llm import engine, payload
    p = pipeline.build_profile("Participant", case["cv_text"], today=pipeline.REFERENCE_DATE)
    first_line = case["cv_text"].strip().splitlines()[0]
    out = engine.run_match(payload.build_payload(p, extra_names=[first_line]), cat, runs=1)
    sc = out["scores"].sort_values("rank")
    return [dict(area_id=r.area_id, name=r.name, score=float(r.final)) for r in sc.itertuples()]


_EVIDENCE_CTX: dict = {}


def rank_llm_evidence(case: dict, cat):
    """Evidence-first engine. Returns (supported ranking, exploration ids, stage outputs); a failed run raises (recorded, no fallback)."""
    from careerx.evidence import assess, client as ev_client, engine as ev_engine
    ctx = _EVIDENCE_CTX
    if "defs" not in ctx:
        ctx["defs"], ctx["reg"] = assess.load_definitions(ctx.get("definitions")), assess.load_regulated(ctx.get("regulated"))
    first_line = case["cv_text"].strip().splitlines()[0]
    res = ev_engine.run(case["cv_text"], first_line, ctx["defs"], cfg=ctx["cfg"], regulated=ctx["reg"],
                        use_confusions=ctx.get("use_confusions", False), policy=ctx.get("policy", "v2"))
    if res["status"] == "failed":
        raise RuntimeError("; ".join(res["errors"])[:300])
    ranking = [dict(area_id=s["area_id"], name=s["name"], score=float(s["relevance"] or 0), support_class=s["support_class"])
               for s in res["supported"]]
    stages = dict(status=res["status"], warnings=[w["code"] for w in res["warnings"]], validation_log=res["validation_log"],
                  extraction=res["stages"].get("extraction"), assessment=res["stages"].get("assessment"),
                  exploration=res["exploration"], context_only=res.get("context_only"), run_meta=res["run_meta"])
    return ranking, [e["area_id"] for e in res["exploration"]], stages


ENGINES = {"rule": rank_rule, "llm_direct": rank_llm_direct, "llm_evidence": rank_llm_evidence}


def rescore(path: Path, cases_path: Path, k: int) -> None:
    """Re-score a stored run under the current metrics version and case file. The stored rankings are untouched."""
    run = json.loads(path.read_text(encoding="utf-8"))
    cases = [c for c in metrics.load_cases(cases_path) if c["id"] in run["top"]]
    stages = run.get("stages") or {}
    expl = lambda cid: [e["area_id"] for e in (stages.get(cid) or {}).get("exploration", [])]   # noqa: E731
    per_case = {c["id"]: metrics.case_metrics(c, [r["area_id"] for r in run["top"][c["id"]]], k, expl(c["id"])) for c in cases}
    run["aggregate"] = metrics.aggregate(cases, per_case, k)
    run["per_case"] = per_case
    run["meta"].update(rescored_from=path.name, metrics_version=metrics.METRICS_VERSION, cases_file=cases_path.name,
                       cases_sha256=hashlib.sha256(cases_path.read_bytes()).hexdigest()[:16])
    out = path.with_name(path.stem + f"_m{metrics.METRICS_VERSION}_{cases_path.stem}.json")
    out.write_text(json.dumps(run, indent=1, ensure_ascii=False), encoding="utf-8")
    o = run["aggregate"]["overall"]
    print(f"{path.name} -> {out.name}: domain-confusion {o['domain_confusion_cases']}, recall {o['supported_recall']}, "
          f"overclaim cases {o['overclaim_cases']}, mean displayed {o['mean_areas_displayed']}, abstained on no-support {o['abstained_on_no_support_cases']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", required=True, choices=sorted(ENGINES))
    ap.add_argument("--cases", default=str(metrics.CASES_PATH))
    ap.add_argument("--only", default="")
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--model", default="", help="llm_direct / llm_evidence: single pinned model id (no fallbacks)")
    ap.add_argument("--provider", default="", help="llm_evidence: pinned provider slug")
    ap.add_argument("--data-collection", default="deny", choices=["deny", "allow"],
                    help="llm_evidence: 'allow' is needed for free endpoints; only ever used with synthetic cases")
    ap.add_argument("--max-tokens", type=int, default=12000, help="llm_evidence: output limit per call (reasoning models need more)")
    ap.add_argument("--account", type=int, default=1, choices=[1, 2], help="llm_evidence: which configured OpenRouter key is primary (recorded in the run metadata, never the key)")
    ap.add_argument("--split", default="", help="only run cases of this split (tune, holdout, holdout_v2, ...)")
    ap.add_argument("--definitions", default="", help="llm_evidence: area definitions file (default data/processed/area_definitions_v1.yaml)")
    ap.add_argument("--regulated", default="", help="llm_evidence: regulated-areas file (default data/processed/regulated_areas_v1.yaml)")
    ap.add_argument("--policy", default="v2", choices=["v2", "v3"], help="llm_evidence: v2 = frozen pipeline; v3 = assess_v3 prompt + exposure-free, capped ranking (2026-10-30)")
    ap.add_argument("--use-confusions", action="store_true", help="llm_evidence ablation: show common_contextual_confusions to the assessor")
    ap.add_argument("--run-live", action="store_true")
    ap.add_argument("--label", default="", help="suffix for output/checkpoint file names, e.g. pipe2")
    ap.add_argument("--resume", action="store_true", help="keep finished cases from the checkpoint of a killed run; re-run the rest")
    ap.add_argument("--rescore", default="", help="recompute metrics for a stored run file with the current metrics/case file (no API calls)")
    a = ap.parse_args()
    if a.rescore:
        return rescore(Path(a.rescore), Path(a.cases), a.k)
    if a.engine == "llm_direct":
        if not a.run_live or not a.model:
            sys.exit("llm_direct calls an external API: pass --model and --run-live (synthetic cases only).")
        os.environ["OPENROUTER_MODEL"] = a.model
        os.environ["OPENROUTER_FALLBACK_MODELS"] = ""
        os.environ["CAREERX_LLM_RUNS"] = "1"
    if a.engine == "llm_evidence":
        if not a.run_live or not a.model or not a.provider:
            sys.exit("llm_evidence calls an external API: pass --model, --provider and --run-live (synthetic cases only).")
        from careerx.evidence import client as ev_client
        cfg = ev_client.settings()
        cfg.update(model=a.model, provider=a.provider, max_tokens=a.max_tokens, require_zdr=False, temperature="",
                   data_collection=a.data_collection, max_price="")
        if a.account == 2:
            if not cfg.get("api_key_2"):
                sys.exit("--account 2 needs OPENROUTER_API_KEY_2 in .env")
            cfg.update(api_key=cfg["api_key_2"], api_key_2="")
        _EVIDENCE_CTX.update(cfg=cfg, definitions=a.definitions or None, regulated=a.regulated or None, use_confusions=a.use_confusions, policy=a.policy)
    cases = metrics.load_cases(a.cases)
    if a.only:
        cases = [c for c in cases if c["id"] in a.only.split(",")]
    if a.split:
        cases = [c for c in cases if c.get("split") == a.split]
    cat = pipeline.get_catalogue()
    per_case, ranked_out, failed, stage_out = {}, {}, {}, {}
    rd = ROOT / "bench" / "runs"
    rd.mkdir(parents=True, exist_ok=True)
    tag = a.engine + (("_" + a.model.replace("/", "_")) if a.model else "") + (f"_{a.split}" if a.split else "") + (f"_{a.label}" if a.label else "")
    tag = re.sub(r"[^A-Za-z0-9._-]", "_", tag)          # model ids contain ":" (an NTFS stream separator) and "/"
    ckpt = rd / f"_checkpoint_{tag}.json"
    resumed = []
    if a.resume and ckpt.exists():                      # a killed run keeps its finished cases; failed ones are run again
        prev = json.loads(ckpt.read_text(encoding="utf-8"))
        per_case, ranked_out, stage_out = prev["per_case"], prev["top"], prev["stages"]
        resumed = sorted(per_case)
        print(f"resuming: {len(resumed)} finished cases kept from {ckpt.name}")
    for c in cases:
        assert c["synthetic"] is True, "refusing to run a non-synthetic case"
        if c["id"] in per_case:
            continue
        try:
            got = ENGINES[a.engine](c, cat)
        except Exception as e:                      # record the failure; never substitute another engine's result
            failed[c["id"]] = f"{type(e).__name__}: {str(e)[:160]}"
            print(f"{c['id']:<44} FAILED {failed[c['id']][:100]}")
            continue
        ranking, exploration = (got[0], got[1]) if isinstance(got, tuple) else (got, [])
        if isinstance(got, tuple):
            stage_out[c["id"]] = got[2]
        ids = [r["area_id"] for r in ranking]
        m = metrics.case_metrics(c, ids, a.k, exploration)
        per_case[c["id"]] = m
        ranked_out[c["id"]] = ranking[:a.k]
        ckpt.write_text(json.dumps(dict(per_case=per_case, top=ranked_out, stages=stage_out), ensure_ascii=False), encoding="utf-8")
        print(f"{c['id']:<44} shown {m['n_displayed']:>2} found {len(m['supported_found'])}/{len(c['supported'])}  traps {m['trap_hits'] or '-'}"
              f"{('  (as exploration: ' + ','.join(m['trap_as_exploration']) + ')') if m['trap_as_exploration'] else ''}")
    agg = metrics.aggregate([c for c in cases if c["id"] in per_case], per_case, a.k)
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    except OSError:
        commit = ""
    meta = dict(engine=a.engine, date=str(date.today()), git_commit=commit, k=a.k, n_cases=len(cases), n_failed=len(failed),
                cases_sha256=hashlib.sha256(Path(a.cases).read_bytes()).hexdigest()[:16],
                catalogue_fingerprint=catalogue_fingerprint(cat), reference_date=str(pipeline.REFERENCE_DATE),
                model=a.model or None, note="synthetic design expectations, not expert ratings")
    if a.engine == "llm_direct":
        meta.update(prompt="llm/prompt_v1.md", runs_per_case=1, fallbacks="none", provider="unpinned (frozen client)")
    if a.engine == "llm_evidence":
        meta.update(provider=a.provider, split=a.split or "all", prompts="extract_v1+" + ("assess_v3" if a.policy == "v3" else "assess_v2"), policy=a.policy, schema="evidence_v1",
                    definitions_status=(__import__("yaml").safe_load(open(a.definitions or str(ROOT / "data/processed/area_definitions_v1.yaml"), encoding="utf-8")).get("status")),
                    frozen_files={f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest()[:12] for f in (
                        "src/careerx/evidence/extract_v1.md", "src/careerx/evidence/assess_v2.md", "src/careerx/evidence/assess_v3.md", "src/careerx/evidence/validate.py",
                        "src/careerx/evidence/verify.py", "src/careerx/evidence/rank.py", "src/careerx/evidence/engine.py",
                        a.regulated or "data/processed/regulated_areas_v1.yaml", a.definitions or "data/processed/area_definitions_v1.yaml")},
                    label=a.label or None, use_confusions=a.use_confusions, zdr=False, data_collection=a.data_collection, account=a.account, fallbacks="none", runs_per_case=1)
    meta["resumed_cases_from_checkpoint"] = resumed
    out = dict(meta=meta, aggregate=agg, per_case=per_case, top=ranked_out, failed=failed, stages=stage_out)
    path = rd / f"career_{tag}_{date.today()}.json"
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    if not failed and ckpt.exists():
        ckpt.unlink()
    o = agg["overall"]
    print(f"\n{a.engine}: domain-confusion cases {o['domain_confusion_cases']}, supported recall {o['supported_recall']}, "
          f"mean shown {o['mean_areas_displayed']}, top-1 ok {o['top1_in_authored_ok_set']}, abstained on no-support {o['abstained_on_no_support_cases']}, failed {len(failed)}  -> {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
