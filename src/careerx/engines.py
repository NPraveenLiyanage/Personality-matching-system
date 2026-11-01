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
LABELS = {"rule": "Rule-based engine (keyword scoring)", "llm_evidence": "Evidence-first AI pipeline (prompted model, not fine-tuned)",
          "final": "Two-step pipeline: CV evidence, then PersonaMap work-style fit (prompted model, not fine-tuned)"}
MAX_FIT_SUPPORTED, MAX_FIT_EXPLORATION = 6, 3             # caps the size and cost of the fit call


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
    fit: dict = field(default_factory=dict)               # Step 2: work-style fit per area; empty for engines without it

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


def run_evidence(cv_text: str, name: str, defs: dict, regulated: dict | None = None, chat=None, cfg: dict | None = None,
                 policy: str = "v2", hide: list[str] | None = None, mask_orgs: bool = False, **_) -> EngineResult:
    from .evidence import engine as ev
    r = ev.run(cv_text, name, defs, chat=chat, cfg=cfg, regulated=regulated, policy=policy, hide=hide, mask_orgs=mask_orgs)
    return EngineResult(r["engine_id"], r["engine_version"], r["status"], r["supported"], r["exploration"], r["errors"],
                        [w["code"] if isinstance(w, dict) else str(w) for w in r.get("warnings", [])], r["validation_log"],
                        r.get("run_meta", {}))


def cache_key(cv_text: str, name: str, pm, policy: str, hide, mask_orgs: bool, cfg: dict | None) -> str:
    """Digest of everything that decides the answer. Only the digest is kept, never the text."""
    import hashlib
    from .evidence import assess, extract, fit as ev_fit
    c = cfg or {}
    parts = [cv_text, name or "", pm.report_text() if pm is not None else "", policy, "|".join(hide or []), str(mask_orgs),
             str(c.get("model")), str(c.get("provider")), extract.PROMPT_VERSION, assess.PROMPT_VERSION, ev_fit.PROMPT_VERSION]
    return hashlib.sha256("".join(parts).encode("utf-8")).hexdigest()


def run_final(cv_text: str, name: str, defs: dict, personamap_text: str | None = None, personamap=None, regulated: dict | None = None,
              chat=None, cfg: dict | None = None, policy: str = "v2", hide: list[str] | None = None, mask_orgs: bool = False,
              cache: dict | None = None, **_) -> EngineResult:
    """Step 1 (CV evidence) decides which areas are supported. Step 2 (PersonaMap) only adds a separate work-style fit for those
    areas; it never changes which areas are supported or their order. A failed Step 2 leaves Step 1 intact and says so."""
    from . import cost, personamap as PMAP
    from .evidence import fit as ev_fit
    pm = personamap or (PMAP.parse_text(personamap_text) if personamap_text else None)
    key = cache_key(cv_text, name, pm, policy, hide, mask_orgs, cfg) if cache is not None else None
    if key and key in cache and cache[key].status != "failed":        # a repeat of the same inputs costs nothing
        hit = cache[key]
        hit.run_meta["cache_hit"] = True
        return hit
    r = run_evidence(cv_text, name, defs, regulated, chat, cfg, policy, hide, mask_orgs)
    r.engine_id, r.engine_version = "final", f"{r.engine_version}+{ev_fit.PROMPT_VERSION}"
    if pm is None:
        r.warnings.append("no_personamap: the work-style fit was not run")
    else:
        cands = (r.supported[:MAX_FIT_SUPPORTED] + r.exploration[:MAX_FIT_EXPLORATION]) if r.status != "failed" else []
        if not cands:
            r.warnings.append("fit_skipped: no candidate areas from the CV step")
        else:
            f = ev_fit.run_fit(pm, cands, defs, chat=chat, cfg=cfg)
            r.fit = f
            r.run_meta["fit"] = f["run_meta"]
            if f["status"] == "failed":
                r.warnings.append("fit_failed: " + "; ".join(f["errors"]))
    r.run_meta["totals"] = cost.totals(r.run_meta)
    if key and r.status != "failed":
        cache[key] = r
    return r


REGISTRY = {"rule": run_rule, "llm_evidence": run_evidence, "final": run_final}


def run(engine_id: str | None, cv_text: str, name: str = "Participant", **kw) -> EngineResult:
    eid = engine_id or selected_engine()
    if eid not in REGISTRY:
        return EngineResult(eid, "n/a", "failed", errors=[f"unknown engine {eid!r}"])
    return REGISTRY[eid](cv_text, name, **kw)
