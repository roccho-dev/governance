from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .common import canonical_json, sha256_bytes, sha256_text, write_json


class TreeError(RuntimeError):
    pass


def build_manifest(root: Path) -> dict[str, Any]:
    root = root.resolve()
    if not root.is_dir():
        raise TreeError(f"not a directory: {root}")
    entries: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        if ".git" in path.relative_to(root).parts:
            continue
        if path.is_symlink():
            target = os.readlink(path)
            if os.path.isabs(target):
                raise TreeError(f"absolute symlink is forbidden: {relative}")
            entries.append({"path": relative, "type": "symlink", "target": target})
        elif path.is_file():
            data = path.read_bytes()
            entries.append(
                {
                    "path": relative,
                    "type": "file",
                    "executable": bool(path.stat().st_mode & 0o111),
                    "size": len(data),
                    "sha256": sha256_bytes(data),
                }
            )
        elif path.is_dir():
            continue
        else:
            raise TreeError(f"unsupported filesystem entry: {relative}")
    manifest_core = {"kind": "sealed-tree.v1", "entries": entries}
    digest = sha256_text(canonical_json(manifest_core) + "\n")
    return {**manifest_core, "tree_sha256": digest}


def write_manifest(root: Path, output: Path) -> dict[str, Any]:
    manifest = build_manifest(root)
    write_json(output, manifest)
    return manifest
