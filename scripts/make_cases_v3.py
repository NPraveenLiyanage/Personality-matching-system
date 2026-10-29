"""Build bench/cases/career_cases_v3.yaml from the two original case files plus the reviewer's section-7b changes.

The original files are never edited. v3 keeps every CV text and split, and changes only the expectations, each with a recorded reason.
New field `exploration_only`: areas that are fine to show ONLY as clearly labelled exploration; showing one as a supported
recommendation counts as an overclaim (a separate metric from domain-confusion traps).

IMPORTANT (honesty): the review was done after the pipeline's outputs on these cases were known to the team, and some v3 changes happen
to move results in the pipeline's favour. v3 numbers are therefore reported next to the old ones and are not independent evidence.
"""
import hashlib
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from bench import metrics  # noqa: E402

SOURCES = ["career_cases.yaml", "career_cases_holdout_v2.yaml"]
R = "Reviewer 7b (provisional desk review, 2026-10-29)"
CAT = "catalogue ISCO assignment"

# case id -> final expectation fields (unspecified fields keep the original) + reason
CHANGES = {
    "c01_hospital_app_developer": dict(acceptable=[], exploration_only=["A044", "A086", "A087", "A088"],
        why=f"{R}: only A043 is supported by the stated project; other tech areas need their own task evidence, exploratory only."),
    "c02_practising_nurse": dict(acceptable=["A025"], exploration_only=["A021", "A027", "A093"],
        why=f"{R}: do not infer paramedic, personal-care assistant or trainer experience from nursing alone."),
    "c03_bank_app_developer": dict(acceptable=[], exploration_only=["A044", "A088", "A090"],
        why=f"{R}: A090 needs explicit security tasks; other options exploratory unless evidenced."),
    "c04_accountant": dict(acceptable=["A092"], exploration_only=["A041", "A040", "A052", "A008", "A003"],
        why=f"{R}: clerk, bank-clerk, compliance or management roles are not demonstrated by being an accountant."),
    "c05_legal_chatbot_developer": dict(supported=["A043"], acceptable=[], exploration_only=["A087", "A086", "A044", "A088"],
        why=f"{R}: A087 is direct only for actual AI/model engineering. The full CV shows a chatbot built on an LLM API, not model engineering, so A087 moves to exploration."),
    "c06_lawyer": dict(acceptable=[], exploration_only=["A052", "A053", "A008"],
        why=f"{R}: compliance, social/community support and management need separate tasks."),
    "c07_education_platform_developer": dict(acceptable=[], exploration_only=["A044", "A088"],
        why=f"{R}: database/design areas need evidence of actual tasks."),
    "c08_secondary_teacher": dict(acceptable=["A032"], exploration_only=["A029", "A013", "A093"],
        why=f"{R}: maths teaching is not statistical/actuarial research; vocational or L&D work need additional tasks."),
    "c10_consultant_physician": dict(acceptable=["A093"], exploration_only=["A028", "A032"],
        why=f"{R}: no university teaching or specialist advisory duties are stated (supervision of interns keeps A093 acceptable)."),
    "c12_team_project_limited_contribution": dict(acceptable=[], exploration_only=["A044", "A088"],
        why=f"{R}: optional areas need role-specific contributions; A043 stays supported because the CV states 'I wrote the REST API endpoints'."),
    "c13_explicit_negation": dict(acceptable=["A037", "A042", "A055"], exploration_only=["A006"],
        why=f"{R}: do not infer management."),
    "c14_skills_list_only": dict(supported=[], acceptable=[], exploration_only=["A043", "A086", "A087", "A090", "A044", "A045"],
        why=f"{R}: skills names alone support no occupation; these may be shown only as exploration."),
    "c15_referee_titles": dict(acceptable=["A062"], exploration_only=["A010", "A004", "A036"],
        why=f"{R}: management and real-estate areas require duties."),
    "c16_plc_ambiguity": dict(acceptable=["A067", "A089"], exploration_only=["A016", "A015"],
        why=f"{R}: separate hands-on A072/A075 from engineering design A016; do not infer an engineer from a technician title."),
    "c17_incidental_ayurvedic_terms": dict(acceptable=["A049", "A062", "A036"], exploration_only=["A051"],
        why=f"{R}: design/culinary needs personal tasks. A049 stays acceptable because the CV states writing posts and product descriptions."),
    "c20_old_experience_only": dict(supported=["A058", "A009", "A041"], acceptable=["A040", "A060"],
        why=f"{R}: older accounts-clerk work may be direct historical evidence (also calibration pair 9). Recency must lower its rank."),
    "c21_software_engineer_genuine_positive": dict(acceptable=["A044", "A045"], exploration_only=["A087", "A090", "A007"],
        why=f"{R}: do not grant AI, cybersecurity or ICT management from general web development alone."),
    "c22_electrician_genuine_positive": dict(acceptable=["A079"], exploration_only=["A016", "A070"],
        why=f"{R}: engineering and broader construction need matching duties."),
    "v2_01_dairy_farm_manager": dict(acceptable=["A003"], exploration_only=["A065", "A066"],
        why=f"{R}: forestry, fishery and subsistence farming need direct tasks; animal care is not veterinary practice."),
    "v2_02_hospital_kitchen_chef": dict(acceptable=["A009", "A060", "A058", "A051"], exploration_only=["A076"],
        why=f"{R}: food-processing trades need production/baking evidence. A051 added as acceptable: {CAT} places ISCO 3434 Chefs in A051."),
    "v2_03_construction_site_supervisor": dict(supported=["A067"], acceptable=["A006", "A085", "A060"], exploration_only=["A070"],
        why=f"{R}: A070 is hands-on construction trades, not supervision (answer 'no'). {CAT}: ISCO 3123 Construction supervisors are in A067, so A067 becomes the supported area."),
    "v2_04_council_administrative_officer": dict(acceptable=["A042"], exploration_only=["A052", "A001"],
        why=f"{R}: public-sector employment alone does not show government leadership or regulation."),
    "v2_05_packaging_designer_pharma": dict(supported=["A088", "A017"], acceptable=["A051", "A050", "A074", "A035"],
        why=f"{R}: A051 is design support, not professional design; A088 if the catalogue includes graphic design. {CAT}: ISCO 2166 Graphic and multimedia designers are in both A088 and A017."),
    "v2_07_school_leaver_retail": dict(acceptable=["A069", "A055"], exploration_only=["A010"],
        why=f"{R}: retail management needs supervisory tasks."),
    "v2_08_accounting_coursework_only": dict(supported=[], acceptable=[], exploration_only=["A033", "A041", "A092", "A013", "A040"],
        why=f"{R}: coursework supports an exploratory pathway, not professional accounting practice (answers open question Q8: an in-progress degree is exploration)."),
    "v2_09_backend_developer_hospital": dict(acceptable=[], exploration_only=["A044", "A090", "A088"],
        why=f"{R}: security and design need actual tasks."),
    "v2_10_backend_developer_bank": dict(acceptable=[], exploration_only=["A044", "A090", "A088"],
        why=f"{R}: security and design need actual tasks."),
    "v2_11_backend_developer_school": dict(acceptable=[], exploration_only=["A044", "A090", "A088"],
        why=f"{R}: security and design need actual tasks."),
    "v2_12_garbled_text": dict(supported=[], acceptable=[],
        why=f"{R}: without intelligible duties no area should be an acceptable recommendation."),
}
UNCHANGED_NOTE = {
    "c11_nurse_who_built_scheduler": "Reviewer row was based on a summary that showed only the name (summary-extraction artefact); full CV expectations kept.",
    "c09_disease_classifier_student": "Reviewer: depends on model-building in the full CV, which states it; kept.",
    "c18_prompt_injection": "Reviewer agreed; kept.", "c19_career_changer_nurse_to_developer": "Reviewer: both direct, rank by recency; kept.",
    "v2_06_sparse_one_line": "Reviewer agreed; kept.",
}


def main():
    out = []
    for fn in SOURCES:
        for c in metrics.load_cases(ROOT / "bench" / "cases" / fn):
            c = dict(c)
            ch = CHANGES.get(c["id"], {})
            c["source_file"] = fn
            c["supported_v1"], c["acceptable_v1"] = list(c["supported"]), list(c.get("acceptable", []))
            for k in ("supported", "acceptable"):
                if k in ch:
                    c[k] = ch[k]
            c["acceptable"] = c.get("acceptable", [])
            c["exploration_only"] = ch.get("exploration_only", [])
            c["v3_change"] = ch.get("why", UNCHANGED_NOTE.get(c["id"], "No reviewer change."))
            c["cases_version"] = 3
            assert not set(c["supported"]) & set(c["traps"]) and not set(c["exploration_only"]) & (set(c["supported"]) | set(c["traps"])), c["id"]
            assert not set(c["acceptable"]) & set(c["exploration_only"]), c["id"]
            out.append(c)
    unknown = set(CHANGES) - {c["id"] for c in out}
    assert not unknown, unknown
    header = ("# Case expectations v3 = original expectations + reviewer's section-7b changes (docs/PROJECT_REVIEW.md), generated by\n"
              "# scripts/make_cases_v3.py from the two original files, which are unchanged. CV texts and splits are identical.\n"
              "# New field exploration_only: fine to show ONLY as labelled exploration; showing it as supported is an overclaim.\n"
              "# The review happened after pipeline outputs on these cases were known, so v3 scores are not independent evidence;\n"
              "# always read them next to the original-expectation scores (docs/CASES_V3_COMPARISON.md).\n"
              f"# sources: " + ", ".join(f"{f} sha256:{hashlib.sha256((ROOT / 'bench' / 'cases' / f).read_bytes()).hexdigest()[:12]}" for f in SOURCES) + "\n")
    dest = ROOT / "bench" / "cases" / "career_cases_v3.yaml"
    dest.write_text(header + yaml.safe_dump(out, sort_keys=False, allow_unicode=True, width=120), encoding="utf-8")
    print("wrote", dest.relative_to(ROOT), len(out), "cases;", sum(1 for c in out if c["v3_change"] != "No reviewer change."), "with a recorded change")


if __name__ == "__main__":
    main()
