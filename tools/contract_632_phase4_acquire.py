#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET_DIR = ROOT / "tools/package_contract_targets"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def run(args, cwd=None):
    process = subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.returncode:
        raise SystemExit("command-failed:" + " ".join(args[:3]) + ":" + process.stderr)
    return process.stdout.strip()


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def clone(source, destination: Path, tokens):
    access = source["accessClass"]
    token = tokens.get(access)
    if token is None or (access != "public-read" and not token):
        raise SystemExit("access-token-missing:" + access)
    destination.parent.mkdir(parents=True, exist_ok=True)
    run(["git", "init", str(destination)])
    run(["git", "remote", "add", "origin", f"https://github.com/{source['repository']}.git"], destination)
    command = ["git"]
    if token:
        encoded = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        command += ["-c", f"http.https://github.com/.extraheader=AUTHORIZATION: basic {encoded}"]
    command += ["fetch", "--depth=1", "origin", source["revision"]]
    run(command, destination); run(["git", "checkout", "--detach", "FETCH_HEAD"], destination)
    actual = run(["git", "rev-parse", "HEAD"], destination)
    if actual != source["revision"]:
        raise SystemExit("revision-mismatch:" + actual)
    return {"repository": source["repository"], "revision": actual, "tree": run(["git", "rev-parse", "HEAD^{tree}"], destination), "accessClass": access, "path": destination.as_posix()}


def bindings():
    return {path.name[: -len(".target.json")]: json.loads(path.read_text()) for path in sorted(TARGET_DIR.glob("*.target.json"))}


def discover(args):
    targets = sorted(bindings())
    if not targets or "ops" not in targets:
        raise SystemExit("target-set")
    Path(args.out).write_text(canonical({"kind": "governance.packageContractTargets.v1", "targets": targets}) + "\n")


def acquire(args):
    tokens = {"public-read": "", "same-repo-read": os.environ.get("SAME_REPO_TOKEN", ""), "adrs-reader-v1": os.environ.get("ADRS_READER_TOKEN", "")}
    rows = []
    for target, binding in bindings().items():
        for role in ("targetSource", "acceptedRequirementSource", "governancePolicySource", "contractRuntimeSource"):
            rows.append({"targetId": target, "role": role, **clone(binding[role], Path("_sources") / target / role, tokens)})
    fixed = {
        "target": {"repository": "roccho-dev/apps", "revision": "71409fa013b6cb681c0a80b4c377e4685685b690", "accessClass": "public-read"},
        "runtime": {"repository": "roccho-org/ops", "revision": "5eb98c82417b399978c1e38aebab5e3fb39752d4", "accessClass": "public-read"},
        "accepted": {"repository": "roccho-dev/adrs", "revision": "862313008ad19a743034599792d9a8b6e470e4cf", "accessClass": "adrs-reader-v1"},
    }
    for role, source in fixed.items():
        rows.append({"targetId": "apps-shape-preflight", "role": role, **clone(source, Path("_preflight") / role, tokens)})
    Path(args.out).write_text(canonical({"kind": "governance.packageContractSourceAcquisition.v2", "authority": False, "rows": rows}) + "\n")


def build_receipt(target: str, binding, root: Path, destination: Path):
    executor = binding["evidenceExecutor"]
    destination.mkdir(parents=True, exist_ok=True)
    if executor["kind"] == "adapter":
        (destination / "executor.json").write_text(canonical({"kind": "adapter-owned", "authority": False, "targetId": target}) + "\n")
        return
    output = Path(run(["nix", "build", "--no-link", "--print-out-paths", f"path:{root.resolve()}#voice-ui-dist"]))
    source = root / "packages/voice-ui/artifact.jsonl"
    projected = output / ".envs/artifact.jsonl"
    manifest = output / "manifest.json"
    if not source.is_file() or not projected.is_file() or not manifest.is_file() or source.read_bytes() != projected.read_bytes():
        raise SystemExit("voice-ui-dist-projection")
    shutil.copy2(source, destination / "source-artifact.jsonl")
    shutil.copy2(projected, destination / "output-artifact.jsonl")
    shutil.copy2(manifest, destination / "dist-manifest.json")
    receipt = {
        "kind": "governance.packageContractBuildReceipt.v1", "authority": False,
        "targetId": target, "candidate": binding["targetSource"]["revision"],
        "operation": executor["operation"], "grade": executor["grade"],
        "status": "PASS", "readback": "PASS", "outputStorePath": str(output),
        "sourceDigest": sha(source), "outputDigest": sha(projected), "manifestDigest": sha(manifest),
    }
    (destination / "build-receipt.json").write_text(canonical(receipt) + "\n")


def prepare(args):
    for target, binding in bindings().items():
        build_receipt(target, binding, Path("_sources") / target / "targetSource", Path("_evidence") / target)
    preflight_binding = {
        "targetSource": {"revision": "71409fa013b6cb681c0a80b4c377e4685685b690"},
        "evidenceExecutor": {"kind": "nix-build-voice-ui-dist", "operation": "nix-build-voice-ui-dist", "readback": True, "grade": "source"},
    }
    build_receipt("apps-shape-preflight", preflight_binding, Path("_preflight/target"), Path("_preflight/evidence"))


def main():
    parser = argparse.ArgumentParser(); sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("discover"); p.add_argument("--out", required=True)
    p = sub.add_parser("acquire"); p.add_argument("--out", required=True)
    sub.add_parser("prepare")
    args = parser.parse_args(); {"discover": discover, "acquire": acquire, "prepare": prepare}[args.command](args)


if __name__ == "__main__":
    main()
