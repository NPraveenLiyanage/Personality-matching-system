"""Build demo/index.html: a single self-contained page showing the recorded pipeline outputs.

Reads data/demo/pilot_examples.json (real recorded runs on invented CVs) and inlines it into demo/template.html.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "demo" / "pilot_examples.json"
TEMPLATE = ROOT / "demo" / "template.html"
OUT = ROOT / "demo" / "index.html"


def main() -> None:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8")
    assert html.count("__DATA__") == 1
    OUT.write_text(html.replace("__DATA__", payload), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB, {len(data['examples'])} examples)")


if __name__ == "__main__":
    main()
