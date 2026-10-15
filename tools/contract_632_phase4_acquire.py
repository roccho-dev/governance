#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import subprocess
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TARGET_DIR = ROOT / "tools/package_contract_targets"
APPS_REVISION = "71409fa013b6cb681c0a80b4c377e4685685b690"
APPS_TREE = "f0c9f85240d37cf14e78bda93619d71280527c58"
RUNTIME_REVISION = "5eb98c82417b399978c1e38aebab5e3fb39752d4"
ADRS_REVISION = "862313008ad19a743034599792d9a8b6e470e4cf"
RELEASE_TAG = "voice-ui-dist-" + APPS_REVISION
RELEASE_API = f"https://api.github.com/repos/roccho-dev/apps/releases/tags/{RELEASE_TAG}"
EXPECTED_RELEASE_ASSETS = {
    "voice-ui-dist.zip": {"id": 635746304, "bytes": 62585992, "sha256": "a15f4a0c481048e22461d815ead48790ba741d42e619c0088436de85f1dc2417"},
    "provenance.json": {"id": 635746309, "bytes": 36366, "sha256": "43867c3dd595b30375194418e4ed0e27531ef3d0a326f96e865e80a2ad6fd615"},
    "merged-pr-proof.json": {"id": 635746325, "bytes": 434, "sha256": "50370f82881b04ebe475afc31a9310065c6e305193a1a726497fdb1b7215f9cc"},
}
EXPECTED_MANIFEST_SHA256 = "c7e77a89cc911e7337f30779f6badb1b8be560c77aac688703ab0bee3a12cae7"
EXPECTED_DECLARATION_SHA256 = "0f79ee6819cb68140360b97c27486f2365a7a0ac849ef81702f0ff2536485d82"
EXPECTED_FLAKE_LOCK_SHA256 = "ae08fcfa07459cda5ddaf69c480af1b51b2351b73195b5263fc006ada181970e"
EXPECTED_RELEASE_WORKFLOW_SHA256 = "9ab58d5017e46fefff613ed16146977425c67e32b06d3244031fa9bfa7748f10"


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def run(args: list[str], cwd: Path | None = None) -> str:
    process = subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.returncode:
        raise SystemExit("command-failed:" + " ".join(args[:3]) + ":" + process.stderr)
    return process.stdout.strip()


def sha_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha(path: Path) -> str:
    return "sha256:" + sha_bytes(path.read_bytes())


def git_blob(path: Path) -> str:
    raw = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def request_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "contract-632"})
    with urllib.request.urlopen(request, timeout=60) as response:
        value = json.load(response)
    if not isinstance(value, dict):
        raise SystemExit("release-json-shape")
    return value


def download(url: str, destination: Path) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "contract-632"})
    digest = hashlib.sha256()
    size = 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(request, timeout=180) as response, destination.open("wb") as output:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)
            digest.update(chunk)
            size += len(chunk)
    return {"bytes": size, "sha256": digest.hexdigest()}


def clone(source: dict[str, Any], destination: Path, tokens: dict[str, str]) -> dict[str, Any]:
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
    run(command, destination)
    run(["git", "checkout", "--detach", "FETCH_HEAD"], destination)
    actual = run(["git", "rev-parse", "HEAD"], destination)
    if actual != source["revision"]:
        raise SystemExit("revision-mismatch:" + actual)
    return {"repository": source["repository"], "revision": actual, "tree": run(["git", "rev-parse", "HEAD^{tree}"], destination), "accessClass": access, "path": destination.as_posix()}


def bindings() -> dict[str, dict[str, Any]]:
    return {path.name[: -len(".target.json")]: json.loads(path.read_text(encoding="utf-8")) for path in sorted(TARGET_DIR.glob("*.target.json"))}


def discover(args: argparse.Namespace) -> None:
    targets = sorted(bindings())
    if not targets or "ops" not in targets:
        raise SystemExit("target-set")
    Path(args.out).write_text(canonical({"kind": "governance.packageContractTargets.v1", "targets": targets}) + "\n", encoding="utf-8")


def acquire(args: argparse.Namespace) -> None:
    tokens = {"public-read": "", "same-repo-read": os.environ.get("SAME_REPO_TOKEN", ""), "adrs-reader-v1": os.environ.get("ADRS_READER_TOKEN", "")}
    rows: list[dict[str, Any]] = []
    for target, binding in bindings().items():
        for role in ("targetSource", "acceptedRequirementSource", "governancePolicySource", "contractRuntimeSource"):
            rows.append({"targetId": target, "role": role, **clone(binding[role], Path("_sources") / target / role, tokens)})
    fixed = {
        "target": {"repository": "roccho-dev/apps", "revision": APPS_REVISION, "accessClass": "public-read"},
        "runtime": {"repository": "roccho-org/ops", "revision": RUNTIME_REVISION, "accessClass": "public-read"},
        "accepted": {"repository": "roccho-dev/adrs", "revision": ADRS_REVISION, "accessClass": "adrs-reader-v1"},
    }
    for role, source in fixed.items():
        rows.append({"targetId": "apps-shape-preflight", "role": role, **clone(source, Path("_preflight") / role, tokens)})
    Path(args.out).write_text(canonical({"kind": "governance.packageContractSourceAcquisition.v2", "authority": False, "rows": rows}) + "\n", encoding="utf-8")


def write_adapter_evidence(target: str, binding: dict[str, Any], destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    evidence = {"kind": "governance.packageContractEvidenceInput.v1", "authority": False, "targetId": target, "candidate": binding["targetSource"]["revision"], "mode": "adapter", "executor": binding["evidenceExecutor"]}
    (destination / "evidence.json").write_text(canonical(evidence) + "\n", encoding="utf-8")


def find_dist_manifest(zipped: zipfile.ZipFile) -> tuple[str, dict[str, Any]]:
    candidates: list[tuple[str, dict[str, Any]]] = []
    for name in zipped.namelist():
        if name == "manifest.json" or name.endswith("/manifest.json"):
            try:
                value = json.loads(zipped.read(name))
            except (KeyError, json.JSONDecodeError, UnicodeDecodeError):
                continue
            if isinstance(value, dict) and value.get("schema") == "voice-ui-dist/2":
                candidates.append((name, value))
    if len(candidates) != 1:
        raise SystemExit("release-dist-manifest-cardinality")
    return candidates[0]


def verify_release_evidence(target_root: Path, destination: Path) -> None:
    if run(["git", "rev-parse", "HEAD"], target_root) != APPS_REVISION:
        raise SystemExit("release-target-revision")
    if run(["git", "rev-parse", "HEAD^{tree}"], target_root) != APPS_TREE:
        raise SystemExit("release-target-tree")
    release = request_json(RELEASE_API)
    if release.get("tag_name") != RELEASE_TAG or release.get("target_commitish") != APPS_REVISION:
        raise SystemExit("release-identity")
    assets = {row.get("name"): row for row in release.get("assets", []) if isinstance(row, dict)}
    work = destination / "download"
    work.mkdir(parents=True, exist_ok=True)
    observed_assets: dict[str, Any] = {}
    for name, expected in EXPECTED_RELEASE_ASSETS.items():
        asset = assets.get(name)
        if not isinstance(asset, dict):
            raise SystemExit("release-asset-missing:" + name)
        if asset.get("id") != expected["id"] or asset.get("size") != expected["bytes"] or asset.get("digest") != "sha256:" + expected["sha256"]:
            raise SystemExit("release-asset-metadata:" + name)
        path = work / name
        actual = download(str(asset["browser_download_url"]), path)
        if actual != {"bytes": expected["bytes"], "sha256": expected["sha256"]}:
            raise SystemExit("release-asset-body:" + name)
        observed_assets[name] = {"id": expected["id"], "bytes": actual["bytes"], "sha256": "sha256:" + actual["sha256"]}

    archive = work / "voice-ui-dist.zip"
    with zipfile.ZipFile(archive) as zipped:
        manifest_name, manifest = find_dist_manifest(zipped)
        manifest_bytes = zipped.read(manifest_name)
        if sha_bytes(manifest_bytes) != EXPECTED_MANIFEST_SHA256:
            raise SystemExit("release-manifest-digest")
        if manifest.get("sources", {}).get("apps") != APPS_REVISION:
            raise SystemExit("release-manifest-candidate")
        auth_path = manifest.get("auth")
        if auth_path != ".envs/artifact.jsonl":
            raise SystemExit("release-manifest-auth")
        rows = manifest.get("files")
        if not isinstance(rows, list) or not rows:
            raise SystemExit("release-manifest-files")
        prefix = manifest_name[: -len("manifest.json")]
        expected_files = {manifest_name}
        for row in rows:
            if not isinstance(row, dict) or set(row) != {"path", "bytes", "sha256"}:
                raise SystemExit("release-manifest-row")
            relative = row["path"]
            if not isinstance(relative, str) or relative.startswith("/") or ".." in relative.split("/"):
                raise SystemExit("release-manifest-path")
            name = prefix + relative
            raw = zipped.read(name)
            if len(raw) != row["bytes"] or sha_bytes(raw) != row["sha256"]:
                raise SystemExit("release-manifest-member:" + relative)
            expected_files.add(name)
        actual_files = {name for name in zipped.namelist() if not name.endswith("/")}
        if actual_files != expected_files:
            raise SystemExit("release-manifest-universe")
        output_bytes = zipped.read(prefix + auth_path)

    source = target_root / "packages/voice-ui/artifact.jsonl"
    source_bytes = source.read_bytes()
    if sha_bytes(source_bytes) != EXPECTED_DECLARATION_SHA256 or source_bytes != output_bytes:
        raise SystemExit("release-declaration-projection")
    provenance_path = work / "provenance.json"
    proof_path = work / "merged-pr-proof.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    source_identity = provenance.get("source", {})
    producer = provenance.get("producer", {})
    artifact = provenance.get("artifact", {})
    input_digests = provenance.get("input_digests", {})
    if source_identity != {"repository": "roccho-dev/apps", "commit": APPS_REVISION, "tree": APPS_TREE}:
        raise SystemExit("release-provenance-source")
    if producer.get("repository") != "roccho-dev/apps" or str(producer.get("run_id")) != "38339283395" or str(producer.get("run_attempt")) != "2" or not isinstance(producer.get("workflow_ref"), str):
        raise SystemExit("release-provenance-producer")
    if artifact.get("name") != "voice-ui-dist.zip" or artifact.get("bytes") != EXPECTED_RELEASE_ASSETS["voice-ui-dist.zip"]["bytes"] or artifact.get("sha256") != EXPECTED_RELEASE_ASSETS["voice-ui-dist.zip"]["sha256"]:
        raise SystemExit("release-provenance-artifact")
    if input_digests.get("flake.lock") != EXPECTED_FLAKE_LOCK_SHA256:
        raise SystemExit("release-provenance-lock")
    if sha_bytes((target_root / "flake.lock").read_bytes()) != EXPECTED_FLAKE_LOCK_SHA256:
        raise SystemExit("release-lock-source")
    if sha_bytes((target_root / ".github/workflows/voice-ui-release.yml").read_bytes()) != EXPECTED_RELEASE_WORKFLOW_SHA256:
        raise SystemExit("release-workflow-source")
    if proof.get("merge_sha") != APPS_REVISION or proof.get("reviewed_tree") != APPS_TREE or proof.get("merge_tree") != APPS_TREE or not proof.get("merged_at") or not proof.get("r_exact_head_verdict_ref"):
        raise SystemExit("release-proof")

    destination.mkdir(parents=True, exist_ok=True)
    (destination / "source-artifact.jsonl").write_bytes(source_bytes)
    (destination / "output-artifact.jsonl").write_bytes(output_bytes)
    (destination / "dist-manifest.json").write_bytes(manifest_bytes)
    shutil.copy2(provenance_path, destination / "provenance.json")
    shutil.copy2(proof_path, destination / "merged-pr-proof.json")
    executor = {"kind": "exact-existing-release", "operation": "nix-build-voice-ui-dist", "readback": True, "grade": "source"}
    receipt = {
        "kind": "governance.packageContractBuildReceipt.v2",
        "authority": False,
        "targetId": "apps-shape-preflight",
        "candidate": APPS_REVISION,
        "operation": executor["operation"],
        "grade": executor["grade"],
        "status": "PASS",
        "readback": "PASS",
        "sourceDigest": "sha256:" + EXPECTED_DECLARATION_SHA256,
        "outputDigest": "sha256:" + EXPECTED_DECLARATION_SHA256,
        "manifestDigest": "sha256:" + EXPECTED_MANIFEST_SHA256,
        "provenanceDigest": "sha256:" + EXPECTED_RELEASE_ASSETS["provenance.json"]["sha256"],
        "proofDigest": "sha256:" + EXPECTED_RELEASE_ASSETS["merged-pr-proof.json"]["sha256"],
        "provider": {"repository": "roccho-dev/apps", "releaseTag": RELEASE_TAG, "runId": 38339283395, "runAttempt": 2, "artifactId": 11787016196, "artifactDigest": "sha256:f9eb3f7ec6f8ef1643c86ca8d88d069c7b8b7e08b386d203afee18ea37e9b208", "assets": observed_assets},
    }
    evidence = {"kind": "governance.packageContractEvidenceInput.v1", "authority": False, "targetId": "apps-shape-preflight", "candidate": APPS_REVISION, "mode": "exact-existing-release", "executor": executor, "receipt": receipt}
    (destination / "evidence.json").write_text(canonical(evidence) + "\n", encoding="utf-8")
    shutil.rmtree(work)


def prepare(args: argparse.Namespace) -> None:
    for target, binding in bindings().items():
        write_adapter_evidence(target, binding, Path("_evidence") / target)
    verify_release_evidence(Path("_preflight/target"), Path("_preflight/evidence"))


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("discover")
    p.add_argument("--out", required=True)
    p = sub.add_parser("acquire")
    p.add_argument("--out", required=True)
    sub.add_parser("prepare")
    args = parser.parse_args()
    {"discover": discover, "acquire": acquire, "prepare": prepare}[args.command](args)


if __name__ == "__main__":
    main()
