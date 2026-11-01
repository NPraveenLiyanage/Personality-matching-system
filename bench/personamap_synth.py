"""Invented PersonaMap reports in the same layout as the real one (same headings, same step blocks, a running page header with a made-up
name). Every sentence is original and chosen from the preference percentages, so no real person's report text is reproduced and each
profile has distinctive text a model can quote. SYNTHETIC: used only for the fit benchmark and tests.
"""
from __future__ import annotations

# (side text for the first pole when > 50, text for the second pole when < 50). Strength words follow the shared bands.
LINES = {
    "E": ("You draw energy from conversation and bring people along with you.",
          "You recharge alone and prefer a few close working relationships to a wide circle."),
    "N": ("You explain things through meaning and pattern rather than literal detail.",
          "You trust concrete facts and what experience has shown, and you prefer practical detail."),
    "F": ("You weigh how people will be affected before you decide anything.",
          "You decide by logic and consistent criteria, even when the answer is uncomfortable."),
    "J": ("You plan and schedule early and like decisions settled.",
          "You keep options open, adapt as you go, and work well when plans change late."),
}
EXTRA = {
    "E": ("Meetings and open discussion leave you energised rather than tired.",
          "Long stretches of interruption-free work are where you do your best thinking."),
    "N": ("You are quick to see where an idea could lead and slower to check the small print.",
          "You are careful with the small print and slower to trust ideas that have no example behind them."),
    "F": ("Harmony in a team matters to you, and you notice quickly when someone is left out.",
          "You give direct feedback plainly and expect others to do the same."),
    "J": ("An unclosed list or an open question bothers you until it is dealt with.",
          "A fixed timetable feels confining; you prefer to see what the day brings."),
}
STEP_TEXT = {
    "Fastest step": "Fastest step", "Strong": "Strong", "Moderate": "Moderate", "Most-skipped step": "Most-skipped step",
    "Slowest step": "Slowest step", "Developing": "Developing",
}
STEPS = ["Read the situation", "Frame the meaning", "Plan the approach", "Commit and execute"]
COMMIT_LINE = {
    "Fastest step": "You decide quickly and are comfortable closing a question once you have enough.",
    "Strong": "You close decisions reliably once the plan is clear.",
    "Moderate": "You close decisions at an ordinary pace.",
    "Most-skipped step": "The plan is ready before the decision is, and closing is the step you are most likely to put off.",
    "Slowest step": "Closing a decision is the slowest part of your process; you keep gathering information.",
}


def _line(dim: str, pct: float, extra: bool = False) -> str | None:
    if abs(pct - 50) < 5:
        return None
    return (EXTRA if extra else LINES)[dim][0 if pct > 50 else 1]


def _word(pct: float) -> str:
    d = abs(pct - 50)
    return "Balanced" if d < 5 else "Slight" if d < 15 else "Moderate" if d < 30 else "Strong"


def make_report(name: str, prefs: dict, ratings: list[str], date: str = "1 March 2026") -> str:
    """prefs: {"E","N","F","J"} as % of the first pole; ratings: four step ratings in order."""
    E, N, F, J = (prefs[d] for d in "ENFJ")
    code = "".join(("X" if abs(prefs[d] - 50) < 5 else (a if prefs[d] > 50 else b)) for d, (a, b) in
                   zip("ENFJ", (("E", "I"), ("N", "S"), ("F", "T"), ("J", "P"))))
    header = ["CONFIDENTIAL - PERSONAL. Prepared for the named participant only.", "Example Consultancy (Pvt) Ltd, 2026.",
              "PersonaMap is an invented example for testing.", f"PersonaMap Personalised Personality Profile - {name}"]
    pole = {"E": ("Extroverted", "Introverted"), "N": ("Intuition", "Sensing"), "F": ("Feeling", "Thinking"), "J": ("Judging", "Perceiving")}

    def pct_block() -> list[str]:
        out = []
        for d in "ENFJ":
            v = prefs[d]
            if abs(v - 50) < 5:
                out += ["50% - evenly balanced"] if d == "E" else [f"{int(round(v))}% - evenly balanced"]
                out += list(pole[d])
            else:
                first = v > 50
                out += [f"{int(round(v if first else 100 - v))}% {pole[d][0 if first else 1]}", *pole[d]]
        return out

    cover = header + ["Prepared for", name, "Profile code", " ".join(code), "Temperament", "Example", "Your two readings",
                      "ENFJ - Connection Builder   /   INFJ - Visionweaver" if abs(E - 50) < 5 else "Example reading",
                      "Report date", date, "How to read this report", "This describes preferences and tendencies only."]
    p2 = header + ["Personality profile summary", "Your four preference results, and what each one means."] + pct_block() + [
        f"Overall profile: {code}", "A short invented summary for testing."]
    rows = []
    for d, label in zip("ENFJ", ("E - I", "S - N", "T - F", "J - P")):
        v = prefs[d]
        side = "Both" if abs(v - 50) < 5 else pole[d][0 if v > 50 else 1]
        rows += [label, side, _word(v), _line(d, v) or "Genuinely even on this scale."]
    p3 = header + ["Your profile", "Your responses place you among the Idealists.", "Dimension", "Your side", "Strength",
                   "What this looks like in practice"] + rows + ["Your two readings", "Both are examples."]
    stand = [("■ " + s) for d in "ENFJ" if (s := _line(d, prefs[d]))]
    effort = [("■ " + s) for d in "ENFJ" if (s := _line(d, 100 - prefs[d], True))]
    drains = [("■ " + s) for d in "ENFJ" if (s := _line(d, 100 - prefs[d], True))]
    p4 = header + ["What stands out most about you"] + (stand or ["■ Your results are close to even on every scale."]) + [
        "What sets you apart", "■ " + COMMIT_LINE.get(ratings[3], "You close decisions at an ordinary pace."),
        "Your strengths", "What you are likely to do well"] + [("■ " + s) for d in "ENFJ" if (s := _line(d, prefs[d], True))] + [
        "What may take more conscious effort"] + (effort[:2] or ["■ Nothing stands out."]) + [
        "What is likely to drain you"] + (drains[2:] or drains or ["■ Nothing stands out."])
    steps_block = ["1. " + STEPS[0], "2. " + STEPS[1], "3. " + STEPS[2], "4. " + STEPS[3]]
    labels = []
    for r in ratings:
        labels += [STEP_TEXT[r], "A short invented note on this step."]
    p5 = header + ["Under pressure", "This section describes likely tendencies.", "Likely triggers",
                   _line("J", J, True) or "Unclear deadlines.", "How you solve problems",
                   "Your profile suggests an approach drawn from your results."] + steps_block + labels + [
        "One adjustment to try: write down the decision you are putting off.", "How you would be likely to lead",
        (_line("E", E) or "Your energy is even, so your style depends on the setting.") + " " + (_line("F", F) or "")]
    p6 = header + ["Working with others", "When you follow", (_line("J", J) or "You follow plans lightly.") + " You like to know the reason for a task.",
                   "Your development priorities", "Priority", "Close decisions on", "a timetable", "In summary", "•",
                   "A short invented strength.", "Does this fit?", "Both readings are yours."]
    return "\f".join("\n".join(pg) for pg in (cover, p2, p3, p4, p5, p6))
