# Public CV and occupational dataset audit (desk research, 2026-10-30)

**Nothing was downloaded, copied or used.** This is a first screen from web pages read on 2026-10-30. It is **not legal advice**, and every row marked "verify" needs the primary source or a legal check before any use. Owner decision Q4: public datasets may be considered for training only after source-specific licence and privacy clearance, and nothing is trained or fine-tuned before explicit approval. A public licence label on a page does not prove the uploader had the rights to the underlying text.

## Verdict table
| Dataset | What it is | Licence as stated | Provenance / privacy | Fit for our use | Verdict |
|---|---|---|---|---|---|
| **O*NET OnLine / database** (USDOL/ETA) | Occupation tasks, skills, work activities | CC BY 4.0 with exceptions for external-source content; attribution and a change notice are required. The page does not mention ML training. | Government occupational data, no individuals | Reference for writing synthetic tasks (already used). Not CVs. | **Usable as a reference with attribution.** Ask the programme before bulk training use. |
| **ILO ISCO-08** | Occupation classification | "Free of charge, can be used without prior authorization"; the FAQ does not address attribution, redistribution or commercial use (contact isco@ilo.org to confirm) | No individuals | Backbone of our catalogue (already used). | **Usable; confirm redistribution terms if we ship the structure.** |
| **ESCO** (European Commission) | Occupations, skills, alternative labels | Not confirmed from the pages I could load (the licence page failed). It is generally described as open, with attribution; **verify on the official licence page**. | No individuals | Alternative labels for synonyms; skills for exploration hints. Not CVs. | **Candidate; verify licence first.** |
| **Sri Lanka SLSCO-11 / DCS NADA microdata** | National occupation classification; survey microdata | No open licence found on the pages searched | Survey microdata may carry confidentiality terms | Useful to align with local occupations. | **Not cleared; contact the Department of Census and Statistics.** |
| **TVEC national competency standards / LMI** | Sri Lankan vocational standards | No dataset or open licence found | Documents, not individuals | Good source of local task descriptions for non-degree trades. | **Not cleared; request permission or read for paraphrase only.** |
| **CareerCorpus** (Mendeley Data, 302 annotated resumes) | Anonymised resumes in six categories | CC BY 4.0 stated, but the site footer reserves text and data mining and AI-training rights, and the page does not say how the two interact. Five categories derive from a Kaggle set of LiveCareer resumes; one from LinkedIn public profiles. | Names, emails and phones replaced by placeholders; other personal data not addressed; scraping and consent not described | Closest to real CV text. | **Do not use.** Upstream rights are unclear. |
| **Kaggle "Resume Dataset" (snehaanbhawal)** | About 2,400 resumes scraped from LiveCareer | No licence found on the pages searched; a GitHub mirror says Apache-2.0, which applies to the mirror, not the data | Scraped from a commercial site; terms of that site apply | Popular in tutorials. | **Do not use** without LiveCareer's permission. |
| **ResumeAtlas** (Hugging Face, 13,389 resumes) | Resume classification set, 43 categories | MIT on the dataset page; the card does not say how resumes were collected; the paper describes search-engine collection | Sample rows show names, phones, emails and street addresses | Large but personal. | **Do not use.** Contains personal data; collection basis unclear. |
| **datasetmaster/resumes** (Hugging Face) | Mix of real and synthetic resumes | MIT on the card | Real resumes described only as anonymised submissions; no consent statement (I could not load the card myself; this is from a search summary: verify) | Mostly technical roles. | **Do not use** the real part; the synthetic part would need the card checked. |
| **PopResume** (Hugging Face) | Synthetic resumes for fairness testing of screeners | CC BY 4.0 reported; gated access (contact details required). I could not load the page; verify. | Reported as fully synthetic | Built for bias evaluation, not career-area labelling. | **Possible only for fairness testing; verify.** |

## What this means for the project
1. **Real-CV datasets found so far are not safe to use.** Each either scrapes a commercial site or social profiles, carries personal data, or has an unclear collection basis. A permissive licence label (MIT, CC BY) does not fix that.
2. **The reliable public sources are occupation references (O*NET, ISCO, possibly ESCO), not CV text.** They suit writing and checking synthetic CVs, and they do not contain our labels.
3. **For Sri Lanka there is no usable open CV or occupation-task dataset yet.** SLSCO-11 and TVEC standards would help, but permission is needed.
4. **Training data, when we get there:** invented synthetic CVs seeded from reference tasks (as in `docs/SYNTHETIC_DATA_METHOD.md`), plus participants' CVs only with specific consent for inference and, separately, for training. The PersonaMap workbook stays out of training.

## Decisions needed from the owner
- Approve contacting O*NET (training use), ILO (redistribution), the Department of Census and Statistics (SLSCO, NADA) and TVEC (competency standards) for written terms.
- Confirm ESCO's licence from the official page, or ask me to try again.
- Decide whether any public real-CV dataset is worth a legal review. My recommendation is no.

## Limits of this audit
Three pages failed to load with connection errors (the ESCO download page, the PopResume card and the datasetmaster card), so those rows rely on search summaries and are flagged "verify". I read licence statements from dataset pages and did not inspect the data. Page contents can change.

Sources read: https://www.onetonline.org/help/license, https://isco.ilo.org/en/faq/, https://data.mendeley.com/datasets/wzzwn37gmd/1, https://huggingface.co/datasets/ahmedheakl/resume-atlas, https://huggingface.co/datasets/datasetmaster/resumes (search summary), https://huggingface.co/datasets/sumin-yu/PopResume (search summary), https://esco.ec.europa.eu/en/use-esco/download (search summary), Kaggle listing mirrors (search summary), ILO labour-statistics profile for Sri Lanka, TVEC pages (search summary).
