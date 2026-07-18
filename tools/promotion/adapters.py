from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Iterable

from .core import PromotionError, canonical


class FileSource:
    def __init__(self, root: Path):
        self.root = root

    def read_events(self) -> Iterable[dict[str, Any]]:
        for path in sorted((self.root / "events").glob("*.json")):
            yield json.loads(path.read_text(encoding="utf-8"))


class FileWriter:
    def __init__(self, root: Path):
        self.root = root

    @staticmethod
    def _append_exact(path: Path, content: bytes) -> None:
        if path.exists():
            if path.read_bytes() != content:
                raise PromotionError(f"append-only-conflict:{path.name}")
            return
        path.write_bytes(content)

    def append(self, event: dict[str, Any], signature: bytes, receipt: dict[str, Any]) -> None:
        for directory in ["events", "signatures", "receipts"]:
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        name = f"{event['promotionId']}.json"
        self._append_exact(self.root / "events" / name, canonical(event) + b"\n")
        self._append_exact(self.root / "signatures" / (name + ".sig"), signature.hex().encode() + b"\n")
        self._append_exact(self.root / "receipts" / name, canonical(receipt) + b"\n")


class GenericGitRemote:
    def __init__(self, remote: str, ref: str = "refs/heads/governance-promotions"):
        self.remote = remote
        self.ref = ref

    @staticmethod
    def _run(args: list[str], cwd: Path | None = None, *, check: bool = True) -> str:
        proc = subprocess.run(
            args,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if check and proc.returncode:
            raise PromotionError(proc.stdout.strip() or "git-command-failed")
        return proc.stdout.strip()

    def _remote_ref_exists(self) -> bool:
        proc = subprocess.run(
            ["git", "ls-remote", "--exit-code", self.remote, self.ref],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if proc.returncode not in {0, 2}:
            raise PromotionError(proc.stdout.strip() or "git-ls-remote-failed")
        return proc.returncode == 0

    @staticmethod
    def _tracked_paths(root: Path) -> list[Path]:
        paths: list[Path] = []
        for directory in ["events", "signatures", "receipts"]:
            base = root / directory
            if base.exists():
                paths.extend(path for path in base.rglob("*") if path.is_file())
        return sorted(paths)

    @classmethod
    def _require_remote_history_preserved(cls, remote_tree: Path, proposed_tree: Path) -> None:
        for existing in cls._tracked_paths(remote_tree):
            relative = existing.relative_to(remote_tree)
            proposed = proposed_tree / relative
            if not proposed.exists():
                raise PromotionError(f"history-deletion:{relative.as_posix()}")
            if proposed.read_bytes() != existing.read_bytes():
                raise PromotionError(f"history-rewrite:{relative.as_posix()}")

    @classmethod
    def _copy_tree(cls, source: Path, destination: Path) -> None:
        for directory in ["events", "signatures", "receipts"]:
            source_dir = source / directory
            destination_dir = destination / directory
            destination_dir.mkdir(parents=True, exist_ok=True)
            if source_dir.exists():
                for path in sorted(source_dir.rglob("*")):
                    if not path.is_file():
                        continue
                    relative = path.relative_to(source_dir)
                    target = destination_dir / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(path.read_bytes())

    def publish(self, tree: Path, worktree: Path) -> str:
        if worktree.exists():
            shutil.rmtree(worktree)
        exists = self._remote_ref_exists()
        if exists:
            self._run(["git", "clone", "--no-checkout", self.remote, str(worktree)])
            self._run(["git", "fetch", "origin", self.ref], worktree)
            self._run(["git", "checkout", "-B", "governance-promotions", "FETCH_HEAD"], worktree)
            self._require_remote_history_preserved(worktree, tree)
        else:
            worktree.mkdir(parents=True)
            self._run(["git", "init"], worktree)
            self._run(["git", "remote", "add", "origin", self.remote], worktree)
            self._run(["git", "checkout", "--orphan", "governance-promotions"], worktree)
        self._run(["git", "config", "user.name", "promotion-publisher"], worktree)
        self._run(["git", "config", "user.email", "promotion@invalid"], worktree)
        self._copy_tree(tree, worktree)
        self._run(["git", "add", "events", "signatures", "receipts"], worktree)
        status = self._run(["git", "status", "--porcelain"], worktree)
        if status:
            self._run(["git", "commit", "-m", "append signed promotion"], worktree)
            self._run(["git", "push", "origin", f"HEAD:{self.ref}"], worktree)
        return self._run(["git", "rev-parse", "HEAD"], worktree)

    def clone_readback(self, destination: Path) -> str:
        if destination.exists():
            shutil.rmtree(destination)
        branch = self.ref.removeprefix("refs/heads/")
        self._run(["git", "clone", "--branch", branch, self.remote, str(destination)])
        return self._run(["git", "rev-parse", "HEAD"], destination)
