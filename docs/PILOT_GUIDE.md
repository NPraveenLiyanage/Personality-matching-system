# Pilot guide (for demonstrating progress)

## Start it
```
cd "C:\Users\lnipu\SANDBOX\Personality matching system"
streamlit run app/streamlit_app.py
```
The landing page is **Evidence-first pilot**. Other pages: Overview report and Test bench (the earlier rule-based tools).

## Suggested 10-minute walk-through
1. **The problem (2 min).** Pick *Student who built a hospital app* (recorded example). Section 4 shows the earlier rule-based engine ranking Nursing, Paramedic and Medicine near the top, each tagged "Industry exposure only" by the new pipeline. The earlier direct AI prompt shows a medical-technology area. The new pipeline recommends Software & applications development and lists the healthcare areas only as labelled exploration.
2. **It does not just block healthcare words (2 min).** Pick *Practising nurse*, *Consultant physician*, *Accountant*, *Lawyer*: they keep their own areas. Pick *Nurse who built a scheduling tool*: Nursing stays direct, Software appears as transferable.
3. **Other safeguards (3 min).** *School leaver, skills list only* shows no recommendation and explains why. *Logistics coordinator (explicitly no clinical/accounting experience)* and *CV containing an injected instruction* show negation and prompt-injection handling. Section 3 ("What the checker changed") shows claims the backend downgraded.
4. **Live mode (optional, 3-5 min).** Choose "Try your own invented example text", keep the sample or paste invented text, tick the confirmation, run. It refuses text containing an email, phone number or link. Free models are slow and limited to 50 requests a day (2 per run).

## What to say and what not to say
- Say: results are from 22 + 12 invented cases written by the team; on the development cases no wrong-field area was shown as a supported recommendation, but the pipeline also finds fewer of the expected areas than the earlier engines (see `docs/PHASE3_RESULTS.md`).
- Do not say: "accurate", "validated", "ready for participants". Expected outcomes are not yet independently reviewed, definitions are AI-drafted, results are one run on a free model, and the held-out evidence is still thin.
- Privacy: live mode sends text to a free model whose provider may log prompts. Never paste a real CV. Real participants need consent and a compliant endpoint first (`docs/PRIVACY_ROUTING.md`).

## What is real and what is recorded
Recorded examples are stored outputs of the pipeline from the benchmark runs (`bench/runs/`), rebuilt offline. The earlier engines' lists for the same text are the frozen baselines. Live mode runs the same code on your text.
