"""Career Area Catalogue: ISCO-08 minor groups -> field-based career areas.

Rules (documented in the notebook, section 4):
  1. Base unit is the ISCO minor group (3 digits). Armed Forces (major 0) are excluded.
  2. Professional/associate/clerical groups that are the same field are MERGED into one area,
     so an area spans skill levels instead of encoding them ("area, not level").
  3. Every area is renamed to a field noun, not a designation.
  4. A few additive "lens" areas are carved out of unit groups ISCO lumps together
     (data science, AI/ML, UX, ...). They overlap their parents on purpose and are flagged,
     because ISCO-08 predates several of these fields. Each carries a small, explicit
     supplement text so the modern vocabulary is visible and auditable.
"""
from __future__ import annotations

import pandas as pd

from . import isco

TECH = "Technology & Data"
SCI = "Science, Engineering & Built Environment"
HEALTH = "Health, Care & Wellbeing"
BUS = "Business, Finance & Management"
EDU = "Education, Social & Public Service"
CREATIVE = "Creative, Media & Culture"
SERVICE = "Hospitality, Retail & Personal Services"
PROD = "Production, Trades, Transport & Operations"
AGRI = "Agriculture, Forestry & Fisheries"

CLUSTERS = [TECH, SCI, HEALTH, BUS, EDU, CREATIVE, SERVICE, PROD, AGRI]

# (area name, cluster, [ISCO minor groups])
AREA_DEFS: list[tuple[str, str, list[str]]] = [
    # --- Managers (1)
    ("Government & public-sector leadership", EDU, ["111"]),
    ("Executive leadership & general management", BUS, ["112"]),
    ("Business services & administration management", BUS, ["121"]),
    ("Sales, marketing & R&D management", BUS, ["122"]),
    ("Agricultural production & farm management", AGRI, ["131", "611", "612", "613"]),
    ("Manufacturing, construction & logistics management", PROD, ["132"]),
    ("ICT service management", TECH, ["133"]),
    ("Professional services management", BUS, ["134"]),
    ("Hospitality management", SERVICE, ["141"]),
    ("Retail & wholesale management", SERVICE, ["142"]),
    ("Sports, culture & other services management", SERVICE, ["143"]),
    # --- Science, engineering
    ("Physical & earth sciences", SCI, ["211"]),
    ("Mathematics, statistics & actuarial science", SCI, ["212"]),
    ("Life sciences, biology & laboratory science", SCI, ["213", "314"]),
    ("Engineering & engineering technology", SCI, ["214", "311"]),
    ("Electrical, electronics & telecom engineering", SCI, ["215"]),
    ("Architecture, planning, surveying & design", SCI, ["216"]),
    # --- Health
    ("Medicine", HEALTH, ["221"]),
    ("Nursing & midwifery", HEALTH, ["222", "322"]),
    ("Traditional & complementary medicine", HEALTH, ["223", "323"]),
    ("Paramedic & emergency care", HEALTH, ["224"]),
    ("Veterinary science & animal health", HEALTH, ["225", "324"]),
    ("Dentistry, pharmacy & allied health therapies", HEALTH, ["226"]),
    ("Medical & pharmaceutical technology", HEALTH, ["321"]),
    ("Community health & health support", HEALTH, ["325"]),
    ("Sports coaching & fitness", HEALTH, ["342"]),
    ("Personal care & care assistance", HEALTH, ["532"]),
    # --- Education
    ("University & higher education teaching", EDU, ["231"]),
    ("Vocational education & training", EDU, ["232"]),
    ("Secondary school teaching", EDU, ["233"]),
    ("Primary & early-childhood teaching and child care", EDU, ["234", "531"]),
    ("Specialist teaching & education advisory", EDU, ["235"]),
    # --- Business & finance
    ("Finance, accounting & financial analysis", BUS, ["241", "331"]),
    ("Management analysis, HR & organisational development", BUS, ["242"]),
    ("Sales, marketing & public relations", BUS, ["243", "332"]),
    ("Business services: events, recruitment & real estate", BUS, ["333"]),
    ("Administrative & executive support", BUS, ["334", "412"]),
    ("Office administration", BUS, ["411"]),
    ("Data entry & keyboard operation", BUS, ["413"]),
    ("Banking & payment services clerks", BUS, ["421"]),
    ("Numerical & accounting clerks", BUS, ["431"]),
    ("Records, mail & other clerical support", BUS, ["441"]),
    # --- ICT
    ("Software & applications development", TECH, ["251"]),
    ("Database, systems & network administration", TECH, ["252"]),
    ("ICT operations, user support & telecoms", TECH, ["351", "352"]),
    # --- Law, social, culture
    ("Law & justice", EDU, ["261"]),
    ("Libraries, archives & museums", CREATIVE, ["262"]),
    ("Social sciences, psychology & counselling", EDU, ["263"]),
    ("Writing, journalism & languages", CREATIVE, ["264"]),
    ("Creative & performing arts", CREATIVE, ["265"]),
    ("Photography, design support & culinary arts", CREATIVE, ["343"]),
    ("Government regulation & compliance", EDU, ["335"]),
    ("Paralegal, social work & community support", EDU, ["341"]),
    ("Protective services (police, fire, security)", EDU, ["541"]),
    # --- Services
    ("Client information & contact-centre services", SERVICE, ["422"]),
    ("Travel, tourism & guiding", SERVICE, ["511"]),
    ("Cooking & food preparation", SERVICE, ["512", "941"]),
    ("Food & beverage service", SERVICE, ["513"]),
    ("Hairdressing, beauty & grooming", SERVICE, ["514"]),
    ("Housekeeping & facilities supervision", SERVICE, ["515"]),
    ("Other personal services", SERVICE, ["516"]),
    ("Retail, shop & street sales", SERVICE, ["521", "522", "523", "524", "952"]),
    ("Cleaning services", SERVICE, ["911", "912"]),
    ("Street services, waste collection & other elementary work", SERVICE, ["951", "961", "962"]),
    # --- Agriculture
    ("Forestry, fishery & hunting", AGRI, ["621", "622"]),
    ("Subsistence farming, fishing & agricultural labour", AGRI, ["631", "632", "633", "634", "921"]),
    # --- Production, trades, transport
    ("Industrial production supervision & process control", PROD, ["312", "313"]),
    ("Aviation & maritime operations", PROD, ["315"]),
    ("Stores, logistics & transport clerks", PROD, ["432"]),
    ("Building & construction trades", PROD, ["711", "712", "713"]),
    ("Metalwork, welding & fabrication", PROD, ["721"]),
    ("Machinery mechanics, toolmaking & repair", PROD, ["722", "723"]),
    ("Handicrafts & artisan crafts", CREATIVE, ["731"]),
    ("Printing trades", PROD, ["732"]),
    ("Electrical & electronics installation & repair", PROD, ["741", "742"]),
    ("Food processing & baking trades", PROD, ["751"]),
    ("Woodworking & cabinet-making", PROD, ["752"]),
    ("Garment, tailoring & textile trades", PROD, ["753"]),
    ("Other craft & specialist trades", PROD, ["754"]),
    ("Mining, metal & chemical plant operation", PROD, ["811", "812", "813"]),
    ("Manufacturing machine operation", PROD, ["814", "815", "816", "817", "818"]),
    ("Assembly work", PROD, ["821"]),
    ("Professional driving & rail operation", PROD, ["831", "832", "833"]),
    ("Mobile plant & marine deck operation", PROD, ["834", "835"]),
    ("Labouring in mining, construction, manufacturing & transport", PROD, ["931", "932", "933"]),
]

EXCLUDED_MINOR = ["011", "021", "031"]  # Armed Forces

# Additive "lens" areas: (name, cluster, [ISCO unit groups], supplement text)
LENS_DEFS: list[tuple[str, str, list[str], str]] = [
    ("Data science & analytics", TECH, ["2120", "2511", "2521", "2421"],
     "data science data analytics data analyst business intelligence dashboards data visualisation "
     "data mining predictive modelling statistical modelling big data insights reporting"),
    ("AI & machine learning engineering", TECH, ["2511", "2512", "2519", "2120"],
     "artificial intelligence machine learning deep learning natural language processing neural networks "
     "model training prediction classification algorithms"),
    ("UX, product & digital design", TECH, ["2513", "2166", "2519", "2511"],
     "user experience interface design usability prototyping product design digital product requirements "
     "stakeholders"),
    ("IoT, embedded & smart systems", TECH, ["2152", "2153", "2519", "3511"],
     "internet of things embedded systems sensors microcontrollers connected devices smart home automation "
     "monitoring"),
    ("Cybersecurity & information security", TECH, ["2523", "2529", "2522"],
     "cybersecurity information security protect systems networks threats risk compliance"),
    ("Psychology & behavioural research", EDU, ["2634", "2632", "2635", "2120"],
     "psychology behavioural science mental health emotional wellbeing human behaviour assessment research"),
    ("Economics & public policy analysis", BUS, ["2631", "2422", "2120"],
     "economic analysis policy evaluation public policy research impact assessment"),
    ("Training, learning & development", BUS, ["2424", "2356", "2351"],
     "learning and development corporate training instructional design facilitation workshops capability building"),
    ("Music performance & production", CREATIVE, ["2652", "2654", "3521"],
     "music composition performance sound production recording audio musician songwriter"),
]


def _assemble_text(codes: list[str], level: int) -> tuple[str, list[str], list[str]]:
    """Concatenate definition + tasks + titles + examples for the given ISCO codes."""
    s = isco.load_structure()
    texts, examples, titles = [], [], []
    for c in codes:
        row = s[(s.code == c) & (s.level == level)]
        if row.empty:
            raise KeyError(f"ISCO {level}-level code not found: {c}")
        r = row.iloc[0]
        titles.append(r.title)
        texts.append(r.title)
        texts.append(isco.clean_text(r.definition))
        texts.append(isco.clean_text(r.tasks))
        examples += isco.example_occupations(r.included)
    return " ".join(t for t in texts if t), titles, examples


def build_catalogue() -> pd.DataFrame:
    s = isco.load_structure()
    band = isco.major_skill_band()
    units = isco.unit_groups()
    recs = []

    # --- merged / renamed ISCO areas
    for name, cluster, minors in AREA_DEFS:
        texts, titles, examples, unit_codes = [], [], [], []
        for m in minors:
            t, ti, _ = _assemble_text([m], 3)
            texts.append(t)
            titles.append(ti[0])
            for _, u in units[units.code.str.startswith(m)].iterrows():
                unit_codes.append(u.code)
                texts.append(u.title + " " + isco.clean_text(u.definition) + " " + isco.clean_text(u.tasks))
                examples += isco.example_occupations(u.included)
        bands = sorted({band[m[0]] for m in minors})
        recs.append(dict(
            name=name, cluster=cluster, kind="isco", isco_minor=",".join(minors),
            isco_units=",".join(unit_codes), isco_titles=" | ".join(titles),
            band_min=min(bands), band_max=max(bands), major=minors[0][0],
            text=f"{name}. " + " ".join(texts),
            examples=examples[:60], supplement="",
        ))

    # --- lens areas
    for name, cluster, unit_codes, supplement in LENS_DEFS:
        t, titles, examples = _assemble_text(unit_codes, 4)
        bands = sorted({band[c[0]] for c in unit_codes})
        recs.append(dict(
            name=name, cluster=cluster, kind="lens", isco_minor=",".join(sorted({c[:3] for c in unit_codes})),
            isco_units=",".join(unit_codes), isco_titles=" | ".join(titles),
            band_min=min(bands), band_max=max(bands), major=unit_codes[0][0],
            text=f"{name}. {supplement}. {t}", examples=examples[:60], supplement=supplement,
        ))

    df = pd.DataFrame(recs)
    df.insert(0, "area_id", [f"A{i:03d}" for i in range(1, len(df) + 1)])
    df["n_isco_units"] = df.isco_units.str.count(",") + 1
    return df


def coverage_report(cat: pd.DataFrame | None = None) -> dict:
    """Check every non-armed-forces ISCO minor group is covered by exactly one merged area."""
    cat = cat if cat is not None else build_catalogue()
    all_minor = set(isco.minor_groups().code) - set(EXCLUDED_MINOR)
    assigned = [m for _, _, ms in AREA_DEFS for m in ms]
    dup = sorted({m for m in assigned if assigned.count(m) > 1})
    return dict(
        isco_minor_total=len(isco.minor_groups()),
        excluded_armed_forces=len(EXCLUDED_MINOR),
        in_scope=len(all_minor),
        assigned=len(set(assigned)),
        missing=sorted(all_minor - set(assigned)),
        unknown=sorted(set(assigned) - all_minor),
        duplicates=dup,
        areas_isco=int((cat.kind == "isco").sum()),
        areas_lens=int((cat.kind == "lens").sum()),
        areas_total=len(cat),
    )
