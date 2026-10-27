"""Benchmark metrics with explicit denominators (metrics_version 2).

These measure agreement with AUTHORED design expectations (supported / acceptable / trap areas per synthetic case). They are not
expert-rated relevance and not real-world accuracy. Overall agreement across all 94 areas is deliberately not reported: scoring
many irrelevant areas low would hide poor top recommendations.

Trap definition (v2): a trap is an area that has no supporting evidence in the CV and would be an UNSUPPORTED CLAIM if shown as a
supported recommendation. Showing it as a clearly labelled exploration option is allowed and counted separately. Baseline engines
have no exploration list, so every area they display counts as displayed-as-supported.

Engines may display fewer than k supported areas, so precision divides by the number actually displayed, and the mean number
displayed is reported next to recall (a baseline that always shows 10 gets recall more cheaply than one that shows 3).
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import yaml

METRICS_VERSION = 2
CASES_PATH = Path(__file__).resolve().parent / "cases" / "career_cases.yaml"


def load_cases(path=None) -> list[dict]:
    return yaml.safe_load(Path(path or CASES_PATH).read_text(encoding="utf-8"))


def case_metrics(case: dict, ranked: list[str], k: int = 10, exploration: list[str] | None = None) -> dict:
    """ranked: areas displayed as supported recommendations, best first. exploration: areas displayed with an exploration label."""
    top = list(ranked[:k])
    exploration = list(exploration or [])
    sup, acc, traps = set(case["supported"]), set(case.get("acceptable", [])), set(case.get("traps", []))
    trap_sup = [a for a in top if a in traps]
    return dict(
        top=top,
        exploration=exploration,
        n_displayed=len(top),
        supported_found=[a for a in top if a in sup],
        supported_missed=sorted(sup - set(top)),
        trap_hits=trap_sup,                                     # traps displayed AS SUPPORTED (alias kept from metrics v1)
        trap_as_exploration=[a for a in exploration if a in traps],
        n_in_authored_ok_set=sum(a in sup | acc for a in top),
        top1_in_authored_ok_set=bool(top) and top[0] in sup | acc,
        rank_of_first_supported=next((i + 1 for i, a in enumerate(ranked) if a in sup), None),
        abstained=len(top) == 0,
    )


def aggregate(cases: list[dict], per_case: dict[str, dict], k: int = 10) -> dict:
    """per_case: case id -> case_metrics(). Counts with denominators, overall and by category / split."""
    def block(cs: list[dict]) -> dict:
        m = [(c, per_case[c["id"]]) for c in cs if c["id"] in per_case]
        trap_cases = [(c, x) for c, x in m if c.get("traps")]
        sup_cases = [(c, x) for c, x in m if c["supported"]]
        ok_cases = [(c, x) for c, x in m if set(c["supported"]) | set(c.get("acceptable", []))]
        empty_cases = [(c, x) for c, x in m if not c["supported"]]
        n_sup = sum(len(c["supported"]) for c, _ in sup_cases)
        n_disp = sum(x["n_displayed"] for _, x in m)
        return dict(
            n_cases=len(m),
            domain_confusion_cases=f"{sum(bool(x['trap_hits']) for _, x in trap_cases)}/{len(trap_cases)}",
            domain_confusion_rate=_r(sum(bool(x['trap_hits']) for _, x in trap_cases), len(trap_cases)),
            trap_areas_displayed_as_supported=sum(len(x['trap_hits']) for _, x in m),
            trap_cases_shown_only_as_exploration=sum(bool(x['trap_as_exploration']) and not x['trap_hits'] for _, x in trap_cases),
            supported_recall=f"{sum(len(x['supported_found']) for _, x in sup_cases)}/{n_sup}",
            supported_recall_rate=_r(sum(len(x['supported_found']) for _, x in sup_cases), n_sup),
            all_supported_found_cases=f"{sum(not x['supported_missed'] for _, x in sup_cases)}/{len(sup_cases)}",
            mean_areas_displayed=round(n_disp / len(m), 2) if m else None,
            top1_in_authored_ok_set=f"{sum(x['top1_in_authored_ok_set'] for _, x in ok_cases)}/{len(ok_cases)}",
            authored_ok_share_of_displayed_lower_bound=_r(sum(x['n_in_authored_ok_set'] for _, x in ok_cases),
                                                           sum(x['n_displayed'] for _, x in ok_cases)),
            abstained_on_no_support_cases=f"{sum(x['abstained'] for _, x in empty_cases)}/{len(empty_cases)}",
            abstained_cases_total=sum(x['abstained'] for _, x in m),
        )

    out = dict(metrics_version=METRICS_VERSION, k=k, overall=block(cases))
    cats, splits = defaultdict(list), defaultdict(list)
    for c in cases:
        for cat in c.get("categories", []):
            cats[cat].append(c)
        splits[c.get("split", "unspecified")].append(c)
    out["by_category"] = {k_: block(v) for k_, v in sorted(cats.items())}
    out["by_split"] = {k_: block(v) for k_, v in sorted(splits.items())}
    return out


def _r(a: int, b: int):
    return round(a / b, 3) if b else None
