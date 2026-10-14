#!/usr/bin/env python3
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.contract_632_topology_view import canonical_final_topology

with canonical_final_topology(ROOT):
    runpy.run_path(str(Path(__file__).with_name("check-package-ci-final-role-demotion-core.py")), run_name="__main__")
