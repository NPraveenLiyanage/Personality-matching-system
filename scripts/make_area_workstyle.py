"""Draft the 94 area work-demand profiles (data/processed/area_workstyle_v1.yaml).

AUTHOR-DRAFTED, UNREVIEWED. Each number is the author's judgement of what the work usually demands, from the area name and its
ISCO group. A human domain reviewer must check every row before the fit step counts as validated. These profiles describe the
work, never a person, and say nothing about who can do it.

Scale 0-4 per dimension (the first four line up with the four PersonaMap preference scales; pace with the "commit" step):
  people     0 mostly alone or with machines ... 4 constant interaction with people          (Extroverted pole)
  abstract   0 concrete, hands-on, literal ... 4 abstract ideas, patterns, models           (Intuition pole)
  values     0 objective, technical analysis ... 4 care, values, people-centred judgement   (Feeling pole)
  structure  0 improvised, flexible ... 4 planned, scheduled, procedural                    (Judging pole)
  pace       0 slow, deliberate decisions ... 4 rapid decisions and hard deadlines          (fast "commit and execute")
"""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
# area_id: (people, abstract, values, structure, pace)
T = {
 "A001": (4,3,3,3,3), "A002": (4,3,2,3,4), "A003": (4,2,2,3,3), "A004": (4,3,2,3,3), "A005": (2,1,1,3,3),
 "A006": (3,1,1,4,4), "A007": (3,3,1,3,3), "A008": (4,3,2,3,3), "A009": (4,1,3,3,4), "A010": (4,1,2,3,4),
 "A011": (4,2,3,2,3), "A012": (1,4,0,3,1), "A013": (1,4,0,3,1), "A014": (1,3,1,4,1), "A015": (2,3,0,3,2),
 "A016": (1,3,0,3,2), "A017": (3,3,2,3,2), "A018": (4,2,4,4,4), "A019": (4,1,4,4,4), "A020": (4,2,4,2,2),
 "A021": (4,0,4,3,4), "A022": (3,1,4,3,4), "A023": (3,1,3,4,3), "A024": (1,1,1,4,2), "A025": (4,1,4,2,2),
 "A026": (4,0,3,2,3), "A027": (4,0,4,3,2), "A028": (3,4,2,3,1), "A029": (4,1,2,3,2), "A030": (4,2,3,4,3),
 "A031": (4,1,4,3,3), "A032": (3,3,3,3,2), "A033": (1,3,0,4,2), "A034": (3,3,2,3,2), "A035": (4,2,2,2,4),
 "A036": (4,1,2,2,4), "A037": (3,1,1,4,3), "A038": (2,1,1,4,2), "A039": (0,0,0,4,2), "A040": (3,0,0,4,3),
 "A041": (1,1,0,4,2), "A042": (1,0,0,4,2), "A043": (1,4,0,3,2), "A044": (1,3,0,4,3), "A045": (3,2,1,3,3),
 "A046": (3,4,2,4,3), "A047": (2,3,2,4,1), "A048": (3,4,4,2,1), "A049": (2,4,2,2,3), "A050": (2,4,3,1,2),
 "A051": (2,2,2,2,3), "A052": (2,2,1,4,2), "A053": (4,2,4,3,3), "A054": (3,0,2,4,4), "A055": (4,0,2,4,4),
 "A056": (4,1,3,2,3), "A057": (2,0,1,3,4), "A058": (4,0,2,3,4), "A059": (4,0,3,2,2), "A060": (3,0,1,4,3),
 "A061": (4,0,3,2,2), "A062": (4,0,2,2,3), "A063": (1,0,0,3,2), "A064": (1,0,0,3,2), "A065": (0,0,0,2,2),
 "A066": (0,0,0,2,2), "A067": (3,1,1,4,4), "A068": (2,1,0,4,4), "A069": (1,0,0,4,3), "A070": (1,0,0,3,3),
 "A071": (0,0,0,3,2), "A072": (1,1,0,3,3), "A073": (1,2,2,1,1), "A074": (1,0,0,4,3), "A075": (1,1,0,3,3),
 "A076": (1,0,0,4,3), "A077": (0,1,1,2,1), "A078": (1,1,1,3,2), "A079": (1,1,1,2,2), "A080": (1,0,0,4,3),
 "A081": (0,0,0,4,3), "A082": (1,0,0,4,3), "A083": (0,0,0,4,3), "A084": (1,0,0,3,3), "A085": (1,0,0,2,2),
 "A086": (1,4,0,3,2), "A087": (1,4,0,3,2), "A088": (3,4,3,2,2), "A089": (1,3,0,3,2), "A090": (1,3,0,4,4),
 "A091": (2,4,3,3,1), "A092": (2,4,1,3,2), "A093": (4,3,3,3,2), "A094": (3,3,3,1,2),
}
DIMS = ("people", "abstract", "values", "structure", "pace")


def build() -> dict:
    defs = yaml.safe_load((ROOT / "data/processed/area_definitions_v3.yaml").read_text(encoding="utf-8"))["areas"]
    assert set(T) == set(defs), sorted(set(defs) ^ set(T))
    return dict(
        version="area_workstyle_v1", status="draft_unreviewed", drafted_by="author (AI-assisted), 2026-10-31",
        note=("What each area's work usually demands, 0-4 per dimension. Author judgement from the area name and ISCO group; NOT "
              "reviewed or validated. Describes the work, never a person. Needs a human domain reviewer before use in evaluation."),
        dimensions=dict(people="0 alone or with machines ... 4 constant interaction with people (Extroverted pole)",
                        abstract="0 concrete hands-on ... 4 abstract ideas, patterns, models (Intuition pole)",
                        values="0 objective technical analysis ... 4 care, values, people-centred judgement (Feeling pole)",
                        structure="0 improvised, flexible ... 4 planned, scheduled, procedural (Judging pole)",
                        pace="0 slow deliberate decisions ... 4 rapid decisions and hard deadlines"),
        areas={a: dict(name=defs[a]["name"], demands=dict(zip(DIMS, T[a]))) for a in sorted(T)})


if __name__ == "__main__":
    out = ROOT / "data/processed/area_workstyle_v1.yaml"
    out.write_text(yaml.safe_dump(build(), sort_keys=False, allow_unicode=True, width=120), encoding="utf-8", newline="\n")
    print("wrote", out, len(T), "areas")
