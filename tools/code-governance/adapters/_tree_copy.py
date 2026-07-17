from __future__ import annotations

import shutil
from pathlib import Path, PurePosixPath


class CopyError(RuntimeError):
    pass


def validate_include(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise CopyError(f"invalid include path: {value}")
    return path


def copy_selected(source_root: Path, snapshot_root: Path, includes: list[str]) -> None:
    source_root = source_root.resolve()
    if not source_root.is_dir():
        raise CopyError(f"not a directory: {source_root}")
    if snapshot_root.exists():
        shutil.rmtree(snapshot_root)
    snapshot_root.mkdir(parents=True)
    for raw in includes:
        relative = validate_include(raw)
        source = source_root.joinpath(*relative.parts)
        destination = snapshot_root.joinpath(*relative.parts)
        if source.is_dir():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source, destination, symlinks=True)
        elif source.is_file() or source.is_symlink():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination, follow_symlinks=False)
        else:
            raise CopyError(f"include does not exist: {raw}")
