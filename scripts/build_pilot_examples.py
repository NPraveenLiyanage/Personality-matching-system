"""Build data/demo/pilot_examples.json for the pilot page from the stored benchmark runs (offline, no model calls).

Contains synthetic example CVs and the recorded outputs of the evidence pipeline, the rule engine and the direct-LLM baseline
for the same text, so the pilot can show them instantly. Nothing here comes from real participants or the PersonaMap workbook.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from bench import metrics  # noqa: E402
from careerx import pipeline  # noqa: E402
from careerx.evidence import assess, replay  # noqa: E402

RUNS = ROOT / "bench" / "runs"
EVIDENCE_RUNS = ["career_llm_evidence_nvidia_nemotron-3.5-super-vl_free_tune_2026-10-27.json",
                 "career_llm_evidence_nvidia_nemotron-3.5-super-vl_free_holdout_2026-10-29.json",
                 "career_llm_evidence_nvidia_nemotron-3.5-super-vl_free_2026-10-28.json",       # holds c20
                 "career_llm_evidence_nvidia_nemotron-3.5-super-vl_free_holdout_v2_2026-10-29.json"]
V3_RUN = "career_llm_evidence_nvidia_nemotron-3.5-super-vl_free_holdout_v3_pipe2_2026-10-29.json"   # pipeline v2 (definitions/regulated v2)
TITLES = {  # short human titles for the selector
    "c01_hospital_app_developer": "Student who built a hospital app", "c02_practising_nurse": "Practising nurse",
    "c03_bank_app_developer": "Developer on a banking platform", "c04_accountant": "Accountant",
    "c05_legal_chatbot_developer": "Student who built a legal chatbot", "c06_lawyer": "Lawyer",
    "c07_education_platform_developer": "Developer on a school learning platform", "c08_secondary_teacher": "Secondary school teacher",
    "c09_disease_classifier_student": "Student who built a skin-disease classifier", "c10_consultant_physician": "Consultant physician",
    "c11_nurse_who_built_scheduler": "Nurse who built a scheduling tool", "c12_team_project_limited_contribution": "Team projects, limited personal role",
    "c13_explicit_negation": "Logistics coordinator (explicitly no clinical/accounting experience)", "c14_skills_list_only": "School leaver, skills list only",
    "c15_referee_titles": "Sales executive (referees are hospital/finance staff)", "c16_plc_ambiguity": "Maintenance technician at a 'PLC' company",
    "c17_incidental_ayurvedic_terms": "Marketing assistant at an Ayurvedic brand", "c18_prompt_injection": "CV containing an injected instruction",
    "c19_career_changer_nurse_to_developer": "Former nurse, now developer", "c20_old_experience_only": "Restaurant supervisor, old accounts-clerk job",
    "c21_software_engineer_genuine_positive": "Software engineer", "c22_electrician_genuine_positive": "Electrician",
    "v2_01_dairy_farm_manager": "Dairy farm manager", "v2_02_hospital_kitchen_chef": "Chef in a hospital kitchen",
    "v2_03_construction_site_supervisor": "Construction site supervisor", "v2_04_council_administrative_officer": "Council administrative officer",
    "v2_05_packaging_designer_pharma": "Packaging designer for a pharma company", "v2_06_sparse_one_line": "Sparse one-line CV",
    "v2_07_school_leaver_retail": "School leaver, part-time supermarket", "v2_08_accounting_coursework_only": "Accounting student, coursework only",
    "v2_09_backend_developer_hospital": "Backend developer: hospital client", "v2_10_backend_developer_bank": "Backend developer: bank client",
    "v2_11_backend_developer_school": "Backend developer: school client", "v2_12_garbled_text": "Garbled-text CV",
    "v3_01_pharmacist": "Pharmacist", "v3_02_nursing_student_coursework": "Nursing student (study in progress)",
    "v3_03_medical_centre_receptionist": "Receptionist at a medical centre", "v3_04_heavy_truck_driver_medical_supplies": "Truck driver delivering medical supplies",
    "v3_05_primary_school_teacher": "Primary school teacher", "v3_06_bank_data_analyst": "Data analyst at a bank",
    "v3_07_social_worker": "Social worker (child protection)", "v3_08_mechanical_technician_bus_depot": "Bus-depot mechanical technician",
    "v3_09_school_leaver_wants_to_be_a_doctor": "School leaver who wants to be a doctor", "v3_10_law_firm_software_developer": "Software developer at a law firm",
    "v3_11_law_firm_legal_secretary": "Legal secretary at a law firm", "v3_12_newspaper_reporter": "Newspaper reporter"}


def main():
    cases = {c["id"]: c for c in metrics.load_cases() + metrics.load_cases(ROOT / "bench" / "cases" / "career_cases_holdout_v2.yaml")
             } | {c["id"]: c for c in metrics.load_cases(ROOT / "bench" / "cases" / "career_cases_holdout_v3.yaml")}
    defs, reg = assess.load_definitions(), assess.load_regulated()
    cat = pipeline.get_catalogue()
    direct = json.loads((RUNS / "career_llm_direct_anthropic_claude-haiku-5.5_2026-10-27_m2.json").read_text(encoding="utf-8"))
    examples = {}
    defs2, reg2 = assess.load_definitions(ROOT / "data/processed/area_definitions_v2.yaml"), assess.load_regulated(ROOT / "data/processed/regulated_areas_v2.yaml")
    for fn in EVIDENCE_RUNS + [V3_RUN]:
        p = RUNS / fn
        if not p.exists():
            continue
        run = json.loads(p.read_text(encoding="utf-8"))
        for cid, st in run["stages"].items():
            if cid in examples or cid not in cases:
                continue
            rb = replay.rebuild(st, *( (defs2, reg2) if fn == V3_RUN else (defs, reg) ))
            if not rb["ok"]:
                continue
            c = cases[cid]
            prof = pipeline.build_profile("Participant", c["cv_text"], today=pipeline.REFERENCE_DATE)
            rule = pipeline.run(prof)["scores"].sort_values("score", ascending=False).head(10)
            rm = st.get("run_meta") or {}
            examples[cid] = dict(
                id=cid, title=TITLES.get(cid, cid), cv_text=c["cv_text"], split=c["split"],
                supported=rb["supported"], exploration=rb["exploration"], validation_log=rb["validation_log"],
                classes=rb["classes"], warnings=st.get("warnings", []),
                records=[dict(evidence_id=r.evidence_id, evidence_type=r.evidence_type, role=r.role, contribution=r.contribution,
                              domain_context=r.domain_context, quote=r.quote, status=r.status) for r in rb["records"]],
                rule_top10=[dict(area_id=r.area_id, name=r.name) for r in rule.itertuples()],
                direct_top10=[dict(area_id=t["area_id"], name=t["name"]) for t in direct["top"].get(cid, [])],
                run_meta=dict(model=(rm.get("assessment") or {}).get("model"), provider=(rm.get("assessment") or {}).get("provider"),
                              latency_s=round(sum((rm.get(k) or {}).get("latency_s", 0) or 0 for k in ("extraction", "assessment")), 1),
                              completion_tokens=sum(((rm.get(k) or {}).get("usage") or {}).get("completion_tokens", 0) or 0
                                                    for k in ("extraction", "assessment"))))
    out = dict(note="Synthetic example CVs and recorded outputs. Built offline by scripts/build_pilot_examples.py.",
               area_names=dict(zip(cat.area_id, cat.name)), examples=examples)
    dest = ROOT / "data" / "demo" / "pilot_examples.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", dest.relative_to(ROOT), len(examples), "examples,", round(dest.stat().st_size / 1024), "KB")


if __name__ == "__main__":
    main()
