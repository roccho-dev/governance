#!/usr/bin/env python3
"""records-gate: NON-blocking obligation-debt REPORT over governance records.

Since C1 (CUE unification) the BLOCKING gate is `cue vet` only, driven by
the declarations in policy/interface.json:
  - per-file schema vet : cue vet policy/cue/*.cue <file> -d '<def>'
  - relational vet      : grouped jsonl ledgers bundled into one labeled JSON
                          and vetted against policy/cue/relational.cue #All
(see flake.nix checks.<system>.records-gate for the generic plumbing).

This tool is REPORT-ONLY — demoted from the former blocking cue+sql flow:
  --report PATH writes the obligation-debt JSON (shape/content unchanged from
  the pre-C1 report; kind governance.obligationDebtReport.v1):
    - accepted-without-feat-evidence : accepted contracts with no promotable
      feat build evidence row (records/feat/build-evidence.v1.jsonl).
    - membership-member-not-accepted : catalog members whose contract status
      is not 'accepted' (stricter target state of the membership constraint).
    - catalog-field-gap              : membership contracts whose
      rawDefinition leaves a nominally-required catalog field null/missing
      (the 3 fields with known historical gaps).
  Additionally the DuckDB queries under policy/sql/report/ (the former
  blocking assertions, retained as the report-side relational view) are run
  informationally; their violation counts are printed but NEVER gate (the
  blocking equivalents live in policy/cue/relational.cue #All).

rc=0 unless the tool itself fails (unparseable records, missing files,
query execution error) — violation rows found by the report queries do not
affect rc.

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

# catalog fields with known historical rawDefinition gaps (tracked as debt,
# see policy/sql/report/catalog-required-fields-nonnull.sql and
# policy/cue/relational.cue).
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


def run_report_queries(duckdb_bin: str, root: pathlib.Path, policy: pathlib.Path) -> list[tuple[str, int]]:
    """Run the report-side DuckDB queries (former blocking assertions).

    Informational only: returns (query, violation-row-count) pairs; a query
    EXECUTION failure aborts (tool error), but violation rows never do.
    """
    summary = []
    sql_dir = policy / "sql" / "report"
    sql_files = sorted(sql_dir.glob("*.sql"))
    if not sql_files:
        raise SystemExit(f"records-gate: no report SQL found under {sql_dir}")
    for sql_path in sql_files:
        script = f"SET VARIABLE root = '{root}';\n" + sql_path.read_text(encoding="utf-8")
        proc = subprocess.run([duckdb_bin, "-json", "-c", script],
                              capture_output=True, text=True)
        if proc.returncode != 0:
            raise SystemExit(f"records-gate: report query failed {sql_path.name}: "
                             f"{proc.stderr.strip()}")
        out = proc.stdout.strip()
        rows = json.loads(out) if out else []
        summary.append((sql_path.name, len(rows)))
        for row in rows:
            print(f"records-gate: report-query violation {sql_path.name}: "
                  f"{json.dumps(row, ensure_ascii=False)}")
    return summary


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
    ap = argparse.ArgumentParser(
        description="NON-blocking obligation-debt report over governance records "
                    "(the blocking gate is cue vet; see policy/interface.json)")
    ap.add_argument("--root", default=".", help="governance repo root holding records/")
    ap.add_argument("--report", required=True,
                    help="write the obligation-debt JSON to this path")
    ap.add_argument("--duckdb-bin", default=shutil.which("duckdb") or "duckdb")
    args = ap.parse_args()

    root = pathlib.Path(args.root).resolve()
    policy = pathlib.Path(__file__).resolve().parent.parent / POLICY_DIR_NAME
    if not (policy / "sql" / "report").is_dir():
        raise SystemExit(f"records-gate: policy report dir missing: {policy}/sql/report")

    summary = run_report_queries(args.duckdb_bin, root, policy)
    for name, count in summary:
        status = "pass" if count == 0 else f"violations={count}"
        print(f"records-gate: report-query {name}: {status}")

    report_path = pathlib.Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = build_obligation_debt_report(root)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(f"records-gate: obligation-debt report (non-blocking) -> {report_path} "
          f"counts={report['counts']}")
    print("records-gate: REPORT DONE (non-blocking; blocking gate = cue vet)")


if __name__ == "__main__":
    main()
