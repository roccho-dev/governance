#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from package_obligations.core import ContractError
from package_obligations.materialize import check_materialized, materialize

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = ROOT / "fixtures" / "adrs-package-obligations" / "v1"


def main() -> int:
    parser = argparse.ArgumentParser(description="Materialize exact package obligations from a provider-neutral ADRS source fixture.")
    parser.add_argument("command", choices=("materialize", "check"))
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        receipt = materialize(args.fixture, args.out_dir) if args.command == "materialize" else check_materialized(args.fixture, args.out_dir)
    except (ContractError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"package-obligations:{args.command}:error:{exc}")
        return 1
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True) if args.json else f"package-obligations:{args.command}:pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
