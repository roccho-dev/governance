from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from engine.common import read_json
from .github_pages import AdapterError, capture as capture_pages

API_ROOT = "https://api.github.com"


def _request_json(url: str, token: str | None) -> tuple[list[dict[str, Any]], dict[str, str]]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "governance-code-governance-fixture-v1",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
            response_headers = {key.lower(): value for key, value in response.headers.items()}
    except (urllib.error.URLError, UnicodeError, json.JSONDecodeError) as exc:
        raise AdapterError(f"failed to fetch provider page: {exc}") from exc
    if not isinstance(payload, list):
        raise AdapterError("provider page must be an array")
    return payload, response_headers


def _fetch_pages(repository: str, issue: int, token: str | None, output_dir: Path) -> Path:
    pages: list[list[dict[str, Any]]] = []
    page = 1
    while True:
        query = urllib.parse.urlencode({"per_page": 100, "page": page})
        url = f"{API_ROOT}/repos/{repository}/issues/{issue}/comments?{query}"
        payload, headers = _request_json(url, token)
        pages.append(payload)
        link = headers.get("link", "")
        has_next = 'rel="next"' in link
        if not has_next:
            break
        page += 1
        if page > 1000:
            raise AdapterError("provider pagination exceeded 1000 pages")

    pages_dir = output_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    for index, comments in enumerate(pages, start=1):
        normalized: list[dict[str, Any]] = []
        for value in comments:
            if not isinstance(value, dict):
                raise AdapterError("provider response comment must be an object")
            user = value.get("user")
            normalized.append(
                {
                    "id": value.get("id"),
                    "created_at": value.get("created_at"),
                    "updated_at": value.get("updated_at"),
                    "author": {"login": user.get("login") if isinstance(user, dict) else None},
                    "body": value.get("body"),
                }
            )
        page_value = {
            "page": index,
            "has_next": index < len(pages),
            "comments": normalized,
        }
        (pages_dir / f"page-{index:04d}.json").write_text(
            json.dumps(page_value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
    return pages_dir


def capture(
    repository: str,
    issue: int,
    trusted_actor: str,
    output_dir: Path,
    *,
    token: str | None = None,
    previous_receipt: Path | None = None,
    expected_event_count: int | None = None,
    expected_row_count: int | None = None,
    expected_ledger_sha256: str | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    pages_dir = _fetch_pages(repository, issue, token, output_dir)
    receipt = capture_pages(
        pages_dir,
        repository,
        issue,
        trusted_actor,
        output_dir,
        previous_receipt,
    )
    if expected_event_count is not None and receipt["selected_event_count"] != expected_event_count:
        raise AdapterError(
            f"selected event count mismatch: expected {expected_event_count}, got {receipt['selected_event_count']}"
        )
    if expected_row_count is not None and receipt["row_count"] != expected_row_count:
        raise AdapterError(f"row count mismatch: expected {expected_row_count}, got {receipt['row_count']}")
    if expected_ledger_sha256 is not None and receipt["ledger_sha256"] != expected_ledger_sha256:
        raise AdapterError(
            f"ledger digest mismatch: expected {expected_ledger_sha256}, got {receipt['ledger_sha256']}"
        )
    return read_json(output_dir / "transport-receipt.json")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--issue", type=int, required=True)
    parser.add_argument("--trusted-actor", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--token-env", default="ADRS_TOKEN")
    parser.add_argument("--previous-receipt", type=Path)
    parser.add_argument("--expected-event-count", type=int)
    parser.add_argument("--expected-row-count", type=int)
    parser.add_argument("--expected-ledger-sha256")
    args = parser.parse_args()
    token = os.environ.get(args.token_env) or None
    try:
        capture(
            args.repository,
            args.issue,
            args.trusted_actor,
            args.output,
            token=token,
            previous_receipt=args.previous_receipt,
            expected_event_count=args.expected_event_count,
            expected_row_count=args.expected_row_count,
            expected_ledger_sha256=args.expected_ledger_sha256,
        )
    except AdapterError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
