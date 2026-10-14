#!/usr/bin/env python3
from pathlib import Path
import os
import runpy

root = Path(__file__).resolve().parents[1]
proof = root / ".github/workflows/contract-632-phase4.yml"
hidden = root / ".github/contract-632-phase4.proof.yml"
if hidden.exists():
    raise SystemExit("phase4-proof-hidden-path-exists")
if proof.exists():
    hidden.parent.mkdir(parents=True, exist_ok=True)
    os.replace(proof, hidden)
try:
    runpy.run_path(str(Path(__file__).with_name("check-package-ci-final-role-demotion-core.py")), run_name="__main__")
finally:
    if hidden.exists():
        os.replace(hidden, proof)
