#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import package_contract_port_common as _common  # noqa: E402
from tools.package_contract_port_common import *  # noqa: F401,F403,E402
from tools.package_contract_port_verify import verify_bundle  # noqa: F401,E402
from tools.package_contract_port_cli import main, produce_bundle  # noqa: F401,E402

# Existing destructive tests replace this module's TARGET_DIR. Keep that test
# seam while the implementation lives in the smaller common module.
TARGET_DIR = _common.TARGET_DIR


def load_target(target_id):
    _common.TARGET_DIR = TARGET_DIR
    return _common.load_target(target_id)


def discover_targets():
    _common.TARGET_DIR = TARGET_DIR
    return _common.discover_targets()


if __name__ == "__main__":
    raise SystemExit(main())
