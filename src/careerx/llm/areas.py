"""The closed list of 94 career areas as the LLM prompt numbers them (1-94, grouped by field).

Names are identical to data/processed/career_area_catalogue.csv; `to_catalogue_ids` maps prompt id -> area_id (A0xx).
"""
from __future__ import annotations

GROUPS: dict[str, list[str]] = {
    "Agriculture, Forestry & Fisheries": [
        "Agricultural production & farm management", "Forestry, fishery & hunting",
        "Subsistence farming, fishing & agricultural labour"],
    "Business, Finance & Management": [
        "Administrative & executive support", "Banking & payment services clerks",
        "Business services & administration management", "Business services: events, recruitment & real estate",
        "Data entry & keyboard operation", "Economics & public policy analysis",
        "Executive leadership & general management", "Finance, accounting & financial analysis",
        "Management analysis, HR & organisational development", "Numerical & accounting clerks",
        "Office administration", "Professional services management", "Records, mail & other clerical support",
        "Sales, marketing & R&D management", "Sales, marketing & public relations",
        "Training, learning & development"],
    "Creative, Media & Culture": [
        "Creative & performing arts", "Handicrafts & artisan crafts", "Libraries, archives & museums",
        "Music performance & production", "Photography, design support & culinary arts",
        "Writing, journalism & languages"],
    "Education, Social & Public Service": [
        "Government & public-sector leadership", "Government regulation & compliance", "Law & justice",
        "Paralegal, social work & community support", "Primary & early-childhood teaching and child care",
        "Protective services (police, fire, security)", "Psychology & behavioural research",
        "Secondary school teaching", "Social sciences, psychology & counselling",
        "Specialist teaching & education advisory", "University & higher education teaching",
        "Vocational education & training"],
    "Health, Care & Wellbeing": [
        "Community health & health support", "Dentistry, pharmacy & allied health therapies",
        "Medical & pharmaceutical technology", "Medicine", "Nursing & midwifery", "Paramedic & emergency care",
        "Personal care & care assistance", "Sports coaching & fitness", "Traditional & complementary medicine",
        "Veterinary science & animal health"],
    "Hospitality, Retail & Personal Services": [
        "Cleaning services", "Client information & contact-centre services", "Cooking & food preparation",
        "Food & beverage service", "Hairdressing, beauty & grooming", "Hospitality management",
        "Housekeeping & facilities supervision", "Other personal services", "Retail & wholesale management",
        "Retail, shop & street sales", "Sports, culture & other services management",
        "Street services, waste collection & other elementary work", "Travel, tourism & guiding"],
    "Production, Trades, Transport & Operations": [
        "Assembly work", "Aviation & maritime operations", "Building & construction trades",
        "Electrical & electronics installation & repair", "Food processing & baking trades",
        "Garment, tailoring & textile trades", "Industrial production supervision & process control",
        "Labouring in mining, construction, manufacturing & transport",
        "Machinery mechanics, toolmaking & repair", "Manufacturing machine operation",
        "Manufacturing, construction & logistics management", "Metalwork, welding & fabrication",
        "Mining, metal & chemical plant operation", "Mobile plant & marine deck operation",
        "Other craft & specialist trades", "Printing trades", "Professional driving & rail operation",
        "Stores, logistics & transport clerks", "Woodworking & cabinet-making"],
    "Science, Engineering & Built Environment": [
        "Architecture, planning, surveying & design", "Electrical, electronics & telecom engineering",
        "Engineering & engineering technology", "Life sciences, biology & laboratory science",
        "Mathematics, statistics & actuarial science", "Physical & earth sciences"],
    "Technology & Data": [
        "AI & machine learning engineering", "Cybersecurity & information security", "Data science & analytics",
        "Database, systems & network administration", "ICT operations, user support & telecoms",
        "ICT service management", "IoT, embedded & smart systems", "Software & applications development",
        "UX, product & digital design"],
}

NAMES: dict[int, str] = {}
FIELD_OF: dict[int, str] = {}
_i = 0
for _field, _names in GROUPS.items():
    for _n in _names:
        _i += 1
        NAMES[_i] = _n
        FIELD_OF[_i] = _field
assert len(NAMES) == 94


def area_list_text() -> str:
    """The numbered list, grouped by field, exactly as inserted in the system prompt."""
    out, i = [], 0
    for field, names in GROUPS.items():
        out.append(f"[{field}]")
        for n in names:
            i += 1
            out.append(f"{i}. {n}")
    return "\n".join(out)


def to_catalogue_ids(catalogue) -> dict[int, str]:
    """prompt id (1-94) -> catalogue area_id ('A0xx'). Raises if any name differs."""
    by_name = dict(zip(catalogue["name"], catalogue["area_id"]))
    missing = [n for n in NAMES.values() if n not in by_name]
    if missing or len(by_name) != 94:
        raise ValueError(f"Area names differ from the catalogue: {missing}")
    return {i: by_name[n] for i, n in NAMES.items()}
