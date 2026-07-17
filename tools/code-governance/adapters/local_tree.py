from __future__ import annotations

import argparse
from pathlib import Path

from engine.common import write_json
from engine.tree import write_manifest
from ._tree_copy import CopyError, copy_selected


class AdapterError(RuntimeError):
    pass


def capture(source_root: Path, includes: list[str], output_dir: Path) -> dict[str, object]:
    try:
        snapshot = output_dir / "snapshot"
        copy_selected(source_root, snapshot, includes)
    except CopyError as exc:
        raise AdapterError(str(exc)) from exc
    manifest = write_manifest(snapshot, output_dir / "tree.json")
    receipt: dict[str, object] = {
        "kind": "transport-receipt.v1",
        "provider": "local-directory",
        "locator": str(source_root.resolve()),
        "includes": includes,
        "tree_sha256": manifest["tree_sha256"],
    }
    write_json(output_dir / "transport-receipt.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--include", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        capture(args.source_root, args.include, args.output)
    except AdapterError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
