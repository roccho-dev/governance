from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from .packet import build
from .reducer import run as reduce_run
from .scan_go import run as scan_run
from .tree import write_manifest


class PipelineError(RuntimeError):
    pass


def run(ledger: Path, schema: Path, project_root: Path, output_dir: Path) -> Path:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    reduce_run(ledger, schema, output_dir / "reduced")
    scan_run(project_root, output_dir / "reduced/projection.jsonl", output_dir / "scanned")
    tree_path = output_dir / "tree.json"
    write_manifest(project_root, tree_path)
    packet_path = output_dir / "semantic-packet.json"
    build(output_dir, ledger, schema, tree_path, packet_path)
    return packet_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.ledger, args.schema, args.project_root, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
