"""Plain-English content for the Overview report: the checklist, glossary, stories, decisions and limits.

Kept as data (not buried in page code) so the page, the Markdown export and the tests all use the same words.
No real participant data appears here: only what the project learned.
"""
from __future__ import annotations

# status: "done" | "partly" | "open"
REQUIREMENTS = [
    ("R1", "Recommend career areas (a field of work), not job titles", "done",
     "94 areas built from the international ISCO-08 job classification."),
    ("R2", "Use the international ISCO classification as the base", "done",
     "Adapting it to Sri Lanka is still to do."),
    ("R3", "Score every tester against every area, then ask them for feedback", "partly",
     "Scoring and the feedback form are built. No tester feedback has been collected yet."),
    ("R4", "Never show 100+ options: show two short lists of 10", "done",
     "The engine scores everything but a person only sees about 20, then 10."),
    ("R5", "Sanity check: matching someone to most of the list means something is broken", "done",
     "An automatic 'is the map too generous?' check blocks a map where over a quarter of areas look suitable."),
    ("R6", "Testers rate each line 1 to 5 and explain anything below 'highly accurate'", "partly",
     "The form is built. Nobody has used it yet, so the 90% accuracy target is untested."),
    ("R7", "Ask about passions beyond the CV", "partly",
     "The intake and the 'surface a hidden passion' mechanism work. Real intake answers are not collected yet."),
    ("R8", "Let the person react: like, maybe, no, and why", "done", "Built into the test bench."),
    ("R9", "Use personality and leadership insights", "partly",
     "Personality is used. The report's leadership section is not used by the engine yet."),
    ("R10", "Later: study or work path, vacancies, apply, employers", "open", "Phase 2. Not started."),
]

GLOSSARY = {
    "Career area": "A field of work such as 'Data science' or 'Nursing'. Not a job title and not a seniority level.",
    "Match %": "How well an area fits this person, 0 to 100. It is a comparison across areas, not a promise.",
    "Evidence": "What the CV actually says, found by looking for known phrases (the keyword list).",
    "Working style": "How a person likes to work, taken from their personality report. It re-orders areas that already "
                     "fit. It cannot make an unrelated area fit.",
    "Level fit": "Whether the person's education and experience match the level the area usually needs.",
    "Is the map too generous?": "If over a quarter of all areas look suitable, the scoring is too loose and the map "
                                "should not be shown.",
    "Keyword list": "The list of phrases the engine looks for in a CV. If a career is missing from it, the engine is blind to it.",
    "Shortlist": "The top 20 areas a person is asked to react to, instead of all 94.",
    "Passion": "Something a person loves even if it is not on their CV. It can lift an area the CV never mentions.",
}

# Each: (short tab label, headline, what we saw, why, what we did)
WHAT_BROKE = [
    ("Too generous", "Our first scoring marked far too many careers as suitable",
     "Adding the parts together gave every degree-level area a built-in head start.",
     "Working style and level fit are nearly the same for most areas, so adding them lifted everything, "
     "even careers the CV never mentions.",
     "We multiply instead: evidence first, then working style, then level. An automatic check now blocks a generous map."),
    ("63 years", "A CV with overlapping jobs read as 63 years of experience",
     "Adding up each job's length counted the same calendar years many times.",
     "Founders and part-timers run several roles at once.",
     "We now count the calendar months covered by at least one role. The app also stopped crashing on big numbers."),
    ("Referees", "A referee's job title was read as the candidate's own career",
     "Teaching and entrepreneurship appeared as strengths because the referees held those jobs.",
     "The references section sits in the same document as the real experience.",
     "We ignore the references section."),
    ("Missing words", "The engine could not see an entire career",
     "A senior learning, consulting and media CV matched almost none of our phrases.",
     "The keyword list had been shaped around one technical CV.",
     "Version 2 adds the missing categories, and a coverage check now shows the words the engine ignores."),
    ("One hobby", "Adding one passion lowered every other area",
     "We averaged CV evidence with interests, so a hobby with no CV evidence dragged the average down.",
     "A passion should add, not subtract.",
     "Either source can now lift an area, and neither can lower the other."),
    ("Personality", "Working style changed the order but not who made the top 10",
     "For the people tested so far, switching personality off changed only neighbouring places.",
     "It describes how someone likes to work, not which field, so it is deliberately limited.",
     "We kept it, say so plainly, and will test with the other testers whether it adds value."),
    ("Look-alikes", "Several top areas are near-copies of each other",
     "Areas that share the same ISCO groups, such as security and database work, score almost alike.",
     "Our extra 'modern job' areas overlap their parents on purpose.",
     "An optional diversity setting trades some evidence for breadth. The right amount is a decision to make."),
]

DECISIONS = [
    ("D1", "Score every area, then narrow with the person's reactions", "A hard sector-to-sub-group-to-job funnel",
     "ISCO's big groups describe level of work, not field, so one early wrong guess could not be undone."),
    ("D2", "Areas merged across levels, plus 9 extra modern areas", "Use ISCO groups as they are",
     "The brief said area, not designation and not level."),
    ("D3", "A transparent rule-based scorer", "An AI judge", "Repeatable, explainable and free. An AI judge can be added later."),
    ("D4", "Multiply evidence x working style x level", "Add weighted parts", "Adding failed the 'too generous' check."),
    ("D5", "Passions add to CV evidence (either-or)", "Average them", "Averaging made a hobby lower every CV area."),
    ("D6", "A balanced personality result gets no weight", "Treat 50% as a data point",
     "The report itself refuses to read a pattern there."),
    ("D7", "Personality stays with the person", "Pass it to employers later",
     "The report says it must not be used for selection decisions."),
    ("D8", "Optional diversity setting, off by default", "Always diversify", "Breadth costs evidence; agree the setting with the consultant."),
    ("D9", "Versioned keyword list (v1, v2)", "Edit the list in place", "Lets us show before and after honestly."),
    ("D10", "No real person's data inside the app or repository", "Ship a real sample",
     "Real CVs and reports only enter at run time and live in session memory."),
    ("D11", "Keep adding evidence across strands", "'Any strong strand counts' scoring",
     "We tested it. On two rich CVs it marked 34% and 52% of areas suitable, so it fails the 'too generous' check."),
]

LIMITATIONS = [
    ("The catalogue is finer in technology than elsewhere",
     "Technology gets about 1.8 areas per ISCO group, science and engineering about 0.75, farming about 0.27. "
     "That can inflate technology in a technical person's top 10."),
    ("ISCO predates modern jobs", "Data science, AI and UX needed extra areas with a short supplement text."),
    ("The keyword list is hand-written and English-only",
     "It was tuned after looking at a few CVs, so the next testers are the real test."),
    ("Breadth can beat depth", "A person with one strong strand (music, media) can rank below a generalist management area."),
    ("A project is not a career", "A software project built for a clinic can look like a healthcare signal."),
    ("Personality is matched against ISCO's wording", "That is a rough stand-in for real work-style data."),
    ("No Sri Lanka specifics yet", "Local jobs and labour-market data are not in."),
    ("Self-employment is not an area", "ISCO describes what a job involves, not whether you run it yourself."),
]

NEXT_STEPS = [
    "Collect the interests intake from each tester and rerun.",
    "Run every tester through the same engine and compare (the 'too generous' check must hold for all).",
    "Run validation round 1 with the feedback form, fix what it shows, repeat for three rounds.",
    "Settle the catalogue questions: split engineering and sciences, how to treat managers, stable area IDs.",
    "Decide how the personality report's leadership section should feed the match.",
    "Only then design Phase 2 (vacancies, employers, applying), with a consent and privacy review.",
]

# Fields for the "same field, different levels" explorer: field -> ISCO minor groups (3-digit)
FIELD_GROUPS = {
    "Technology (ICT)": ["251", "252", "351", "352"],
    "Health": ["221", "222", "321", "322"],
    "Finance": ["241", "331"],
    "Arts and culture": ["265", "343", "262"],
    "Teaching": ["231", "232", "233", "234", "235", "531"],
    "Engineering": ["214", "215", "311"],
    "Business support": ["242", "333", "334", "411", "412"],
}
