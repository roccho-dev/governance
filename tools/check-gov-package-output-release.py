#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gov_release.package_output import PackageOutputError, check_archive, check_directory

DEFAULT_FIXTURE = ROOT / "fixtures" / "adrs-package-obligations" / "v1"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate exact package-obligation bytes in a gov-package-output directory or archive.")
    parser.add_argument("kind", choices=("directory", "archive"))
    parser.add_argument("--path", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        report = check_directory(args.path, args.fixture) if args.kind == "directory" else check_archive(args.path, args.fixture)
    except (PackageOutputError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"gov-package-output-release:{args.kind}:error:{exc}")
        return 1
    print(json.dumps(report, ensure_ascii=False, sort_keys=True) if args.json else f"gov-package-output-release:{args.kind}:pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
