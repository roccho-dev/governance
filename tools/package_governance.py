from __future__ import annotations

import json
from pathlib import Path
from typing import Any

IDENTITY_FIELDS = [
    "adrsRef",
    "universe",
    "repo",
    "packageId",
    "packagePath",
    "ownerRole",
    "obligationId",
    "requirementId",
    "requiredTestId",
]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"invalid JSONL {path}:{line_no}: {exc}") from exc
        if not isinstance(row, dict):
            raise SystemExit(f"invalid JSONL {path}:{line_no}: row is not object")
        rows.append(row)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def value_as_string(row: dict[str, Any], field: str) -> str | None:
    value = row.get(field)
    if isinstance(value, str) and value:
        return value
    return None


def target_universe_set(rows: list[dict[str, Any]]) -> set[str]:
    universes: set[str] = set()
    for row in rows:
        universe = value_as_string(row, "universe") or value_as_string(row, "id")
        if universe:
            universes.add(universe)
    return universes


def package_key(row: dict[str, Any]) -> tuple[str, ...] | None:
    values: list[str] = []
    for field in IDENTITY_FIELDS:
        value = value_as_string(row, field)
        if value is None:
            return None
        values.append(value)
    return tuple(values)


def key_to_object(key: tuple[str, ...]) -> dict[str, str]:
    return dict(zip(IDENTITY_FIELDS, key, strict=True))


def finding(code: str, row_kind: str, row_index: int | None, message: str, row: dict[str, Any] | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {"code": code, "rowKind": row_kind, "message": message}
    if row_index is not None:
        item["rowIndex"] = row_index
    if row is not None:
        for field in IDENTITY_FIELDS:
            value = row.get(field)
            if isinstance(value, str) and value:
                item[field] = value
    return item


def parse_package_inputs(target_universes: list[dict[str, Any]], obligations: list[dict[str, Any]], responses: list[dict[str, Any]]) -> dict[str, Any]:
    universes = target_universe_set(target_universes)
    findings: list[dict[str, Any]] = []
    obligations_by_universe: dict[str, int] = {universe: 0 for universe in universes}
    parsed_obligations: list[dict[str, Any]] = []
    parsed_responses: list[dict[str, Any]] = []
    obligation_keys: set[tuple[str, ...]] = set()

    for index, row in enumerate(obligations, 1):
        universe = value_as_string(row, "universe")
        if universe is None or universe not in universes:
            findings.append(finding("target-universe-unknown", "obligation", index, "obligation references an unknown target universe", row))
            continue
        obligations_by_universe[universe] = obligations_by_universe.get(universe, 0) + 1
        if value_as_string(row, "packageId") is None:
            findings.append(finding("package-id-missing", "obligation", index, "package obligation is missing packageId", row))
            continue
        missing_fields = [field for field in IDENTITY_FIELDS if value_as_string(row, field) is None]
        if missing_fields:
            findings.append(finding("package-identity-field-missing", "obligation", index, "package obligation is missing required identity fields: " + ",".join(missing_fields), row))
            continue
        key = package_key(row)
        assert key is not None
        obligation_keys.add(key)
        parsed_obligations.append({"kind": "governance.parsedPackageObligation.v1", **key_to_object(key)})

    for universe, count in sorted(obligations_by_universe.items()):
        if count == 0:
            findings.append(finding("obligation-missing", "target-universe", None, f"target universe {universe!r} has no package obligation", {"universe": universe}))

    for index, row in enumerate(responses, 1):
        universe = value_as_string(row, "universe")
        if universe is None or universe not in universes:
            findings.append(finding("target-universe-unknown", "response", index, "package response references an unknown target universe", row))
            continue
        if value_as_string(row, "packageId") is None:
            findings.append(finding("package-id-missing", "response", index, "package response is missing packageId", row))
            continue
        missing_fields = [field for field in IDENTITY_FIELDS if value_as_string(row, field) is None]
        if missing_fields:
            findings.append(finding("package-identity-field-missing", "response", index, "package response is missing required identity fields: " + ",".join(missing_fields), row))
            continue
        key = package_key(row)
        assert key is not None
        parsed_responses.append({"kind": "governance.parsedPackageResponse.v1", **key_to_object(key)})

    response_keys = {package_key(row) for row in responses if package_key(row) is not None}
    for key in sorted(obligation_keys):
        if key not in response_keys:
            findings.append(finding("claim-missing", "obligation", None, "package obligation has no matching package response", key_to_object(key)))

    return {
        "kind": "governance.packageParser.report.v1",
        "status": "fail" if findings else "pass",
        "nonAuthority": True,
        "summary": {"targetUniverses": len(universes), "parsedObligations": len(parsed_obligations), "parsedResponses": len(parsed_responses), "findings": len(findings)},
        "obligations": sorted(parsed_obligations, key=lambda row: tuple(row[field] for field in IDENTITY_FIELDS)),
        "responses": sorted(parsed_responses, key=lambda row: tuple(row[field] for field in IDENTITY_FIELDS)),
        "findings": sorted(findings, key=lambda row: (row["code"], row.get("universe", ""), row.get("repo", ""), row.get("packageId", ""))),
    }


def parser_selftest() -> None:
    valid_obligation = {
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
    valid_response = {"kind": "governance.packageResponse.v1", **{field: valid_obligation[field] for field in IDENTITY_FIELDS}, "status": "pass"}
    cases = [
        ("purpose reset without target universe", [], [valid_obligation], [], "target-universe-unknown"),
        ("universe without package obligation", [{"universe": "all-feature-packages"}], [], [], "obligation-missing"),
        ("package obligation without package_id", [{"universe": "all-feature-packages"}], [{k: v for k, v in valid_obligation.items() if k != "packageId"}], [], "package-id-missing"),
        ("obligation without feature claim", [{"universe": "all-feature-packages"}], [valid_obligation], [], "claim-missing"),
    ]
    for name, universes, obligations, responses, expected_code in cases:
        report = parse_package_inputs(universes, obligations, responses)
        codes = {item["code"] for item in report["findings"]}
        if expected_code not in codes:
            raise SystemExit(json.dumps({"case": name, "report": report}, indent=2, sort_keys=True))
    report = parse_package_inputs([{"universe": "all-feature-packages"}], [valid_obligation], [valid_response])
    if report["status"] != "pass" or report["findings"]:
        raise SystemExit(json.dumps({"case": "adopted claim with valid required fields", "report": report}, indent=2, sort_keys=True))
