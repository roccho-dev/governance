from __future__ import annotations

import json
from typing import Any

from package_governance import IDENTITY_FIELDS, key_to_object, package_key, value_as_string
from package_join_report import response_has_required_test, sample_response


def _has_value(row: dict[str, Any], field: str) -> bool:
    value = row.get(field)
    if isinstance(value, str):
        return bool(value)
    if isinstance(value, bool):
        return value
    if isinstance(value, (list, dict)):
        return bool(value)
    return value is not None


def package_check_export_report(responses: list[dict[str, Any]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for index, response in enumerate(responses, 1):
        key = package_key(response)
        base = key_to_object(key) if key is not None else {"rowIndex": index}
        diagnostics: list[str] = []
        if any(value_as_string(response, field) is None for field in IDENTITY_FIELDS):
            diagnostics.append("claim-shape-invalid")
        required_test_id = value_as_string(response, "requiredTestId")
        if required_test_id is None or not response_has_required_test(response, required_test_id):
            diagnostics.append("requirement-test-missing")
        if response.get("evidenceFresh") is not True:
            diagnostics.append("evidence-stale")
        if response.get("receiptPresent") is not True and not _has_value(response, "receipt"):
            diagnostics.append("receipt-missing")
        if response.get("hiddenResidual") is True or response.get("residualsVisible") is False:
            diagnostics.append("hidden-residual")
        if response.get("routeMatches") is False:
            diagnostics.append("route-mismatch")
        if response.get("checkAdoption") is not True:
            diagnostics.append("check-adoption-missing")
        if response.get("generatedOutputBoundary") is False:
            diagnostics.append("generated-output-boundary-missing")
        if response.get("readmeArtifactBoundary") is False:
            diagnostics.append("readme-artifact-boundary-missing")
        rows.append({"kind": "governance.packageCheckExport.row.v1", **base, "status": "pass" if not diagnostics else "fail", "diagnostics": sorted(set(diagnostics)), "nonAuthority": True})
    rows = sorted(rows, key=lambda row: tuple(str(row.get(field, "")) for field in IDENTITY_FIELDS) + (str(row.get("rowIndex", "")),))
    return {
        "kind": "governance.packageCheckExport.report.v1",
        "status": "fail" if any(row["status"] == "fail" for row in rows) else "pass",
        "nonAuthority": True,
        "exportedChecks": ["claim-shape", "requirement-to-test", "evidence-freshness", "receipt-residual", "readme-artifact-boundary", "generated-output-boundary", "check-adoption"],
        "rows": rows,
        "summary": {"rows": len(rows), "pass": sum(1 for row in rows if row["status"] == "pass"), "fail": sum(1 for row in rows if row["status"] == "fail")},
    }


def package_check_export_selftest() -> None:
    valid = sample_response()
    if package_check_export_report([valid])["status"] != "pass":
        raise SystemExit("valid package check export failed")
    cases = [
        ("claim shape", {"packageId": ""}, "claim-shape-invalid"),
        ("requirement test", {"tests": []}, "requirement-test-missing"),
        ("evidence freshness", {"evidenceFresh": False}, "evidence-stale"),
        ("receipt", {"receiptPresent": False}, "receipt-missing"),
        ("hidden residual", {"hiddenResidual": True}, "hidden-residual"),
        ("route", {"routeMatches": False}, "route-mismatch"),
        ("generated output boundary", {"generatedOutputBoundary": False}, "generated-output-boundary-missing"),
        ("readme boundary", {"readmeArtifactBoundary": False}, "readme-artifact-boundary-missing"),
        ("adoption", {"checkAdoption": False}, "check-adoption-missing"),
    ]
    for name, patch, expected in cases:
        report = package_check_export_report([dict(valid, **patch)])
        codes = {code for row in report["rows"] for code in row["diagnostics"]}
        if expected not in codes:
            raise SystemExit(json.dumps({"case": name, "expected": expected, "report": report}, indent=2, sort_keys=True))
