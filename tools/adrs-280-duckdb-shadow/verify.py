#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path

try:
    import duckdb
except ImportError as exc:
    raise SystemExit("duckdb is required") from exc

ROOT = Path(__file__).resolve().parents[2]
TOOL = Path(__file__).resolve().parent
FIXTURE = TOOL / "fixture"
SQL_PATH = TOOL / "reduce_project.sql"
PIN_SOURCE = ROOT / "tools" / "contract-modeling" / "requirements.txt"
OUTPUTS = (
    ("adr_current_export", "adr.current.jsonl"),
    ("accepted_decision_current_export", "accepted-decision.current.jsonl"),
    ("gov_input_export", "gov-input.jsonl"),
)


def _expected_duckdb_version() -> str:
    match = re.search(r"^duckdb==([^\s]+)$", PIN_SOURCE.read_text(encoding="utf-8"), re.MULTILINE)
    if not match:
        raise AssertionError("shared DuckDB pin missing")
    return match.group(1)


def _json_lines(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def _sql_literal(path: Path) -> str:
    return "'" + str(path).replace("'", "''") + "'"


def _register_inputs(con: duckdb.DuckDBPyConnection, work: Path) -> None:
    con.execute(
        f"CREATE TEMP VIEW raw_events AS SELECT * FROM read_json_auto({_sql_literal(work / 'raw.jsonl')}, format='newline_delimited')"
    )
    con.execute(
        f"CREATE TEMP VIEW authorization_results AS SELECT * FROM read_json_auto({_sql_literal(work / 'authorization-results.jsonl')}, format='newline_delimited')"
    )
    con.execute(
        f"CREATE TEMP VIEW fixture_meta AS SELECT * FROM read_json_auto({_sql_literal(work / 'fixture-meta.json')})"
    )


def _run(work: Path) -> dict[str, bytes]:
    con = duckdb.connect(":memory:")
    try:
        _register_inputs(con, work)
        con.execute(SQL_PATH.read_text(encoding="utf-8"))
        result: dict[str, bytes] = {}
        for view, filename in OUTPUTS:
            rows = [
                row[0]
                for row in con.execute(f"SELECT json_line FROM {view} ORDER BY sort_key").fetchall()
            ]
            data = ("\n".join(rows) + ("\n" if rows else "")).encode()
            result[filename] = data
        return result
    finally:
        con.close()


def _assert_expected(actual: dict[str, bytes]) -> None:
    for _, filename in OUTPUTS:
        expected_rows = _json_lines(FIXTURE / "expected" / filename)
        actual_rows = [json.loads(line) for line in actual[filename].decode().splitlines() if line]
        if actual_rows != expected_rows:
            raise AssertionError(
                f"projection mismatch for {filename}:\nexpected={expected_rows}\nactual={actual_rows}"
            )


def _assert_fixture_hashes() -> None:
    meta = json.loads((FIXTURE / "fixture-meta.json").read_text(encoding="utf-8"))
    for filename, key in (
        ("raw.jsonl", "rawSha256"),
        ("authorization-results.jsonl", "authorizationSha256"),
    ):
        actual = "sha256:" + hashlib.sha256((FIXTURE / filename).read_bytes()).hexdigest()
        if meta[key] != actual:
            raise AssertionError(f"fixture hash mismatch for {filename}: {meta[key]} != {actual}")


def _copy_fixture() -> Path:
    root = Path(tempfile.mkdtemp(prefix="adrs280-duckdb-"))
    for filename in ("raw.jsonl", "authorization-results.jsonl", "fixture-meta.json"):
        shutil.copy2(FIXTURE / filename, root / filename)
    return root


def _assert_order_independence(baseline: dict[str, bytes]) -> None:
    work = _copy_fixture()
    try:
        raw = list(reversed(_json_lines(work / "raw.jsonl")))
        auth = list(reversed(_json_lines(work / "authorization-results.jsonl")))
        _write_jsonl(work / "raw.jsonl", raw)
        _write_jsonl(work / "authorization-results.jsonl", auth)
        reordered = _run(work)
        if reordered != baseline:
            raise AssertionError("physical JSONL row order changed reducer/projector output")
    finally:
        shutil.rmtree(work)


def _expect_error(name: str, mutate) -> None:
    work = _copy_fixture()
    try:
        raw = _json_lines(work / "raw.jsonl")
        auth = _json_lines(work / "authorization-results.jsonl")
        mutate(raw, auth)
        _write_jsonl(work / "raw.jsonl", raw)
        _write_jsonl(work / "authorization-results.jsonl", auth)
        try:
            _run(work)
        except Exception:
            return
        raise AssertionError(f"destructive case did not fail closed: {name}")
    finally:
        shutil.rmtree(work)


def _destructive_cases() -> None:
    _expect_error(
        "unknown-kind", lambda raw, auth: raw[0].__setitem__("kind", "timestamp-latest-wins")
    )
    _expect_error("duplicate-event-id", lambda raw, auth: raw.append(dict(raw[0])))
    _expect_error("missing-authorization", lambda raw, auth: auth.pop())

    def broken_predecessor(raw, auth):
        row = next(row for row in raw if row["eventId"] == "pending-accept-v1")
        row["predecessorDigest"] = "sha256:" + "f" * 64

    _expect_error("broken-predecessor", broken_predecessor)

    def stale_accept(raw, auth):
        row = next(row for row in raw if row["eventId"] == "accepted-accept-v2")
        row["targetStateDigest"] = "sha256:" + "a" * 64

    _expect_error("stale-accept-target", stale_accept)

    def provider_leak(raw, auth):
        raw[0]["issueNumber"] = 280

    _expect_error("provider-metadata-in-semantic-lane", provider_leak)


def main() -> int:
    expected_version = _expected_duckdb_version()
    if duckdb.__version__ != expected_version:
        raise AssertionError(
            f"DuckDB version drift: expected {expected_version}, got {duckdb.__version__}"
        )
    _assert_fixture_hashes()
    baseline = _run(FIXTURE)
    _assert_expected(baseline)
    _assert_order_independence(baseline)
    _destructive_cases()
    receipt = {
        "kind": "adrs280.duckdbShadowReducerReceipt.v1",
        "status": "pass",
        "authority": False,
        "cutoverAuthorized": False,
        "liveGitHubIssueRead": False,
        "duckdbVersion": duckdb.__version__,
        "reducerSqlSha256": "sha256:" + hashlib.sha256(SQL_PATH.read_bytes()).hexdigest(),
        "outputs": {
            name: "sha256:" + hashlib.sha256(data).hexdigest()
            for name, data in sorted(baseline.items())
        },
        "checks": {
            "goldenProjection": True,
            "physicalOrderIndependent": True,
            "unauthorizedAcceptIgnored": True,
            "branchConflictQuarantined": True,
            "destructiveCasesFailClosed": 6,
        },
    }
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
