from __future__ import annotations

import json
from typing import Any

from package_check_export import package_check_export_report
from package_governance import IDENTITY_FIELDS, key_to_object, package_key
from package_join_report import build_package_join_report, sample_obligation, sample_response

STATUS_BLOCKING_DIAGNOSTICS = {
    "missing-response",
    "claim-missing",
    "missing-required-test",
    "requirement-test-missing",
    "untested-requirement",
    "evidence-stale",
    "receipt-missing",
    "hidden-residual",
    "route-mismatch",
    "extra-response",
    "duplicate-response",
    "role-mismatch",
    "path-drift",
    "check-adoption-missing",
    "generated-output-boundary-missing",
    "readme-artifact-boundary-missing",
}


def _package_rows(join_rows: list[dict[str, Any]], check_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, ...], dict[str, Any]] = {}
    for row in join_rows + check_rows:
        key = package_key(row)
        if key is None:
            continue
        current = by_key.setdefault(key, {"kind": "governance.packageStatus.row.v1", **key_to_object(key), "diagnostics": [], "sources": []})
        source = row.get("kind", "unknown")
        if source not in current["sources"]:
            current["sources"].append(source)
        diagnostics = row.get("diagnostics", [])
        if isinstance(diagnostics, list):
            for diagnostic in diagnostics:
                if isinstance(diagnostic, str) and diagnostic in STATUS_BLOCKING_DIAGNOSTICS:
                    current["diagnostics"].append(diagnostic)
        if row.get("status") in {"fail", "non-green"} and not diagnostics:
            current["diagnostics"].append("non-green-without-diagnostic")
    rows: list[dict[str, Any]] = []
    for row in by_key.values():
        diagnostics = sorted(set(row["diagnostics"]))
        rows.append({**row, "diagnostics": diagnostics, "sources": sorted(row["sources"]), "status": "green" if not diagnostics else "non-green"})
    return sorted(rows, key=lambda row: tuple(row[field] for field in IDENTITY_FIELDS))


def build_package_status_report(join_rows: list[dict[str, Any]], check_rows: list[dict[str, Any]]) -> dict[str, Any]:
    package_rows = _package_rows(join_rows, check_rows)
    repos: dict[str, dict[str, Any]] = {}
    for row in package_rows:
        repo = row["repo"]
        current = repos.setdefault(repo, {"repo": repo, "status": "green", "packages": 0, "nonGreenPackages": 0, "diagnostics": []})
        current["packages"] += 1
        if row["status"] != "green":
            current["status"] = "non-green"
            current["nonGreenPackages"] += 1
            current["diagnostics"].extend(row["diagnostics"])
    repo_rows = sorted(({**row, "diagnostics": sorted(set(row["diagnostics"]))} for row in repos.values()), key=lambda row: row["repo"])
    return {
        "kind": "governance.packageStatusCi.report.v1",
        "status": "fail" if any(row["status"] != "green" for row in repo_rows) else "pass",
        "nonAuthority": True,
        "repos": repo_rows,
        "packages": package_rows,
        "summary": {
            "repos": len(repo_rows),
            "greenRepos": sum(1 for row in repo_rows if row["status"] == "green"),
            "nonGreenRepos": sum(1 for row in repo_rows if row["status"] != "green"),
            "packages": len(package_rows),
            "nonGreenPackages": sum(1 for row in package_rows if row["status"] != "green"),
        },
    }


def package_status_selftest() -> None:
    obligation = sample_obligation()
    response = sample_response(obligation)
    join_report = build_package_join_report([obligation], [response])
    check_report = package_check_export_report([response])
    report = build_package_status_report(join_report["rows"], check_report["rows"])
    if report["status"] != "pass":
        raise SystemExit(json.dumps({"case": "green status", "report": report}, indent=2, sort_keys=True))

    missing_join = build_package_join_report([obligation], [])
    if build_package_status_report(missing_join["rows"], [])["status"] != "fail":
        raise SystemExit("missing response did not fail status")
    for response in [
        dict(response, tests=[]),
        dict(response, evidenceFresh=False),
        dict(response, receiptPresent=False),
        dict(response, hiddenResidual=True),
        dict(response, routeMatches=False),
        dict(response, checkAdoption=False),
    ]:
        joined = build_package_join_report([obligation], [response])
        checked = package_check_export_report([response])
        report = build_package_status_report(joined["rows"], checked["rows"])
        if report["status"] != "fail":
            raise SystemExit(json.dumps({"case": "non-green fixture", "response": response, "report": report}, indent=2, sort_keys=True))
