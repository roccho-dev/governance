#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from package_governance import parse_package_inputs, parser_selftest, read_jsonl, write_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check package obligation and response parser fixtures.")
    parser.add_argument("command", nargs="?", choices=["check", "selftest"], default="check")
    parser.add_argument("--universes", type=Path)
    parser.add_argument("--obligations", type=Path)
    parser.add_argument("--responses", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)

    if args.command == "selftest":
        parser_selftest()
        print(json.dumps({"kind": "governance.packageParser.selftest.v1", "status": "pass"}, sort_keys=True))
        return 0

    missing = [name for name in ("universes", "obligations", "responses") if getattr(args, name) is None]
    if missing:
        parser.error("check requires --" + ", --".join(missing))

    report = parse_package_inputs(read_jsonl(args.universes), read_jsonl(args.obligations), read_jsonl(args.responses))
    if args.report:
        write_json(args.report, report)
    else:
        print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 1 if report["status"] == "fail" else 0


if __name__ == "__main__":
    sys.exit(main())
