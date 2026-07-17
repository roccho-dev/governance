from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def write_pages(path: Path, comments: list[dict[str, Any]], sizes: list[int]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for old in path.glob("page-*.json"):
        old.unlink()
    pages: list[list[dict[str, Any]]] = []
    position = 0
    for size in sizes:
        if position >= len(comments):
            break
        pages.append(comments[position : position + size])
        position += size
    if position < len(comments):
        pages.append(comments[position:])
    for number, values in enumerate(pages, start=1):
        payload = {"page": number, "has_next": number < len(pages), "comments": values}
        (path / f"page-{number:04d}.json").write_text(canonical(payload) + "\n", encoding="utf-8")


def source_comments(rows: list[dict[str, Any]], actor: str, start_id: int, chunk_size: int) -> list[dict[str, Any]]:
    comments: list[dict[str, Any]] = []
    for index in range(0, len(rows), chunk_size):
        chunk = rows[index : index + chunk_size]
        sequence = len(comments) + 1
        timestamp = f"2030-01-02T00:{sequence:02d}:00Z"
        comments.append({"id": start_id + sequence, "created_at": timestamp, "updated_at": timestamp, "author": {"login": actor}, "body": "\n".join(canonical(row) for row in chunk)})
    return comments


def generate(ledger: Path, output: Path) -> None:
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
    output.mkdir(parents=True, exist_ok=True)
    ledger_dir = output / "ledger"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    variant = "\r\n".join(json.dumps(row, ensure_ascii=False, sort_keys=False, separators=(", ", ": ")) for row in reversed(rows)) + "\r\n"
    (ledger_dir / "variant.jsonl").write_bytes(variant.encode("utf-8"))

    actor_a = "fixture-writer-a"
    current = source_comments(rows, actor_a, 1000, 6)
    previous = current[:-1]
    discussion_a = {"id": 900, "created_at": "2030-01-01T00:00:00Z", "updated_at": "2030-01-01T00:00:00Z", "author": {"login": actor_a}, "body": "Narrative text by the source writer is not semantic input."}
    write_pages(output / "github-a-previous", [*previous, discussion_a], [4, 5])
    write_pages(output / "github-a", [*current, discussion_a], [5, 5])

    actor_b = "fixture-writer-b"
    discussion_b = {"id": 8900, "created_at": "2030-01-01T00:00:00Z", "updated_at": "2030-01-01T00:00:00Z", "author": {"login": actor_b}, "body": "A non-JSONL receipt is transport-only."}
    reversed_comments = source_comments(list(reversed(rows)), actor_b, 9000, 5)
    write_pages(output / "github-b", [discussion_b, *reversed_comments], [2, 4, 3, 99])

    metadata = {"row_count": len(rows), "github_a_event_count": len(current), "github_b_event_count": len(reversed_comments), "actor_a": actor_a, "actor_b": actor_b}
    (output / "manifest.json").write_text(canonical(metadata) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    generate(args.ledger, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
