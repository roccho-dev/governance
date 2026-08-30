#!/usr/bin/env python3
from __future__ import annotations

import argparse
import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.package_obligations.join import JoinError, join_packet


def selftest() -> dict[str, object]:
    suite = unittest.defaultTestLoader.loadTestsFromName("tools.package_obligations.tests.test_join")
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=1).run(suite)
    if not result.wasSuccessful():
        raise JoinError("selftest-failed:" + stream.getvalue().replace("\n", " | "))
    return {
        "kind": "governance.packageObligationExecutionJoinSelftest.v1",
        "status": "pass",
        "testsRun": result.testsRun,
        "destructiveCases": 7,
        "authority": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", choices=("check", "selftest"), default="selftest")
    parser.add_argument("--obligations", type=Path)
    parser.add_argument("--ops-output", type=Path)
    parser.add_argument("--expected-ops-commit")
    parser.add_argument("--expected-release-digest")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "selftest":
            report = selftest()
        else:
            if args.obligations is None or args.ops_output is None:
                parser.error("check requires --obligations and --ops-output")
            report = join_packet(
                args.obligations,
                args.ops_output,
                expected_ops_commit=args.expected_ops_commit,
                expected_release_digest=args.expected_release_digest,
            )
    except (JoinError, OSError, ValueError, json.JSONDecodeError) as exc:
        report = {"kind": "governance.packageObligationExecutionJoin.v1", "status": "fail", "error": str(exc), "authority": False}
        print(json.dumps(report, sort_keys=True) if args.json else f"package-obligation-execution-join:fail:{exc}")
        return 1
    print(json.dumps(report, sort_keys=True) if args.json else f"package-obligation-execution-join:{report['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
