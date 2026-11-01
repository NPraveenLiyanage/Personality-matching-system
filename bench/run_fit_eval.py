"""Fit benchmark runner: the local baseline (offline) or a real model (live) against bench/cases/fit_cases_v1.yaml.

Synthetic cases only; the runner refuses anything else. Live runs save a checkpoint after every case so a daily rate limit never loses
finished work; re-run with the same --label to resume. Nothing here is accuracy evidence: labels are author-written (see the case file).

  python bench/run_fit_eval.py --mode baseline --split all
  python bench/run_fit_eval.py --mode live --split dev --label dev_nemotron --max-tokens 20000 --data-collection allow
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from bench.personamap_synth import make_report  # noqa: E402
from careerx import personamap as PM, workstyle as W  # noqa: E402
from careerx.evidence import assess, client as ev_client, fit  # noqa: E402

CASES = ROOT / "bench" / "cases" / "fit_cases_v1.yaml"
DEFS = ROOT / "data" / "processed" / "area_definitions_v3.yaml"
PRICES = ROOT / "bench" / "prices.yaml"
RUNS = ROOT / "bench" / "runs"
LEVEL = {"stretch": 0, "mixed": 1, "strong": 2}


def load_cases(split: str) -> list[dict]:
    cases = yaml.safe_load(CASES.read_text(encoding="utf-8"))
    return [c for c in cases if split == "all" or c["split"] == split]


def holdout_hash() -> str:
    h = [c for c in yaml.safe_load(CASES.read_text(encoding="utf-8")) if c["split"] == "holdout"]
    return hashlib.sha256(json.dumps(h, sort_keys=True, default=str).encode()).hexdigest()


def to_expected(band: str) -> str:
    return "insufficient" if band in ("neutral", "insufficient_info") else band


def parse_case(c: dict) -> PM.PersonaMap:
    return PM.parse_text(make_report(c["name"], c["prefs"], c["ratings"]))


def score(rows: list[dict]) -> dict:
    """rows: dict(case, area, expected, got). Exact agreement, direction errors, insufficient rate."""
    n = len(rows)
    exact = sum(r["got"] == r["expected"] for r in rows)
    graded = [r for r in rows if r["expected"] in LEVEL and r["got"] in LEVEL]
    flips = sum(abs(LEVEL[r["expected"]] - LEVEL[r["got"]]) == 2 for r in graded)      # strong<->stretch
    abstained_on_clear = sum(r["got"] == "insufficient" and r["expected"] in LEVEL for r in rows)
    claimed_on_even = sum(r["expected"] == "insufficient" and r["got"] in LEVEL for r in rows)
    return dict(n=n, exact=exact, exact_rate=round(exact / n, 3) if n else None, strong_stretch_flips=flips,
                abstained_where_expected_clear=abstained_on_clear, claimed_fit_where_report_is_even=claimed_on_even)


def run_baseline(cases: list[dict]) -> dict:
    prof = W.load_profiles()
    rows = []
    for c in cases:
        pm = parse_case(c)
        for a, exp in c["expected"].items():
            rows.append(dict(case=c["id"], area=a, expected=exp, got=to_expected(W.baseline_fit(pm, prof[a]["demands"])["band"])))
    return dict(mode="baseline", score=score(rows), rows=rows)


def cost_usd(usage: dict, price: dict) -> float:
    return (usage.get("prompt_tokens", 0) * price["input"] + usage.get("completion_tokens", 0) * price["output"]) / 1e6


def run_live(cases: list[dict], cfg: dict, label: str, chat=None, resume: bool = True) -> dict:
    defs = assess.load_definitions(DEFS)
    prof = W.load_profiles()
    ckpt = RUNS / f"_checkpoint_fit_{label}.json"
    done = json.loads(ckpt.read_text(encoding="utf-8")) if (resume and ckpt.exists()) else {}
    for c in cases:
        if c["id"] in done and done[c["id"]].get("status") != "failed":
            continue
        pm = parse_case(c)
        cands = [dict(area_id=a) for a in c["expected"]]
        try:
            r = fit.run_fit(pm, cands, defs, chat=chat or ev_client.chat, cfg=cfg)
        except Exception as e:                                   # network or unexpected provider errors are recorded, not hidden
            r = dict(status="failed", errors=[f"{type(e).__name__}: {str(e)[:160]}"], fits={}, run_meta={})
        done[c["id"]] = r
        ckpt.write_text(json.dumps(done, indent=1, default=str), encoding="utf-8")
        print(c["id"], r["status"], (r.get("errors") or [""])[0][:100], flush=True)
    return summarise(cases, done, label, prof)


def summarise(cases: list[dict], done: dict, label: str, prof: dict) -> dict:
    rows, base_rows, usage, lat, dropped, proposed_ok, failed = [], [], [], [], 0, 0, []
    agree_model_base = tot_pairs = low_conf = 0
    prices = yaml.safe_load(PRICES.read_text(encoding="utf-8")) if PRICES.exists() else {}
    for c in cases:
        r = done.get(c["id"])
        if not r or r["status"] == "failed":
            failed.append(dict(case=c["id"], errors=(r or {}).get("errors", ["not run"])))
            continue
        usage.append(r["run_meta"].get("usage") or {})
        lat.append(r["run_meta"].get("latency_s") or 0)
        for a, exp in c["expected"].items():
            f = r["fits"][a]
            rows.append(dict(case=c["id"], area=a, expected=exp, got=to_expected(f["fit_band"])))
            base_rows.append(dict(case=c["id"], area=a, expected=exp, got=to_expected(f["baseline"]["band"])))
            tot_pairs += 1
            agree_model_base += to_expected(f["fit_band"]) == to_expected(f["baseline"]["band"])
            low_conf += bool(f.get("low_confidence"))
            ok = len(f["reasons"]) + len(f["watch_outs"])
            bad = sum(("dropped" in ch) for ch in f["changes"])
            proposed_ok += ok
            dropped += bad
    tokens_in = sum(u.get("prompt_tokens", 0) for u in usage)
    tokens_out = sum(u.get("completion_tokens", 0) for u in usage)
    n = max(len(usage), 1)
    est = {m: round((tokens_in / n * p["input"] + tokens_out / n * p["output"]) / 1e6 * 1000, 2) for m, p in prices.get("models", {}).items()}
    return dict(mode="live", label=label, date=str(date.today()), cases_run=len(usage), cases_failed=failed,
                model_score=score(rows), baseline_score_same_rows=score(base_rows), rows=rows,
                model_vs_baseline_agreement=round(agree_model_base / tot_pairs, 3) if tot_pairs else None,
                low_confidence_rows=low_conf, quotes_kept=proposed_ok, quotes_or_points_dropped=dropped,
                quote_survival=round(proposed_ok / (proposed_ok + dropped), 3) if proposed_ok + dropped else None,
                mean_tokens_in=round(tokens_in / n), mean_tokens_out=round(tokens_out / n), mean_latency_s=round(sum(lat) / n, 1),
                fit_call_cost_per_1000_users_usd_at_list_price=est, prices_source=prices.get("source"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["baseline", "live"], default="baseline")
    ap.add_argument("--split", choices=["dev", "holdout", "all"], default="dev")
    ap.add_argument("--label", default="run")
    ap.add_argument("--model", default="")
    ap.add_argument("--provider", default="")
    ap.add_argument("--max-tokens", type=int, default=20000)
    ap.add_argument("--data-collection", default="deny", choices=["deny", "allow"])
    ap.add_argument("--no-resume", action="store_true")
    a = ap.parse_args()
    cases = load_cases(a.split)
    assert cases and all(c.get("name") and c.get("prefs") for c in cases)
    if a.mode == "baseline":
        out = run_baseline(cases)
        print(json.dumps(out["score"], indent=1))
    else:
        cfg = dict(ev_client.settings(), max_tokens=a.max_tokens, data_collection=a.data_collection, temperature="", require_zdr=False,
                   max_price="", api_key_2="")
        if a.model:
            cfg["model"] = a.model
        if a.provider:
            cfg["provider"] = a.provider
        out = run_live(cases, cfg, a.label, resume=not a.no_resume)
        out["model"], out["provider"] = cfg["model"], cfg["provider"]
        print(json.dumps({k: v for k, v in out.items() if k != "rows"}, indent=1))
    out["split"], out["holdout_hash"] = a.split, holdout_hash()
    RUNS.mkdir(exist_ok=True)
    (RUNS / f"fit_{a.mode}_{a.split}_{a.label}_{date.today()}.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
