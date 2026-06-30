from __future__ import annotations

import json
from collections import Counter, defaultdict
from typing import Any

from package_governance import IDENTITY_FIELDS, key_to_object, package_key, value_as_string


def sample_obligation() -> dict[str, Any]:
    return {
        "kind": "governance.packageObligation.v1",
        "adrsRef": "roccho-dev/adrs#101",
        "universe": "all-feature-packages",
        "repo": "roccho-dev/ui",
        "packageId": "ui.property-map",
        "packagePath": "packages/property-map",
        "ownerRole": "ui",
        "obligationId": "pkg.ui.property-map",
        "requirementId": "projection-evidence",
        "requiredTestId": "property-map-render-proof",
    }


def sample_response(obligation: dict[str, Any] | None = None) -> dict[str, Any]:
    base = obligation or sample_obligation()
    return {
        "kind": "governance.packageResponse.v1",
        **{field: base[field] for field in IDENTITY_FIELDS},
        "status": "pass",
        "tests": [base["requiredTestId"]],
        "evidenceFresh": True,
        "receiptPresent": True,
        "residualsVisible": True,
        "checkAdoption": True,
    }


def response_has_required_test(response: dict[str, Any], required_test_id: str) -> bool:
    if response.get("requiredTestPresent") is True:
        return True
    tests = response.get("tests")
    return isinstance(tests, list) and required_test_id in tests


def response_has_non_goal_gap(response: dict[str, Any]) -> bool:
    if response.get("nonGoalGap") is True:
        return True
    gaps = response.get("gaps")
    return isinstance(gaps, list) and any(isinstance(gap, dict) and gap.get("classification") == "non-goal" for gap in gaps)


def _relaxed_key(row: dict[str, Any], omitted_field: str) -> tuple[str, ...] | None:
    values: list[str] = []
    for field in IDENTITY_FIELDS:
        if field == omitted_field:
            continue
        value = value_as_string(row, field)
        if value is None:
            return None
        values.append(value)
    return tuple(values)


def _response_candidates_by_relaxed_key(responses: list[dict[str, Any]], omitted_field: str) -> dict[tuple[str, ...], list[dict[str, Any]]]:
    index: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for response in responses:
        key = _relaxed_key(response, omitted_field)
        if key is not None:
            index[key].append(response)
    return index


def build_package_join_report(obligations: list[dict[str, Any]], responses: list[dict[str, Any]]) -> dict[str, Any]:
    response_key_counts = Counter(key for key in (package_key(row) for row in responses) if key is not None)
    response_by_key: dict[tuple[str, ...], dict[str, Any]] = {}
    for row in responses:
        key = package_key(row)
        if key is not None and key not in response_by_key:
            response_by_key[key] = row

    by_role = _response_candidates_by_relaxed_key(responses, "ownerRole")
    by_path = _response_candidates_by_relaxed_key(responses, "packagePath")
    obligation_keys: set[tuple[str, ...]] = set()
    rows: list[dict[str, Any]] = []

    for obligation in obligations:
        key = package_key(obligation)
        if key is None:
            continue
        obligation_keys.add(key)
        response = response_by_key.get(key)
        diagnostics: list[str] = []
        if response is None:
            diagnostics.append("missing-response")
            role_key = _relaxed_key(obligation, "ownerRole")
            path_key = _relaxed_key(obligation, "packagePath")
            if role_key is not None and role_key in by_role:
                diagnostics.append("role-mismatch")
            if path_key is not None and path_key in by_path:
                diagnostics.append("path-drift")
        else:
            if not response_has_required_test(response, obligation["requiredTestId"]):
                diagnostics.append("missing-required-test")
            if response.get("untestedRequirement") is True:
                diagnostics.append("untested-requirement")
            if response_has_non_goal_gap(response):
                diagnostics.append("non-goal-gap")
            if response_key_counts[key] > 1:
                diagnostics.append("duplicate-response")
        rows.append({"kind": "governance.packageJoin.row.v1", **key_to_object(key), "status": "green" if not diagnostics else "non-green", "diagnostics": sorted(set(diagnostics))})

    for response in responses:
        key = package_key(response)
        if key is not None and key not in obligation_keys:
            rows.append({"kind": "governance.packageJoin.row.v1", **key_to_object(key), "status": "non-green", "diagnostics": ["extra-response"]})

    rows = sorted(rows, key=lambda row: tuple(row[field] for field in IDENTITY_FIELDS) + tuple(row["diagnostics"]))
    return {
        "kind": "governance.packageJoin.report.v1",
        "status": "fail" if any(row["status"] != "green" for row in rows) else "pass",
        "nonAuthority": True,
        "rows": rows,
        "summary": {"rows": len(rows), "green": sum(1 for row in rows if row["status"] == "green"), "nonGreen": sum(1 for row in rows if row["status"] != "green")},
    }


def join_report_selftest() -> None:
    obligation = sample_obligation()
    valid_response = sample_response(obligation)
    if build_package_join_report([obligation], [valid_response])["status"] != "pass":
        raise SystemExit("valid package join failed")
    cases: list[tuple[str, list[dict[str, Any]], set[str]]] = [
        ("missing response", [], {"missing-response"}),
        ("missing required test", [dict(valid_response, tests=[])], {"missing-required-test"}),
        ("role mismatch", [dict(valid_response, ownerRole="ops")], {"missing-response", "role-mismatch", "extra-response"}),
        ("path drift", [dict(valid_response, packagePath="packages/property-map-v2")], {"missing-response", "path-drift", "extra-response"}),
        ("non goal gap", [dict(valid_response, nonGoalGap=True)], {"non-goal-gap"}),
        ("duplicate response", [valid_response, dict(valid_response)], {"duplicate-response"}),
        ("extra response", [valid_response, dict(valid_response, packageId="ui.extra", obligationId="pkg.ui.extra")], {"extra-response"}),
    ]
    for name, responses, expected in cases:
        report = build_package_join_report([obligation], responses)
        codes = {code for row in report["rows"] for code in row["diagnostics"]}
        if not expected.issubset(codes):
            raise SystemExit(json.dumps({"case": name, "expected": sorted(expected), "report": report}, indent=2, sort_keys=True))
