"""Concept lexicon: the bridge between how people write CVs and how ISCO describes work.

Each concept has
  triggers : regexes searched in a CV / free-text passions  (person side)
  vocab    : ISCO-style words that describe the concept     (area side)
Affinity of an area to a concept = similarity between the area's ISCO text and `vocab`.
The same concept ids are used for the interests intake in the app, so a stated passion
("music") and a CV mention flow through the same machinery.

This lexicon is deliberately plain and editable. It is the main thing the validation
rounds are expected to refine.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Concept:
    id: str
    label: str
    triggers: tuple[str, ...]
    vocab: str


def _c(id, label, triggers, vocab):
    return Concept(id, label, tuple(triggers), vocab)


CONCEPTS: list[Concept] = [
    _c("statistics", "Statistics & quantitative modelling",
       [r"statistic", r"regression", r"forecast", r"arima", r"hypothesis test", r"data sampling", r"probabilit",
        r"quantitative"],
       "statistics statistical mathematical mathematics models sampling survey data analysis forecast "
       "quantitative research methods"),
    _c("data_analytics", "Data analytics & visualisation",
       [r"data analy", r"data mining", r"dashboard", r"visual analytics", r"power ?bi", r"tableau",
        r"business intelligence", r"reporting", r"insight", r"data-driven", r"data visuali"],
       "data analysis analyse information interpret trends reports business decisions statistics research "
       "computer systems databases"),
    _c("ml_ai", "Machine learning & AI",
       [r"machine learning", r"\bai\b", r"artificial intelligence", r"\bnlp\b", r"natural language", r"deep learning",
        r"neural", r"predictive model", r"classification model", r"feature engineering", r"bert\b", r"transformer"],
       "artificial intelligence machine learning algorithms software systems computer data develop research "
       "models analysis"),
    _c("software_dev", "Software development",
       [r"python", r"\bjava\b", r"javascript", r"\bmern\b", r"react", r"node\.?js", r"flask", r"web application",
        r"full[- ]stack", r"software", r"\bapi\b", r"programming", r"c\+\+", r"c#", r"typescript"],
       "software applications develop programs code computer programming web design test systems "
       "specifications"),
    _c("databases", "Databases & data engineering",
       [r"mysql", r"mongodb", r"oracle", r"sqlite", r"postgres", r"\bsql\b", r"data warehous", r"data engineering",
        r"database", r"schema", r"\betl\b"],
       "database design data warehouse administration management storage data models systems computer "
       "information"),
    _c("systems_analysis", "Systems & requirements analysis",
       [r"requirement", r"specification", r"systems? analy", r"system testing", r"quality assurance", r"\bqa\b",
        r"data validation", r"business analy", r"user stor"],
       "systems analysis requirements specifications business needs users design test quality information "
       "systems computer"),
    _c("iot_electronics", "IoT, embedded & electronics",
       [r"\biot\b", r"arduino", r"esp32", r"sensor", r"microcontroller", r"\bmqtt\b", r"embedded", r"circuit",
        r"electronic", r"raspberry"],
       "electronic electrical equipment sensors circuits control systems devices design engineering install "
       "telecommunications computer"),
    _c("cloud_infra", "Cloud, networks & infrastructure",
       [r"\baws\b", r"azure", r"cloud", r"devops", r"docker", r"deploy", r"server", r"network", r"linux"],
       "network systems administration cloud servers deployment infrastructure computer information "
       "technology"),
    _c("cybersecurity", "Cybersecurity",
       [r"cyber", r"infosec", r"information security", r"penetration test", r"encryption"],
       "security protect systems networks information threats risk computer"),
    _c("ux_design", "UX & interface design",
       [r"\bux\b", r"user experience", r"ui design", r"\bui\b", r"figma", r"prototype", r"graphic design",
        r"wireframe"],
       "design user interface graphic multimedia visual web usability digital"),
    _c("research", "Research & publication",
       [r"research", r"ieee", r"publish", r"publication", r"journal", r"conference", r"thesis", r"dissertation"],
       "research study investigate publish scientific theory findings analyse experiments develop knowledge"),
    _c("org_workforce", "Organisation & workforce analysis",
       [r"workforce", r"organi[sz]ational", r"human resource", r"\bhr\b", r"culture", r"stakeholder",
        r"recommendation", r"talent", r"recruit", r"employee"],
       "organisation management human resources policies workforce employees strategy recommendations "
       "efficiency analyse advise"),
    _c("market_geo", "Market, customer & location insight",
       [r"market", r"location intelligence", r"spatial", r"geograph", r"\bgis\b", r"growth opportunit",
        r"customer segment", r"consumer"],
       "market research survey geographic spatial planning sales marketing customers business growth "
       "analyse"),
    _c("psychology", "Psychology & mental health",
       [r"bipolar", r"mental", r"emotion", r"psycholog", r"behaviou?r", r"wellbeing", r"counsel"],
       "psychology mental health behaviour emotional counselling therapy wellbeing patients assessment "
       "research"),
    _c("healthcare", "Healthcare & medicine",
       [r"patient", r"clinic", r"hospital", r"treatment", r"\bnurs", r"medical", r"doctor", r"ayurved",
        r"pharma"],
       "health patients medical treatment care clinic doctors nursing diagnose therapy"),
    _c("teaching", "Teaching & training",
       [r"\bteach", r"lectur", r"tutor", r"mentor", r"\btrain(er|ing)\b", r"curriculum", r"workshop",
        r"instructor"],
       "teach students education instruct training lessons curriculum learning school courses"),
    _c("finance", "Finance & accounting",
       [r"financ", r"accounting", r"audit", r"budget", r"invest", r"\bbank", r"\btax\b", r"\bacca\b",
        r"\bcima\b", r"bookkeep"],
       "financial accounting audit budget banking investment tax money records"),
    _c("sales_marketing", "Sales, marketing & communications",
       [r"marketing", r"\bsales\b", r"brand", r"advertis", r"campaign", r"\bseo\b", r"social media",
        r"public relations", r"copywrit"],
       "sales marketing advertising promotion brand customers public relations communicate"),
    _c("management_pm", "Project & team management",
       [r"project manage", r"team lead", r"led a team", r"managed a team", r"scrum", r"\bagile\b",
        r"product owner", r"operations manage", r"supervis"],
       "manage plan coordinate direct projects teams resources operations leadership supervise"),
    _c("customer_service", "Customer service",
       [r"customer service", r"customer support", r"help ?desk", r"client relations", r"call cent"],
       "customers clients service support enquiries information assist advise"),
    _c("engineering_mech_civil", "Mechanical & civil engineering",
       [r"civil engineer", r"mechanical", r"structural", r"construction", r"\bcad\b", r"autocad",
        r"manufactur", r"solidworks"],
       "engineering design construction mechanical civil structures materials plans machinery"),
    _c("electrical_power", "Electrical & power systems",
       [r"electrical", r"power system", r"circuit design", r"\bplc\b", r"control system", r"telecom"],
       "electrical electronics power telecommunications equipment engineering install maintain"),
    _c("law_legal", "Law & compliance",
       [r"\blaw\b", r"legal", r"litigation", r"attorney", r"contract", r"compliance", r"paralegal"],
       "law legal court regulations contracts advise justice compliance"),
    _c("writing_media", "Writing, journalism & media",
       [r"creative writing", r"journalis", r"\bcontent (writer|creator|creation)", r"\beditor", r"\bblog",
        r"\bcopywrit", r"\btranslator", r"\binterpreter"],
       "write author journalist editor media articles language translate communicate publish"),
    _c("music_arts", "Music & performing arts",
       [r"music", r"guitar", r"piano", r"singing", r"composer", r"\bband\b", r"theatre", r"drama", r"dance",
        r"orchestra"],
       "music musician composer singer perform arts artist creative performing entertainment"),
    _c("visual_creative", "Visual arts, photography & film",
       [r"photograph", r"\bvideo\b", r"\bfilm", r"animation", r"illustrat", r"fashion", r"interior design",
        r"painting", r"drawing"],
       "design creative photography film video artistic visual media artist draw paint"),
    _c("hospitality_tourism", "Hospitality & tourism",
       [r"hotel", r"restaurant", r"tourism", r"\btravel", r"\bchef", r"\bcook", r"barista", r"catering"],
       "hotel restaurant food tourism guests travel cooking service catering hospitality"),
    _c("agriculture_env", "Agriculture & environment",
       [r"agricultur", r"\bfarm", r"\bcrop", r"horticult", r"forest", r"fisher", r"environmental (science|protection|engineer|impact)",
        r"sustainab", r"climate change", r"ecolog", r"conservation"],
       "agriculture farm crops animals forestry environment natural resources sustainable climate land"),
    _c("logistics", "Logistics & supply chain",
       [r"logistic", r"supply chain", r"warehouse", r"inventory", r"procure", r"\btransport"],
       "logistics supply chain warehouse inventory transport distribution stores procurement goods"),
    _c("science_lab", "Laboratory & natural sciences",
       [r"laborator", r"chemistry", r"biolog", r"physics", r"microbio", r"experiment", r"geolog"],
       "laboratory scientific chemistry biology physics experiments samples research natural sciences"),
    _c("social_community", "Community & social impact",
       [r"community", r"volunteer", r"\bngo\b", r"social work", r"charity", r"outreach", r"welfare",
        r"non-profit"],
       "social community welfare support families people services counselling development"),
    _c("entrepreneurship", "Entrepreneurship & business building",
       [r"entrepreneur", r"start-?up", r"\bfounder", r"own business", r"co-?found"],
       "business owner manage enterprise start small business sales strategy develop"),
]

CONCEPT_BY_ID = {c.id: c for c in CONCEPTS}

# Work-style cues, searched in each area's ISCO text. Used for the personality-fit component.
TRAIT_CUES: dict[str, str] = {
    "people": "customers clients patients students people public guests communicate advise counsel teach care "
              "negotiate persuade interview meet team assist serve explain consult",
    "ideas": "research analyse theory concepts design develop strategy innovate models creative policy plan "
             "advise evaluate investigate principles knowledge conceptual",
    "practical": "operate equipment machinery repair install physical manual tools handle produce construct "
                 "assemble drive maintain materials cut clean cook",
    "structure": "plan schedule organise coordinate procedures regulations standards administer supervise "
                 "records manage budgets monitor compliance systematic prepare",
    "values": "counsel care welfare support patients social ethical teach help children community rehabilitate "
              "advocate protect wellbeing",
    "analytic": "calculate analyse measure technical engineering evidence statistics audit test quantitative "
                "data models compute diagnose",
}
