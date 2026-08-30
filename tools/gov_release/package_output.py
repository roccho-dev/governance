from __future__ import annotations

import hashlib
import io
import json
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

from tools.package_obligations.core import ContractError, load_fixture
from tools.package_obligations.materialize import (
    OUTPUT_FILE,
    RECEIPT_FILE,
    check_materialized,
)


class PackageOutputError(ValueError):
    pass


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _regular_file(path: Path, label: str) -> None:
    if not path.exists() or not path.is_file() or path.is_symlink():
        raise PackageOutputError(f"{label}-regular-file-required:{path}")


def check_directory(packet_dir: Path, fixture_dir: Path) -> dict[str, Any]:
    packet_dir = packet_dir.resolve()
    fixture_dir = fixture_dir.resolve()
    if not packet_dir.is_dir() or packet_dir.is_symlink():
        raise PackageOutputError("packet-directory-required")
    manifest_path = packet_dir / "manifest.json"
    _regular_file(manifest_path, "manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("kind") != "govPackageOutput.v1" or manifest.get("repoId") != "roccho-dev/governance":
        raise PackageOutputError("packet-manifest-identity")
    if manifest.get("nonAuthority") is not True:
        raise PackageOutputError("packet-manifest-authority")
    packet_files = manifest.get("packetFiles")
    if not isinstance(packet_files, list) or not packet_files or any(not isinstance(item, str) or not item for item in packet_files):
        raise PackageOutputError("packet-files-array")
    if len(set(packet_files)) != len(packet_files):
        raise PackageOutputError("packet-files-duplicate")
    for required in (OUTPUT_FILE, RECEIPT_FILE):
        if required not in packet_files:
            raise PackageOutputError(f"packet-file-not-declared:{required}")
    for name in packet_files:
        candidate = PurePosixPath(name)
        if candidate.is_absolute() or ".." in candidate.parts or len(candidate.parts) != 1:
            raise PackageOutputError(f"packet-file-name-invalid:{name}")
        _regular_file(packet_dir / name, f"packet-file:{name}")
    try:
        receipt = check_materialized(fixture_dir, packet_dir)
    except (ContractError, OSError, ValueError, json.JSONDecodeError) as exc:
        raise PackageOutputError(f"package-obligation-materialization:{exc}") from exc
    return {
        "kind": "governance.govPackageOutputReleaseCheck.v1",
        "status": "pass",
        "packet_dir": str(packet_dir),
        "packet_files": sorted(packet_files),
        "package_obligations_sha256": receipt["output_sha256"],
        "package_obligations_receipt_sha256": _sha256(packet_dir / RECEIPT_FILE),
        "row_count": receipt["row_count"],
        "active_package_ids": receipt["active_package_ids"],
        "target_repository": receipt["target_repository"],
        "target_commit": receipt["target_commit"],
        "authority": False,
    }


def _safe_member_name(raw: str) -> str | None:
    name = raw
    while name.startswith("./"):
        name = name[2:]
    if name in ("", "."):
        return None
    candidate = PurePosixPath(name)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise PackageOutputError(f"archive-member-path:{raw}")
    return candidate.as_posix()


def check_archive(archive_path: Path, fixture_dir: Path) -> dict[str, Any]:
    archive_path = archive_path.resolve()
    _regular_file(archive_path, "archive")
    with tempfile.TemporaryDirectory(prefix="gov-package-output-readback-") as tmp:
        output = Path(tmp) / "output"
        output.mkdir()
        seen: set[str] = set()
        with tarfile.open(archive_path, "r:gz") as archive:
            members = archive.getmembers()
            for member in members:
                name = _safe_member_name(member.name)
                if name is None:
                    continue
                if name in seen:
                    raise PackageOutputError(f"archive-member-duplicate:{name}")
                seen.add(name)
                target = output / name
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                if not member.isfile() or member.issym() or member.islnk():
                    raise PackageOutputError(f"archive-member-type:{name}")
                target.parent.mkdir(parents=True, exist_ok=True)
                source = archive.extractfile(member)
                if source is None:
                    raise PackageOutputError(f"archive-member-unreadable:{name}")
                target.write_bytes(source.read())
        report = check_directory(output, fixture_dir)
        return {
            **report,
            "packet_dir": None,
            "archive_sha256": _sha256(archive_path),
            "archive_member_count": len(seen),
        }
