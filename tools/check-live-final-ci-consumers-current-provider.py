#!/usr/bin/env python3
from pathlib import Path
import runpy

runpy.run_path(
    str(Path(__file__).resolve().with_name("check-live-final-ci-consumers-provider.py")),
    run_name="__main__",
)
