#!/usr/bin/env python3
"""Project README artifact policy/model data without rendering or uploading artifacts."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECTOR_VERSION = "govlib-readme-artifact.v1"
REQUIRED_SLOTS = [
    "Purpose",
    "Authority boundary",
    "Inputs",
    "Outputs / artifacts",
    "Checks",
    "Ownership / handoff",
]


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"{path}: expected JSON object")
    return value


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 1


def validate(bundle: dict[str, Any], manifest: dict[str, Any]) -> str | None:
    if bundle.get("status") != "Accepted":
        return "accepted ADR bundle must have status Accepted"
    if bundle.get("uri") != "doc://adrs/readme-artifact-library-boundaries":
        return "accepted ADR bundle uri is not the README artifact boundary"
    if bundle.get("raw_rows"):
        return "raw ADR rows are not final authority input for gov-lib"
    if bundle.get("unknown_policy_inputs"):
        return "unknown policy input must fail closed"
    source_digest = bundle.get("source_digest")
    if not isinstance(source_digest, str) or not source_digest:
        return "accepted ADR bundle requires source_digest"
    if manifest.get("kind") != "repo.readmeArtifactConsumerManifest.v1":
        return "manifest kind must be repo.readmeArtifactConsumerManifest.v1"
    if manifest.get("capsule_digest") != source_digest:
        return "manifest capsule_digest must match accepted bundle source_digest"
    if manifest.get("projector_version") != PROJECTOR_VERSION:
        return f"manifest projector_version must be {PROJECTOR_VERSION}"
    required_slots = bundle.get("policy_facts", {}).get("required_slots")
    if not isinstance(required_slots, list):
        return "policy_facts.required_slots is required"
    missing = [slot for slot in REQUIRED_SLOTS if slot not in required_slots]
    if missing:
        return "required README slots missing from accepted policy facts: " + ", ".join(missing)
    return None


def project(bundle: dict[str, Any], manifest: dict[str, Any], out: Path) -> None:
    repo = manifest["repo"]
    profile = manifest.get("profile", "library")
    source_digest = bundle["source_digest"]
    required_slots = bundle["policy_facts"]["required_slots"]
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "readme.policy.capsule.json", {
        "kind": "governance.readmePolicyCapsule.v1",
        "repo": repo,
        "profile": profile,
        "projector_version": PROJECTOR_VERSION,
        "source_digest": source_digest,
        "severity": manifest.get("severity", "blocking"),
        "required_slots": required_slots,
        "gates": ["readme-required-slots", "source-closure", "no-markdown-rendering", "no-artifact-ownership"],
        "policy_facts": bundle.get("policy_facts", {}),
    })
    write_json(out / "repo.explain.model.json", {
        "kind": "governance.repoExplainModel.v1",
        "repo": repo,
        "profile": profile,
        "projector_version": PROJECTOR_VERSION,
        "document_model": {
            "kind": "document.model.v1",
            "sections": [{"title": slot, "required": True} for slot in required_slots],
        },
    })
    (out / "diagnostics.jsonl").write_text("", encoding="utf-8")
    (out / "source-closure.jsonl").write_text(
        json.dumps({
            "kind": "governance.sourceClosure.v1",
            "repo": repo,
            "uri": bundle["uri"],
            "source_digest": source_digest,
        }, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--accepted-bundle", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    bundle = read_json(args.accepted_bundle)
    manifest = read_json(args.manifest)
    error = validate(bundle, manifest)
    if error:
        return fail(error)
    project(bundle, manifest, args.out)
    forbidden = ["README.md", "README", "artifact.zip", "artifact.tar", "rendered.md"]
    written = {p.name for p in args.out.iterdir()}
    leaked = sorted(written.intersection(forbidden))
    if leaked:
        return fail("gov-lib must not render or own artifact files: " + ", ".join(leaked))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
