from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .common import canonical_json, sha256_text, write_jsonl


class LedgerError(RuntimeError):
    pass


def parse_jsonl_text(text: str, *, label: str = "ledger") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LedgerError(f"{label}:{line_no}: invalid JSON: {exc}") from exc
        if not isinstance(value, dict):
            raise LedgerError(f"{label}:{line_no}: row must be an object")
        rows.append(value)
    if not rows:
        raise LedgerError(f"{label}: no rows")
    return rows


def canonicalize_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    values = list(rows)
    by_id: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(values, start=1):
        if not isinstance(row, dict):
            raise LedgerError(f"row {index}: must be an object")
        event_id = row.get("id")
        if not isinstance(event_id, str) or not event_id:
            raise LedgerError(f"row {index}: missing non-empty id")
        if event_id in by_id:
            raise LedgerError(f"duplicate event id: {event_id}")
        by_id[event_id] = row
    return [by_id[event_id] for event_id in sorted(by_id)]


def seal_rows(rows: Iterable[dict[str, Any]], output: Path) -> dict[str, Any]:
    canonical_rows = canonicalize_rows(rows)
    write_jsonl(output, canonical_rows)
    text = output.read_text(encoding="utf-8")
    return {
        "kind": "canonical-ledger-receipt.v1",
        "row_count": len(canonical_rows),
        "ledger_sha256": sha256_text(text),
    }


def seal_text(text: str, output: Path, *, label: str = "ledger") -> dict[str, Any]:
    return seal_rows(parse_jsonl_text(text, label=label), output)
