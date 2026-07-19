#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.gov_release.core import (  # noqa: E402
    digest,
    make_engine_descriptor,
    make_manifest,
    make_nix_output_descriptor,
    reduce_manifests,
    validate_manifest,
    validate_readback,
)


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"not-object:{path}")
    return value


def nullable_digest(value: str) -> str | None:
    return None if value in {"", "null", "none"} else value


def write(path: Path | None, value: dict) -> None:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    print(text, end="")


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    engine = subparsers.add_parser("engine-descriptor")
    engine.add_argument("--repository", required=True)
    engine.add_argument("--commit-sha", required=True)
    engine.add_argument("--out", type=Path)

    nix = subparsers.add_parser("nix-descriptor")
    nix.add_argument("--package", required=True)
    nix.add_argument("--nar-hash", required=True)
    nix.add_argument("--out", type=Path)

    manifest = subparsers.add_parser("manifest")
    manifest.add_argument("--release-id", required=True)
    manifest.add_argument("--sequence", required=True, type=int)
    manifest.add_argument("--previous-release-digest", default="null")
    manifest.add_argument("--supersedes-release-digest", default="null")
    manifest.add_argument("--accepted-decision-digest", required=True)
    manifest.add_argument("--engine-descriptor", type=Path, required=True)
    manifest.add_argument("--nix-descriptor", type=Path, required=True)
    manifest.add_argument("--out", type=Path)

    validate = subparsers.add_parser("validate")
    validate.add_argument("--manifest", type=Path, required=True)
    validate.add_argument("--out", type=Path)

    reduce_parser = subparsers.add_parser("reduce")
    reduce_parser.add_argument("--manifests", type=Path, required=True)
    reduce_parser.add_argument("--out", type=Path)

    readback = subparsers.add_parser("readback")
    readback.add_argument("--manifest", type=Path, required=True)
    readback.add_argument("--receipt", type=Path, required=True)
    readback.add_argument("--out", type=Path)

    args = parser.parse_args()
    if args.command == "engine-descriptor":
        value = make_engine_descriptor(repository=args.repository, commit_sha=args.commit_sha)
    elif args.command == "nix-descriptor":
        value = make_nix_output_descriptor(package=args.package, nar_hash=args.nar_hash)
    elif args.command == "manifest":
        engine_descriptor = read_json(args.engine_descriptor)
        nix_descriptor = read_json(args.nix_descriptor)
        value = make_manifest(
            release_id=args.release_id,
            sequence=args.sequence,
            previous_release_digest=nullable_digest(args.previous_release_digest),
            supersedes_release_digest=nullable_digest(args.supersedes_release_digest),
            accepted_decision_digest=args.accepted_decision_digest,
            gov_engine_digest=digest(engine_descriptor),
            nix_output_digest=digest(nix_descriptor),
        )
    elif args.command == "validate":
        value = {
            "kind": "govReleaseManifestValidation.v1",
            "status": "pass",
            "releaseDigest": validate_manifest(read_json(args.manifest)),
            "authority": False,
        }
    elif args.command == "reduce":
        manifests = [
            json.loads(line)
            for line in args.manifests.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        value = reduce_manifests(manifests)
    else:
        value = validate_readback(read_json(args.receipt), read_json(args.manifest))
    write(args.out, value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
