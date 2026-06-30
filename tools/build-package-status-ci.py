#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from package_governance import read_jsonl, write_json
from package_status_ci import build_package_status_report, package_status_selftest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build repo/package status CI report from package evidence.")
    parser.add_argument("command", nargs="?", choices=["build", "selftest"], default="build")
    parser.add_argument("--join-rows", type=Path)
    parser.add_argument("--check-rows", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    if args.command == "selftest":
        package_status_selftest()
        print(json.dumps({"kind": "governance.packageStatusCi.selftest.v1", "status": "pass"}, sort_keys=True))
        return 0
    if args.join_rows is None or args.check_rows is None:
        parser.error("build requires --join-rows and --check-rows")
    report = build_package_status_report(read_jsonl(args.join_rows), read_jsonl(args.check_rows))
    if args.report:
        write_json(args.report, report)
    else:
        print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 1 if report["status"] == "fail" else 0


if __name__ == "__main__":
    sys.exit(main())
