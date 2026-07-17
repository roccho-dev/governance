from __future__ import annotations

import argparse
from pathlib import Path

from engine.common import digest_file, write_json
from engine.ledger import LedgerError, seal_text


class AdapterError(RuntimeError):
    pass


def capture(source: Path, output_dir: Path) -> dict[str, object]:
    if not source.is_file():
        raise AdapterError(f"not a file: {source}")
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        ledger = seal_text(source.read_text(encoding="utf-8"), output_dir / "ledger.jsonl", label=str(source))
    except (UnicodeError, LedgerError) as exc:
        raise AdapterError(str(exc)) from exc
    receipt: dict[str, object] = {
        "kind": "transport-receipt.v1",
        "provider": "file-jsonl",
        "locator": str(source.resolve()),
        "raw_input_sha256": digest_file(source),
        "row_count": ledger["row_count"],
        "ledger_sha256": ledger["ledger_sha256"],
    }
    write_json(output_dir / "transport-receipt.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        capture(args.source, args.output)
    except AdapterError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
