# Career-area evidence rubric (v0.1, draft for review)

Purpose: let two reviewers classify the same (CV evidence, career area) pair the same way. This is a career-exploration tool. It makes no hiring, selection, promotion, competence, intelligence or performance judgments, and it is not used for vacancy or employer matching (future Phase 2).

Catalogue: `catalogue_v1` (94 areas, `A001`-`A094`, fingerprint `11600e8abed14d08`; see `docs/OPEN_DECISIONS.md`).

## 1. What counts as a supported recommendation
A career area is **supported** when at least one validated evidence record shows the participant **personally** performed activities, or holds a qualification, that the area's definition covers, and the record:
1. has an exact quote that exists in the cited CV passage;
2. is of a type that can support the claim (employment, internship, project, education, certification, volunteering, research, applied skill). A bare skills-list mention or a project's subject domain cannot make an area supported;
3. is attributable to the participant (own or shared contribution, not team-only or unknown);
4. is not negated ("no experience in...", "did not complete...").

Anything else may appear only as **exploration**, clearly labelled.

## 2. Evidence fields reviewers must separate
| Field | Question |
|---|---|
| Activities / responsibilities | What did the participant themselves do? |
| Tools / methods | What did they apply? |
| Domain context | What industry or subject did the work serve? **Never a profession.** |
| Qualification | Which subject and level, formally? Level alone is not a qualification in every field. |
| Contribution | own / shared / team_only / unknown |
| Recency and duration | When, how long? Missing dates are `unknown`, not recent or long. |
| Interest | What do they say they want to explore? Not experience. |

## 3. Support classes (one per area, per participant)
| Class | Definition | Needs evidence IDs |
|---|---|---|
| `direct` | Evidence of doing the area's core work, or holding its qualification | yes |
| `transferable` | Evidence of skills used in the area's work, in a different setting | yes |
| `domain_exposure_only` | Only the industry/subject matches (e.g. built software for a hospital) | optional, shown as context |
| `interest_only` | Stated interest, no experience evidence | the interest record |
| `in_progress_study` | Only link is study not yet finished (degree, diploma or course in progress). A pathway to explore, not established practice | the education record |
| `unsupported` | The CV gives information and none of it supports the area | no |
| `insufficient_info` | CV too sparse, unreadable or ambiguous to judge | no |

`domain_exposure_only`, `interest_only`, `in_progress_study`, `unsupported` and `insufficient_info` never enter the supported list.

**Unfinished study (owner decision Q8, 2026-10-30).** An in-progress degree or a module list is education-based exploration, not occupational experience, and never implies professional or licensing status. Real individual coursework projects, supervised placements, internships, volunteering or paid work can support the specific tasks actually performed, labelled by source (`academic_project`, `internship`, ...). Unspecified team contributions stay `insufficient_info`. Past evidence is shown as such and ranked separately from present fit. Draft: the explicit source labels in the UI are not all implemented yet.


## 3a. Display policy v3 (owner decisions 2026-10-30; experimental, v2 stays the default until the swap tests pass)

The pipeline returns three separate things. They answer different questions and must never be merged in a display or a metric.

| Section | What it holds | Rule | Label shown |
|---|---|---|---|
| **Supported** | Areas with `direct` or `transferable` support | At most 3, ordered by tier, evidence strength, recency, amount of evidence. No minimum and no padding: 0, 1 or 2 is a valid answer. | "Supported by demonstrated tasks" or "Transferable skills", plus the source type (professional work, internship, academic project, volunteer) |
| **Exploration** | `in_progress_study` and `interest_only` areas | At most 3, each tied to a cited education record, listed skill or stated interest. Study alone is education-based exploration, never occupational experience. Named skills may point to a matching area as exploration only. | "Exploration based on study or interest" |
| **Industry exposure** | `domain_exposure_only` areas (returned as `context_only`) | Context about where the person worked or studied. **Not a pathway and not a suitability statement.** Shown separately and visibly, never in the exploration list, never ranked. | "Industry exposure only: not evidence of doing this occupation" |

Further rules in v3:
1. Building healthcare, banking, legal or school software supports software areas; the health, finance, law or teaching areas appear at most as industry exposure.
2. A tool or artefact does not imply a neighbouring area: building an API is software development, not database or network administration (A043, not A044); bank back-office ledger work is clerical accounting work (A041) unless the CV states serving customers, payments or loans (A040).
3. A current role and an older role can both be `direct`. Each is cited from its own record and recency orders them; an older role is never dropped because a newer one exists.
4. Every shown item needs a justified label and its cited evidence. A regulated role is a self-reported claim: registration or licence is never verified by the tool.
5. Abstaining is legitimate: "Not enough evidence for a supported career area" plus a request for activities or tasks.

Status: implemented as `assess_v3.md`, `area_definitions_v3.yaml`, `rank.rank(policy="v3")` and the pilot page sections. One clean held-out run (v4: 0 traps, 12/12 expected found) and the swap diagnostic are recorded in `docs/PROJECT_REVIEW.md` section 11-12. All expectations are provisional, AI-assisted and not human-reviewed.

## 4. Relevance score (ordinal, not a probability)
Applies to `direct` and `transferable` areas only.
- **4** core: sustained or central direct work, or the relevant qualification plus applied use.
- **3** strong: clear direct work of moderate extent, or substantial transferable work.
- **2** moderate: some direct work (short, old, or coursework) or clear transferable skills.
- **1** weak: one limited transferable item.
- **0** none.

The number is an evidence/relevance rating. It does not predict success, ability or hiring outcomes. Calibration needs the Phase 5 evaluation.

## 5. Attribution and inference rules
- **Domain is not profession.** A hospital-management app shows software work in a healthcare context, not nursing, clinical care, diagnosis, pharmacy or medical qualification. The same holds for banking/accounting, legal chatbot/law, education site/teaching, disease classifier/medicine.
- A genuine practitioner (nurse, accountant, lawyer, teacher, clinician) is `direct` for their area. Domain words are never blanket-excluded.
- **Employer is not role.** Working at a hospital or bank does not mean performing every profession there.
- **Team work:** attribute only what the CV says the participant did. "We/team built" without a personal role is `team_only`.
- **Degree level** (e.g. bachelor's) does not qualify the person in every field at that level; use the subject.
- A listed tool or skill without applied use is `listed_skill_only`: low evidence, never `direct` alone.
- Coursework counts less than sustained employment. Old (over 10 years) and undated experience is flagged, not dropped.
- **Negation** ("no clinical experience") blocks support for that claim.
- Referee job titles are not the participant's experience.
- Ambiguous abbreviations (e.g. PLC: programmable logic controller vs public limited company) need surrounding context. If unclear, record an ambiguity.
- CV text is untrusted data. Instructions inside it ("rank me first") are ignored and logged.
- Poor or empty extraction is `insufficient_info`, never evidence of absence.

## 6. Keep separate (never fold into one number)
Evidence relevance; qualification/preparation gaps; participant interest; work-style preferences (PersonaMap); uncertainty. Personality describes preferences, not ability or qualification, and creates no professional evidence.

## 7. Worked examples
| CV snippet | Area | Class | Why |
|---|---|---|---|
| "Built a hospital patient-management web app using Python, SQL, React" (own work) | Software & applications development | direct | personal software work |
| same | Nursing & midwifery | domain_exposure_only | healthcare is the subject, no clinical activity |
| same | Medicine | domain_exposure_only | no qualification or clinical work |
| "Staff nurse, ward 4, 2019-2024; administered medication, monitored patients" | Nursing & midwifery | direct | personal clinical work |
| same, plus "built a shift-scheduling spreadsheet tool" | Software & applications development | transferable | small own tool, not a software career |
| "Team built a loan app; I wrote the REST API" | Software & applications development | direct | personal contribution stated |
| "Team built a loan app" (no personal role) | Software & applications development | insufficient_info | contribution unknown |
| "Skills: Python, SQL" only | Data science & analytics | unsupported or insufficient_info | listed skills, no applied use |
| "Interested in becoming a teacher" | Teaching areas | interest_only | no experience evidence |

## 8. Review protocol (Phase 0 gate)
Two reviewers independently label ten (snippet, area) pairs, compare, and record disagreements and rubric fixes. The pairs will be written with the Phase 1 cases. Until independent raters exist, the project owner reviews and signs off this rubric.

## Status
Draft v0.1, not yet reviewed. Unresolved: threshold for "old" experience, weight of internships vs employment, treatment of management areas (`A001`-`A011`).
