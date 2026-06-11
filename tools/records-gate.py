#!/usr/bin/env python3
"""records-gate: declarative validation gate over governance records.

Pipeline (rc semantics):
  1. CUE schema vet   — policy/cue/*.cue applied per record file (shape).
  2. DuckDB asserts   — policy/sql/assertions/*.sql; every assertion SELECT
                        returns violation rows, 0 rows == pass.
  rc=0 iff every schema vets clean AND every assertion returns 0 rows;
  otherwise all violations are listed and rc=1.

--report PATH additionally writes a NON-blocking obligation-debt JSON
(visibility only; never affects rc):
  - accepted-without-feat-evidence : accepted contracts with no promotable
    feat build evidence row (records/feat/build-evidence.v1.jsonl).
  - membership-member-not-accepted : catalog members whose contract status is
    not 'accepted' (stricter target state of the membership assertion).
  - catalog-field-gap              : membership contracts whose rawDefinition
    leaves a nominally-required catalog field null/missing (the 3 fields with
    known historical gaps; see catalog-required-fields-nonnull.sql).

policy/ is resolved relative to this script (tool and policy version move
together); records are resolved under --root.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys

POLICY_DIR_NAME = "policy"

# (records file relative to root, cue file, cue definition, required)
SCHEMA_BINDINGS = [
    ("records/specs/package-contract.v1.jsonl", "package-contract.cue", "#PackageContract", True),
    ("records/specs/repo-placement.v1.jsonl", "repo-placement.cue", "#RepoPlacement", True),
    ("records/specs/catalog-membership.v1.jsonl", "catalog-membership.cue", "#CatalogMembership", True),
    ("records/specs/dependency-edge.v1.jsonl", "dependency-edge.cue", "#DependencyEdge", True),
    ("records/decisions/specsless-final-cutover-acceptance.v1.jsonl", "decisions.cue", "#SpecslessFinalCutoverAcceptance", True),
    ("records/decisions/specs-main-proposal-admission.v1.jsonl", "decisions.cue", "#SpecsMainProposalAdmissionDecision", True),
    ("records/feat/breaking-change-evidence.v1.jsonl", "feat-evidence.cue", "#BreakingChangeEvidence", True),
    # adrs typed-ladder files live in the adrs repo; vetted when present.
    ("records/raw/adr.v1.jsonl", "adr-ladder.cue", "#AdrRaw", False),
    ("records/promoted/adr.v1.jsonl", "adr-ladder.cue", "#AdrPromoted", False),
    ("records/relations/adr-promotion.v1.jsonl", "adr-ladder.cue", "#AdrPromotionRelation", False),
]

# catalog fields with known historical rawDefinition gaps (tracked as debt,
# see policy/sql/assertions/catalog-required-fields-nonnull.sql).
DEBT_CATALOG_FIELDS = ["dependencyUse", "publicInterface", "checkPackageContract"]


def read_jsonl(path: pathlib.Path) -> list[dict]:
    rows = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"records-gate: unparseable JSONL {path}:{i}: {exc}")
    return rows


def run_cue_vet(cue_bin: str, root: pathlib.Path, policy: pathlib.Path) -> list[dict]:
    violations = []
    for rel, cue_file, definition, required in SCHEMA_BINDINGS:
        data = root / rel
        schema = policy / "cue" / cue_file
        if not data.is_file():
            if required:
                violations.append({"stage": "cue", "rule": "required-record-file-missing",
                                   "target": rel, "detail": str(data)})
            continue
        proc = subprocess.run(
            [cue_bin, "vet", "-d", definition, str(schema), str(data)],
            capture_output=True, text=True)
        if proc.returncode != 0:
            violations.append({"stage": "cue", "rule": "schema-vet-failed", "target": rel,
                               "detail": (proc.stderr or proc.stdout).strip()})
    return violations


def run_assertions(duckdb_bin: str, root: pathlib.Path, policy: pathlib.Path) -> tuple[list[dict], list[tuple[str, int]]]:
    violations, summary = [], []
    sql_dir = policy / "sql" / "assertions"
    sql_files = sorted(sql_dir.glob("*.sql"))
    if not sql_files:
        raise SystemExit(f"records-gate: no assertion SQL found under {sql_dir}")
    for sql_path in sql_files:
        script = f"SET VARIABLE root = '{root}';\n" + sql_path.read_text(encoding="utf-8")
        proc = subprocess.run([duckdb_bin, "-json", "-c", script],
                              capture_output=True, text=True)
        if proc.returncode != 0:
            violations.append({"stage": "duckdb", "rule": "assertion-execution-failed",
                               "target": sql_path.name, "detail": proc.stderr.strip()})
            summary.append((sql_path.name, -1))
            continue
        out = proc.stdout.strip()
        rows = json.loads(out) if out else []
        summary.append((sql_path.name, len(rows)))
        for row in rows:
            violations.append({"stage": "duckdb", "target": sql_path.name, **row})
    return violations, summary


def build_obligation_debt_report(root: pathlib.Path) -> dict:
    contracts = read_jsonl(root / "records/specs/package-contract.v1.jsonl")
    members = {r["packageId"]
               for r in read_jsonl(root / "records/specs/catalog-membership.v1.jsonl")
               if r.get("inSpecPackages") is True}
    evidence_path = root / "records/feat/build-evidence.v1.jsonl"
    evidenced = set()
    if evidence_path.is_file():
        for row in read_jsonl(evidence_path):
            if row.get("promotableBuildEvidence") is True:
                evidenced.add(row.get("packageId"))

    accepted = [r["packageId"] for r in contracts if r.get("status") == "accepted"]
    accepted_without_evidence = sorted(p for p in accepted if p not in evidenced)

    by_pid = {r["packageId"]: r for r in contracts}
    not_accepted_members = sorted(
        [{"packageId": m, "status": by_pid[m].get("status")}
         for m in members if m in by_pid and by_pid[m].get("status") != "accepted"],
        key=lambda d: d["packageId"])

    field_gaps = []
    for field in DEBT_CATALOG_FIELDS:
        pids = sorted(
            r["packageId"] for r in contracts
            if r["packageId"] in members
            and isinstance(r.get("source", {}).get("rawDefinition"), dict)
            and r["source"]["rawDefinition"].get(field) is None)
        if pids:
            field_gaps.append({"field": field, "count": len(pids), "packageIds": pids})

    debts = []
    debts.append({"debtClass": "accepted-without-feat-evidence",
                  "count": len(accepted_without_evidence),
                  "packageIds": accepted_without_evidence})
    debts.append({"debtClass": "membership-member-not-accepted",
                  "count": len(not_accepted_members),
                  "members": not_accepted_members})
    debts.append({"debtClass": "catalog-field-gap",
                  "count": sum(g["count"] for g in field_gaps),
                  "fields": field_gaps})
    return {
        "kind": "governance.obligationDebtReport.v1",
        "blocking": False,
        "generatedBy": "tools/records-gate.py",
        "policy": "policy/promotion-policy.md",
        "counts": {d["debtClass"]: d["count"] for d in debts},
        "debts": debts,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="cue + duckdb validation gate over governance records")
    ap.add_argument("--root", default=".", help="governance repo root holding records/")
    ap.add_argument("--report", help="write NON-blocking obligation-debt JSON to this path")
    ap.add_argument("--cue-bin", default=shutil.which("cue") or "cue")
    ap.add_argument("--duckdb-bin", default=shutil.which("duckdb") or "duckdb")
    args = ap.parse_args()

    root = pathlib.Path(args.root).resolve()
    policy = pathlib.Path(__file__).resolve().parent.parent / POLICY_DIR_NAME
    if not (policy / "cue").is_dir():
        raise SystemExit(f"records-gate: policy dir missing: {policy}")

    violations = run_cue_vet(args.cue_bin, root, policy)
    assertion_violations, summary = run_assertions(args.duckdb_bin, root, policy)
    violations.extend(assertion_violations)

    schema_count = sum(1 for rel, *_ in SCHEMA_BINDINGS if (root / rel).is_file())
    for name, count in summary:
        status = "pass" if count == 0 else ("error" if count < 0 else f"violations={count}")
        print(f"records-gate: assertion {name}: {status}")
    print(f"records-gate: schemas-vetted={schema_count} assertions={len(summary)} "
          f"violations={len(violations)}")

    if args.report:
        report_path = pathlib.Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report = build_obligation_debt_report(root)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                               encoding="utf-8")
        print(f"records-gate: obligation-debt report (non-blocking) -> {report_path} "
              f"counts={report['counts']}")

    if violations:
        print("records-gate: FAIL", file=sys.stderr)
        for v in violations:
            print(json.dumps(v, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
    print("records-gate: PASS")


if __name__ == "__main__":
    main()
