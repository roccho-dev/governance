"""CLI adapter: decode explicit inputs, invoke core, encode outputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from repo_governance import evaluate


def load_json(path: str) -> dict[str, Any]:
    if path == "-":
        value = json.load(sys.stdin)
    else:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level JSON must be an object")
    return value


def write_outputs(out_dir: str, result: dict[str, Any]) -> None:
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    outputs = {
        "repo.contract.json": result["repoContract"],
        "package.contracts.json": result["packageContracts"],
        "violations.json": result["violations"],
        "plan.json": result["plan"],
        "provenance.json": {**result["provenance"], "resultDigest": result["resultDigest"]},
    }
    for name, value in outputs.items():
        (root / name).write_text(
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    (root / "readme.generated.md").write_text(result["readmeGenerated"], encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="repo-governance",
        description="Project and check an explicit repo snapshot against an accepted ADR bundle.",
    )
    parser.add_argument("--adr-bundle", required=True, help="accepted ADR bundle JSON path")
    parser.add_argument("--repo-snapshot", required=True, help="explicit repo snapshot JSON path")
    parser.add_argument("--out-dir", help="optional directory for projected outputs")
    parser.add_argument(
        "--output",
        choices=("summary", "json"),
        default="summary",
        help="stdout representation",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        bundle = load_json(args.adr_bundle)
        snapshot = load_json(args.repo_snapshot)
        result = evaluate(bundle, snapshot).to_dict()
        if args.out_dir:
            write_outputs(args.out_dir, result)
        if args.output == "json":
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        else:
            state = "PASS" if result["passed"] else "FAIL"
            print(
                f"repo-governance: {state} repo={result['repoContract']['repoId']} "
                f"violations={len(result['violations'])} digest={result['resultDigest']}"
            )
            for violation in result["violations"]:
                print(
                    f"[{violation['code']}] {violation['ruleId']} "
                    f"subject={violation['subject']}: {violation['detail']}",
                    file=sys.stderr,
                )
        return 0 if result["passed"] else 1
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"repo-governance: tool error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
