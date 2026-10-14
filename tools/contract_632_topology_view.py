#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path

PROOF_WORKFLOW = ".github/workflows/contract-632-phase4.yml"


@contextmanager
def canonical_final_topology(root: Path):
    root = root.resolve()
    proof = root / PROOF_WORKFLOW
    hidden = root / ".github/contract-632-phase4.proof.yml"
    intent = root / "ci.intent.v1.jsonl"
    if hidden.exists():
        raise RuntimeError("phase4-proof-hidden-path-exists")
    original_intent = intent.read_bytes()
    rows = [line for line in original_intent.decode().splitlines() if line]
    proof_rows = [line for line in rows if json.loads(line).get("path") == PROOF_WORKFLOW]
    if len(proof_rows) != 1:
        raise RuntimeError("phase4-proof-intent-cardinality")
    moved = False
    try:
        if proof.exists():
            hidden.parent.mkdir(parents=True, exist_ok=True)
            os.replace(proof, hidden)
            moved = True
        filtered = [line for line in rows if json.loads(line).get("path") != PROOF_WORKFLOW]
        intent.write_text("\n".join(filtered) + "\n", encoding="utf-8")
        yield
    finally:
        intent.write_bytes(original_intent)
        if moved and hidden.exists():
            os.replace(hidden, proof)
