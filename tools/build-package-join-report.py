#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from package_governance import read_jsonl, write_json
from package_join_report import build_package_join_report, join_report_selftest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a deterministic package obligation/response join report.")
    parser.add_argument("command", nargs="?", choices=["build", "selftest"], default="build")
    parser.add_argument("--obligations", type=Path)
    parser.add_argument("--responses", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)

    if args.command == "selftest":
        join_report_selftest()
        print(json.dumps({"kind": "governance.packageJoin.selftest.v1", "status": "pass"}, sort_keys=True))
        return 0
    if args.obligations is None or args.responses is None:
        parser.error("build requires --obligations and --responses")
    report = build_package_join_report(read_jsonl(args.obligations), read_jsonl(args.responses))
    if args.report:
        write_json(args.report, report)
    else:
        print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
