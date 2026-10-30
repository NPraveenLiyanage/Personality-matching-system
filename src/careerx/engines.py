"""One result shape for every engine, plus the registry the app uses to pick one.

Engines: `rule` (the original keyword engine, the default) and `llm_evidence` (the evidence-first pipeline). A failed run is
returned as status "failed" with its reasons; there is never an automatic fallback from one engine to another.
Select with the CAREERX_ENGINE environment variable (default "rule"), which is the rollback switch.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from . import pipeline as PL

DEFAULT_ENGINE = "rule"
LABELS = {"rule": "Rule-based engine (keyword scoring)", "llm_evidence": "Evidence-first AI pipeline (prompted model, not fine-tuned)"}


@dataclass
class EngineResult:
    engine_id: str
    engine_version: str
    status: str                                           # accepted | repaired | failed | no_evidence
    supported: list[dict] = field(default_factory=list)   # ranked areas the engine stands behind
    exploration: list[dict] = field(default_factory=list)  # labelled, never shown as recommendations
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    validation_log: list[dict] = field(default_factory=list)
    run_meta: dict = field(default_factory=dict)

    @property
    def label(self) -> str:
        return LABELS.get(self.engine_id, self.engine_id)

    def top(self, n: int = 10) -> list[dict]:
        return (self.supported + self.exploration)[:n]


def selected_engine() -> str:
    e = os.environ.get("CAREERX_ENGINE", DEFAULT_ENGINE).strip() or DEFAULT_ENGINE
    return e if e in LABELS else DEFAULT_ENGINE


def run_rule(cv_text: str, name: str = "Participant", **_) -> EngineResult:
    prof = PL.build_profile(name, cv_text, today=PL.REFERENCE_DATE)
    sc = PL.run(prof)["scores"].sort_values("score", ascending=False).head(10)
    rows = [dict(rank=i, area_id=r.area_id, name=r.name, support_class=None, relevance=None, score=float(r.score),
                 explanation=r.why_cv, label=None) for i, r in enumerate(sc.itertuples(), 1)]
    return EngineResult("rule", "rule_v1", "accepted", supported=rows, run_meta=dict(note="keyword scores, not evidence-checked"))


def run_evidence(cv_text: str, name: str, defs: dict, regulated: dict | None = None, chat=None, cfg: dict | None = None, **_) -> EngineResult:
    from .evidence import engine as ev
    r = ev.run(cv_text, name, defs, chat=chat, cfg=cfg, regulated=regulated)
    return EngineResult(r["engine_id"], r["engine_version"], r["status"], r["supported"], r["exploration"], r["errors"],
                        [w["code"] if isinstance(w, dict) else str(w) for w in r.get("warnings", [])], r["validation_log"],
                        r.get("run_meta", {}))


REGISTRY = {"rule": run_rule, "llm_evidence": run_evidence}


def run(engine_id: str | None, cv_text: str, name: str = "Participant", **kw) -> EngineResult:
    eid = engine_id or selected_engine()
    if eid not in REGISTRY:
        return EngineResult(eid, "n/a", "failed", errors=[f"unknown engine {eid!r}"])
    return REGISTRY[eid](cv_text, name, **kw)
