#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from package_check_export import package_check_export_report, package_check_export_selftest
from package_governance import read_jsonl, write_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run exported non-authority package checks for feature repositories.")
    parser.add_argument("command", nargs="?", choices=["check", "selftest"], default="check")
    parser.add_argument("--responses", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    if args.command == "selftest":
        package_check_export_selftest()
        print(json.dumps({"kind": "governance.packageCheckExport.selftest.v1", "status": "pass"}, sort_keys=True))
        return 0
    if args.responses is None:
        parser.error("check requires --responses")
    report = package_check_export_report(read_jsonl(args.responses))
    if args.report:
        write_json(args.report, report)
    else:
        print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 1 if report["status"] == "fail" else 0


if __name__ == "__main__":
    sys.exit(main())
