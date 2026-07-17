from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from engine.common import canonical_json, read_json, sha256_text, write_json
from engine.ledger import LedgerError, parse_jsonl_text, seal_rows

PAGE_RE = re.compile(r"^page-(\d{4})\.json$")


class AdapterError(RuntimeError):
    pass


def _load_pages(pages_dir: Path) -> list[dict[str, Any]]:
    candidates: list[tuple[int, Path]] = []
    for path in pages_dir.iterdir():
        match = PAGE_RE.match(path.name)
        if match:
            candidates.append((int(match.group(1)), path))
    if not candidates:
        raise AdapterError(f"no page-NNNN.json files in {pages_dir}")
    candidates.sort()
    actual = [number for number, _ in candidates]
    expected = list(range(1, len(candidates) + 1))
    if actual != expected:
        raise AdapterError(f"non-contiguous pages: expected {expected}, got {actual}")

    pages: list[dict[str, Any]] = []
    for number, path in candidates:
        page = read_json(path)
        if not isinstance(page, dict) or set(page) != {"page", "has_next", "comments"}:
            raise AdapterError(f"{path}: invalid page fields")
        if page["page"] != number:
            raise AdapterError(f"{path}: page number mismatch")
        if page["has_next"] is not (number < len(candidates)):
            raise AdapterError(f"{path}: has_next mismatch")
        if not isinstance(page["comments"], list):
            raise AdapterError(f"{path}: comments must be an array")
        pages.append(page)
    return pages


def capture(
    pages_dir: Path,
    repository: str,
    issue: int,
    trusted_actor: str,
    output_dir: Path,
    previous_receipt: Path | None = None,
) -> dict[str, Any]:
    pages = _load_pages(pages_dir)
    comments: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    for page in pages:
        for value in page["comments"]:
            if not isinstance(value, dict):
                raise AdapterError("comment must be an object")
            required = {"id", "created_at", "updated_at", "author", "body"}
            if set(value) != required:
                raise AdapterError(f"comment fields mismatch: {sorted(set(value) ^ required)}")
            provider_id = value["id"]
            if not isinstance(provider_id, int) or provider_id < 1:
                raise AdapterError("comment id must be a positive integer")
            if provider_id in seen_ids:
                raise AdapterError(f"duplicate comment id {provider_id}")
            seen_ids.add(provider_id)
            comments.append(value)
    comments.sort(key=lambda item: item["id"])

    semantic_rows: list[dict[str, Any]] = []
    selected_events: list[dict[str, Any]] = []
    semantic_index: list[dict[str, Any]] = []
    for value in comments:
        author = value["author"]
        if not isinstance(author, dict) or set(author) != {"login"}:
            raise AdapterError(f"comment {value['id']}: invalid author")
        if author["login"] != trusted_actor:
            continue
        body = value["body"]
        if not isinstance(body, str) or not body.strip():
            continue
        try:
            rows = parse_jsonl_text(body, label=f"event-{value['id']}")
        except LedgerError:
            # The provider UI may contain discussion or receipts by the same actor.
            # Only JSONL-only events enter the semantic ledger; the expected ledger
            # digest detects any omitted or additional semantic event.
            continue
        if value["created_at"] != value["updated_at"]:
            raise AdapterError(f"comment {value['id']}: trusted source event was edited")
        selected_events.append(
            {
                "provider_event_id": value["id"],
                "created_at": value["created_at"],
                "body_sha256": sha256_text(body),
                "row_count": len(rows),
            }
        )
        for line, row in enumerate(rows, start=1):
            semantic_rows.append(row)
            semantic_index.append(
                {
                    "event_id": row["id"],
                    "provider_event_id": value["id"],
                    "line": line,
                    "row_sha256": sha256_text(canonical_json(row)),
                }
            )

    if not selected_events:
        raise AdapterError("no trusted source events")

    if previous_receipt is not None:
        previous = read_json(previous_receipt)
        expected_locator = {"repository": repository, "issue": issue}
        if previous.get("provider") != "github-issues" or previous.get("locator") != expected_locator:
            raise AdapterError("previous receipt locator mismatch")
        if previous.get("trusted_actor") != trusted_actor:
            raise AdapterError("previous receipt actor mismatch")
        old_events = previous.get("selected_events")
        if not isinstance(old_events, list):
            raise AdapterError("previous receipt has no selected_events")
        current_by_id = {item["provider_event_id"]: item for item in selected_events}
        for old in old_events:
            current = current_by_id.get(old["provider_event_id"])
            if current is None:
                raise AdapterError(f"previous source event {old['provider_event_id']} was deleted")
            if current != old:
                raise AdapterError(f"previous source event {old['provider_event_id']} changed")
        old_ids = {item["provider_event_id"] for item in old_events}
        previous_max = max(old_ids, default=0)
        new_ids = [item["provider_event_id"] for item in selected_events if item["provider_event_id"] not in old_ids]
        if any(value <= previous_max for value in new_ids):
            raise AdapterError("new source event is not appended after previous maximum id")

    output_dir.mkdir(parents=True, exist_ok=True)
    ledger_receipt = seal_rows(semantic_rows, output_dir / "ledger.jsonl")
    pages_digest = sha256_text("".join(canonical_json(page) + "\n" for page in pages))
    receipt = {
        "kind": "transport-receipt.v1",
        "provider": "github-issues",
        "locator": {"repository": repository, "issue": issue},
        "trusted_actor": trusted_actor,
        "page_count": len(pages),
        "selected_event_count": len(selected_events),
        "row_count": ledger_receipt["row_count"],
        "selected_events": selected_events,
        "semantic_index": semantic_index,
        "raw_pages_sha256": pages_digest,
        "ledger_sha256": ledger_receipt["ledger_sha256"],
    }
    write_json(output_dir / "transport-receipt.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", type=Path, required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--issue", type=int, required=True)
    parser.add_argument("--trusted-actor", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--previous-receipt", type=Path)
    args = parser.parse_args()
    try:
        capture(
            args.pages,
            args.repository,
            args.issue,
            args.trusted_actor,
            args.output,
            args.previous_receipt,
        )
    except AdapterError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
