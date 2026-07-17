from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path

from engine.common import write_json
from engine.tree import write_manifest
from ._tree_copy import CopyError, copy_selected


class AdapterError(RuntimeError):
    pass


def _run(command: list[str], *, cwd: Path | None = None) -> str:
    completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise AdapterError(f"command failed: {command!r}\n{completed.stdout}{completed.stderr}")
    return completed.stdout.strip()


def capture(locator: str, revision: str, includes: list[str], output_dir: Path) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="sealed-tree-") as tmp:
        checkout = Path(tmp) / "checkout"
        _run(["git", "clone", "--quiet", "--no-checkout", locator, str(checkout)])
        _run(["git", "checkout", "--quiet", "--detach", revision], cwd=checkout)
        resolved = _run(["git", "rev-parse", "HEAD"], cwd=checkout)
        try:
            snapshot = output_dir / "snapshot"
            copy_selected(checkout, snapshot, includes)
        except CopyError as exc:
            raise AdapterError(str(exc)) from exc
    manifest = write_manifest(output_dir / "snapshot", output_dir / "tree.json")
    receipt: dict[str, object] = {
        "kind": "transport-receipt.v1",
        "provider": "git",
        "locator": locator,
        "requested_revision": revision,
        "resolved_revision": resolved,
        "includes": includes,
        "tree_sha256": manifest["tree_sha256"],
    }
    write_json(output_dir / "transport-receipt.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--locator", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--include", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        capture(args.locator, args.revision, args.include, args.output)
    except AdapterError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
