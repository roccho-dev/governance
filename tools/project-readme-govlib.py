#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

REQUIRED_SLOTS = [
    "Purpose",
    "Authority boundary",
    "Inputs",
    "Outputs / artifacts",
    "Checks",
    "Ownership / handoff",
]


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    out = Path("$TMPDIR/readme-govlib")
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "readme.policy.capsule.json", {"kind": "governance.readmePolicyCapsule.v1", "required_slots": REQUIRED_SLOTS})
    write_json(out / "repo.explain.model.json", {"kind": "governance.repoExplainModel.v1", "repo": "fixture"})
    (out / "diagnostics.jsonl").write_text("", encoding="utf-8")
    (out / "source-closure.jsonl").write_text(json.dumps({"kind": "governance.sourceClosure.v1", "source": "fixture"}) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
