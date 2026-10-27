"""Manual extraction-quality audit sheet: one row per evidence record, reviewer columns left blank."""
from __future__ import annotations

import csv
from pathlib import Path

COLUMNS = ["case_id", "evidence_id", "passage_id", "section", "evidence_type", "quote", "role", "contribution",
           "domain_context", "status", "changes", "flags",
           "reviewer_quote_ok", "reviewer_attribution_ok", "reviewer_domain_not_profession_ok", "reviewer_notes"]


def audit_rows(case_id: str, result) -> list[dict]:
    return [dict(case_id=case_id, evidence_id=r.evidence_id, passage_id=r.passage_id, section=r.section,
                 evidence_type=r.evidence_type, quote=r.quote, role=r.role or "", contribution=r.contribution,
                 domain_context=r.domain_context or "", status=r.status, changes="; ".join(r.changes),
                 flags="; ".join(r.flags)) for r in result.records]


def write_audit_csv(path, rows: list[dict]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, restval="")
        w.writeheader()
        w.writerows(rows)
