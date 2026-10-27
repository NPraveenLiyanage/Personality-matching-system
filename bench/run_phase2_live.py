"""Opt-in live run of the Phase 2 extractor on the synthetic cases. Sends synthetic text only.

  python bench/run_phase2_live.py --run-live            (reads pinning from .env / environment)

Needs OPENROUTER_API_KEY, CAREERX_EVIDENCE_MODEL, CAREERX_EVIDENCE_PROVIDER. Writes bench/runs/ (full results) and an audit sheet.
It never prints the key or the prompt payload.
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from careerx.evidence import audit, client, extract, ingest  # noqa: E402
from careerx.evidence.validate import norm  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-live", action="store_true", help="required: confirms external calls with synthetic data")
    ap.add_argument("--cases", default=str(ROOT / "bench" / "cases" / "phase2_extraction_cases.yaml"))
    ap.add_argument("--only", default="", help="comma-separated case ids")
    a = ap.parse_args()
    if not a.run_live:
        sys.exit("Refusing to call an external API without --run-live.")
    cfg = client.settings()
    cases = yaml.safe_load(Path(a.cases).read_text(encoding="utf-8"))
    if a.only:
        cases = [c for c in cases if c["id"] in a.only.split(",")]
    out, rows, tot = [], [], dict(prompt=0, completion=0, latency=0.0)
    for c in cases:
        assert c["synthetic"] is True, "refusing to send a non-synthetic case"
        ing = ingest.ingest_text(c["cv_text"], [c["name"]])
        res = extract.run_extraction(ing, cfg=cfg)
        got = [norm(r.quote) for r in res.records]
        exp = [norm(e["quote"]) for e in c["expected_records"]]
        hit = [e for e in exp if any(e in g or g in e for g in got)]
        extra = [g for g in got if not any(e in g or g in e for e in exp)]
        u = res.meta.get("usage") or {}
        tot["prompt"] += u.get("prompt_tokens", 0)
        tot["completion"] += u.get("completion_tokens", 0)
        tot["latency"] += res.meta.get("latency_s", 0) or 0
        out.append(dict(case=c["id"], status=res.status, expected=len(exp), matched=len(hit), extra=extra,
                        warnings=[w["code"] for w in res.warnings], errors=res.errors, rejected=res.rejected,
                        notes=res.notes, meta=res.meta,
                        records=[r.__dict__ for r in res.records]))
        rows += audit.audit_rows(c["id"], res)
        print(f"{c['id']:<42} {res.status:<9} matched {len(hit)}/{len(exp)} extra {len(extra)} rejected {len(res.rejected)} "
              f"repaired {sum(r.status == 'repaired' for r in res.records)} {('ERR ' + res.errors[0][:90]) if res.errors else ''}")
    tag = (cfg["model"] or "model").replace("/", "_")
    rd = ROOT / "bench" / "runs"
    rd.mkdir(parents=True, exist_ok=True)
    (rd / f"phase2_{tag}_{date.today()}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    audit.write_audit_csv(ROOT / "bench" / "audit" / f"extraction_audit_{tag}.csv", rows)
    print("tokens", tot["prompt"], "in /", tot["completion"], "out; total latency", round(tot["latency"], 1), "s")


if __name__ == "__main__":
    main()
