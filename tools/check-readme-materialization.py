#!/usr/bin/env python3
"""Local README materialization checker for governance-owned downstream adoption.

This tool is intentionally narrow. It checks that a generated README artifact
matches the committed README for repos that have opted into generated mode, or
emits an explicit residual for repos that are not ready yet. It does not make
README content authority and it does not mutate files.
"""
from __future__ import annotations

import argparse
import difflib
import json
import tempfile
from hashlib import sha256
from pathlib import Path
from typing import Any

RECEIPT_KIND = "readmeMaterializationReceipt.v1"
RESIDUAL_KIND = "readmeMaterializationResidual.v1"
FINDING_KIND = "readmeMaterializationFinding.v1"
SELFTEST_KIND = "readmeMaterializationChecker.selftest.v1"
BOUNDARY = "local README materialization evidence only; no README authority, no final join authority, no branch protection mutation"


def digest_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical(value) + "\n", encoding="utf-8")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def materialization_receipt(
    *,
    repo_id: str,
    mode: str,
    artifact_readme: Path,
    committed_readme: Path,
    producer_repo: str,
    generated_by: str,
) -> tuple[int, dict[str, Any]]:
    if mode != "generated":
        return 2, {
            "kind": FINDING_KIND,
            "repoId": repo_id,
            "status": "fail",
            "mode": mode,
            "diagnosticClass": "invalid-readme-materialization-mode",
            "expected": "mode=generated for mkReadmeMaterializedCheck",
            "actual": f"mode={mode}",
            "nextAction": "use mkReadmeMaterializationResidual for non-generated or not-ready repos",
            "authority": False,
            "nonAuthority": True,
            "boundary": BOUNDARY,
        }

    if not artifact_readme.is_file():
        return 2, {
            "kind": FINDING_KIND,
            "repoId": repo_id,
            "status": "fail",
            "mode": mode,
            "diagnosticClass": "missing-generated-readme-artifact",
            "expected": "generated README artifact README.md",
            "actual": str(artifact_readme),
            "nextAction": "build the repo readme-artifact derivation before running the materialization check",
            "authority": False,
            "nonAuthority": True,
            "boundary": BOUNDARY,
        }
    if not committed_readme.is_file():
        return 2, {
            "kind": FINDING_KIND,
            "repoId": repo_id,
            "status": "fail",
            "mode": mode,
            "diagnosticClass": "missing-committed-readme",
            "expected": "committed README.md",
            "actual": str(committed_readme),
            "nextAction": "pass the repository README.md path into mkReadmeMaterializedCheck",
            "authority": False,
            "nonAuthority": True,
            "boundary": BOUNDARY,
        }

    artifact_digest = digest_file(artifact_readme)
    committed_digest = digest_file(committed_readme)

    if artifact_digest != committed_digest or artifact_readme.read_bytes() != committed_readme.read_bytes():
        diff = "".join(
            difflib.unified_diff(
                read_text(artifact_readme).splitlines(keepends=True),
                read_text(committed_readme).splitlines(keepends=True),
                fromfile="generated README artifact",
                tofile="committed README.md",
            )
        )
        return 1, {
            "kind": FINDING_KIND,
            "repoId": repo_id,
            "status": "fail",
            "mode": "generated",
            "diagnosticClass": "readme-materialization-drift",
            "expected": "generated README artifact README.md",
            "actual": "committed README.md",
            "artifactDigest": artifact_digest,
            "committedDigest": committed_digest,
            "delta": diff,
            "nextAction": "materialize README.md from the generated artifact or use mkReadmeMaterializationResidual until generated mode is ready",
            "authority": False,
            "nonAuthority": True,
            "boundary": BOUNDARY,
        }

    return 0, {
        "kind": RECEIPT_KIND,
        "repoId": repo_id,
        "status": "pass",
        "mode": "generated",
        "artifactDigest": artifact_digest,
        "committedDigest": committed_digest,
        "producerRepo": producer_repo,
        "generatedBy": generated_by,
        "authority": False,
        "nonAuthority": True,
        "boundary": BOUNDARY,
    }


def residual(
    *,
    repo_id: str,
    mode: str,
    owner: str,
    reason: str,
    next_action: str,
    return_condition: str,
    expires: str,
) -> dict[str, Any]:
    return {
        "kind": RESIDUAL_KIND,
        "repoId": repo_id,
        "status": "residual",
        "mode": mode,
        "owner": owner,
        "reason": reason,
        "nextAction": next_action,
        "returnCondition": return_condition,
        "expires": expires,
        "authority": False,
        "nonAuthority": True,
        "boundary": BOUNDARY,
    }


def run_check(args: argparse.Namespace) -> int:
    code, row = materialization_receipt(
        repo_id=args.repo_id,
        mode=args.mode,
        artifact_readme=args.artifact_readme,
        committed_readme=args.committed_readme,
        producer_repo=args.producer_repo,
        generated_by=args.generated_by,
    )
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    if code == 0:
        write_json(out / "receipt.json", row)
        (out / "pass").write_text("", encoding="utf-8")
    else:
        write_json(out / "finding.json", row)
    print(canonical(row))
    return code


def run_residual(args: argparse.Namespace) -> int:
    row = residual(
        repo_id=args.repo_id,
        mode=args.mode,
        owner=args.owner,
        reason=args.reason,
        next_action=args.next_action,
        return_condition=args.return_condition,
        expires=args.expires,
    )
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "residual.json", row)
    (out / "pass").write_text("", encoding="utf-8")
    print(canonical(row))
    return 0


def selftest() -> int:
    cases: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="readme-materialization-") as raw:
        root = Path(raw)
        generated = root / "generated" / "README.md"
        committed = root / "committed" / "README.md"
        generated.parent.mkdir(parents=True)
        committed.parent.mkdir(parents=True)
        generated.write_text("# Title\n\nsame\n", encoding="utf-8")
        committed.write_text("# Title\n\nsame\n", encoding="utf-8")
        code, row = materialization_receipt(
            repo_id="fixture/pass",
            mode="generated",
            artifact_readme=generated,
            committed_readme=committed,
            producer_repo="roccho-dev/governance",
            generated_by="selftest",
        )
        assert code == 0, row
        assert row["kind"] == RECEIPT_KIND and row["status"] == "pass", row
        cases.append({"name": "generated-pass", "status": "pass", "kind": row["kind"]})

        committed.write_text("# Title\n\ndrift\n", encoding="utf-8")
        code, row = materialization_receipt(
            repo_id="fixture/drift",
            mode="generated",
            artifact_readme=generated,
            committed_readme=committed,
            producer_repo="roccho-dev/governance",
            generated_by="selftest",
        )
        assert code == 1, row
        assert row["kind"] == FINDING_KIND
        assert row["diagnosticClass"] == "readme-materialization-drift"
        assert "delta" in row and "drift" in row["delta"]
        cases.append({"name": "generated-drift", "status": "fail", "kind": row["kind"]})

        code, row = materialization_receipt(
            repo_id="fixture/manual-wrong-surface",
            mode="manual",
            artifact_readme=generated,
            committed_readme=committed,
            producer_repo="roccho-dev/governance",
            generated_by="selftest",
        )
        assert code == 2, row
        assert row["diagnosticClass"] == "invalid-readme-materialization-mode"
        cases.append({"name": "wrong-surface", "status": "fail", "kind": row["kind"]})

        row = residual(
            repo_id="fixture/residual",
            mode="manual",
            owner="governance#144",
            reason="fixture repo is not in generated README mode",
            next_action="switch to generated mode when readme-artifact exists",
            return_condition="readme-artifact and committed README are byte-identical",
            expires="2026-08-31",
        )
        assert row["kind"] == RESIDUAL_KIND
        assert row["owner"] == "governance#144"
        assert row["nextAction"]
        cases.append({"name": "residual", "status": "residual", "kind": row["kind"]})

    print(canonical({"kind": SELFTEST_KIND, "status": "pass", "caseCount": len(cases), "cases": cases, "boundary": BOUNDARY}))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    check = sub.add_parser("check")
    check.add_argument("--repo-id", required=True)
    check.add_argument("--mode", default="generated")
    check.add_argument("--artifact-readme", type=Path, required=True)
    check.add_argument("--committed-readme", type=Path, required=True)
    check.add_argument("--out", type=Path, required=True)
    check.add_argument("--producer-repo", default="roccho-dev/governance")
    check.add_argument("--generated-by", default="nix/readme-materialization-checks.nix:mkReadmeMaterializedCheck")

    residual_cmd = sub.add_parser("residual")
    residual_cmd.add_argument("--repo-id", required=True)
    residual_cmd.add_argument("--mode", required=True)
    residual_cmd.add_argument("--owner", required=True)
    residual_cmd.add_argument("--reason", required=True)
    residual_cmd.add_argument("--next-action", required=True)
    residual_cmd.add_argument("--return-condition", required=True)
    residual_cmd.add_argument("--expires", required=True)
    residual_cmd.add_argument("--out", type=Path, required=True)

    sub.add_parser("selftest")

    args = parser.parse_args(argv)
    if args.cmd == "selftest":
        return selftest()
    if args.cmd == "check":
        return run_check(args)
    if args.cmd == "residual":
        return run_residual(args)
    raise AssertionError(args.cmd)


if __name__ == "__main__":
    raise SystemExit(main())
