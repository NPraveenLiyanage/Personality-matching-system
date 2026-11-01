"""One complete pass of the two-step 'final' engine on INVENTED data with a real free model (the same path the app's live mode uses).
Not a benchmark: it proves the pieces work together. Synthetic only."""
import json
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
from bench.personamap_synth import make_report  # noqa: E402
from careerx import engines  # noqa: E402
from careerx.evidence import assess, client as ev_client  # noqa: E402

case = next(c for c in yaml.safe_load((ROOT / "bench/cases/career_cases_synth_v2.yaml").read_text(encoding="utf-8")) if c.get("supported"))
fitcase = next(c for c in yaml.safe_load((ROOT / "bench/cases/fit_cases_v1.yaml").read_text(encoding="utf-8")) if c["id"].startswith("f02"))
defs = assess.load_definitions(ROOT / "data/processed/area_definitions_v3.yaml")
cfg = dict(ev_client.settings(), model="nvidia/nemotron-3.5-super-vl:free", provider="nvidia", data_collection="allow", max_tokens=20000,
           temperature="", require_zdr=False, max_price="", api_key_2="")
res = engines.run("final", case["cv_text"], "", defs=defs, personamap_text=make_report(fitcase["name"], fitcase["prefs"], fitcase["ratings"]),
                  regulated=assess.load_regulated(), cfg=cfg, policy="v3", mask_orgs=True)
out = dict(case=case["id"], expected_supported=case["supported"], status=res.status, errors=res.errors, warnings=res.warnings,
           supported=[(s["area_id"], s["name"], s["support_class"]) for s in res.supported],
           exploration=[(s["area_id"], s["name"]) for s in res.exploration],
           fit={a: dict(band=f["fit_band"], baseline=f["baseline"]["band"], quotes=len(f["reasons"]) + len(f["watch_outs"]), changes=f["changes"])
                for a, f in (res.fit or {}).get("fits", {}).items()}, fit_status=(res.fit or {}).get("status"), fit_errors=(res.fit or {}).get("errors"),
           run_meta={k: (v if k != "extraction" else "...") for k, v in res.run_meta.items()})
(ROOT / f"bench/runs/e2e_final_{date.today()}.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
print(json.dumps({k: v for k, v in out.items() if k != "run_meta"}, indent=1, default=str))
