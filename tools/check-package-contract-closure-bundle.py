#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.package_contract_port_common import *  # noqa: F401,F403,E402
from tools.package_contract_port_verify import verify_bundle  # noqa: F401,E402
from tools.package_contract_port_cli import main, produce_bundle  # noqa: F401,E402

if __name__ == "__main__":
    raise SystemExit(main())
