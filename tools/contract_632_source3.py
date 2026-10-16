from __future__ import annotations

import copy
import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Callable

from tools.package_contract_port_common import (
    DIGEST,
    HEX40,
    canonical,
    digest,
    git_blob_file,
    need,
    read_object,
    run,
    sha256_file,
)

APPS_REVISION = "71409fa013b6cb681c0a80b4c377e4685685b690"
APPS_TREE = "f0c9f85240d37cf14e78bda93619d71280527c58"
RELEASE_TAG = "voice-ui-dist-" + APPS_REVISION
FULL_ASSET_NAME = "voice-ui-dist.zip"


def apps_preflight_binding() -> dict[str, Any]:
    repository = "roccho-dev/apps"
    artifact = "a15f4a0c481048e22461d815ead48790ba741d42e619c0088436de85f1dc2417"
    return {
        "targetId": "apps-shape-preflight",
        "targetSource": {"repository": repository, "revision": APPS_REVISION},
        "evidenceExecutor": {
            "kind": "exact-existing-release",
            "operation": "nix-build-voice-ui-dist",
            "readback": True,
            "grade": "source",
        },
        "evidenceMaterial": {
            "source": {
                "path": "packages/voice-ui/artifact.jsonl",
                "gitBlob": "44c7f74fb5d6b44d3415079b0e542c6866c86fea",
                "sha256": "sha256:0f79ee6819cb68140360b97c27486f2365a7a0ac849ef81702f0ff2536485d82",
            },
            "manifest": {
                "schema": "voice-ui-dist/2",
                "sourceKey": "apps",
                "authPath": ".envs/artifact.jsonl",
                "sha256": "sha256:c7e77a89cc911e7337f30779f6badb1b8be560c77aac688703ab0bee3a12cae7",
                "fileCount": 288,
            },
            "provenance": {
                "schema": "roccho.voice-ui-dist.release-provenance/2",
                "workflowPath": ".github/workflows/voice-ui-release.yml",
                "workflowGitBlob": "745fcda9d4204f846f5c5768e4f9863b26082337",
                "workflowRef": "roccho-dev/apps/.github/workflows/voice-ui-release.yml@refs/heads/proposals",
                "workflowSha256": "sha256:9ab58d5017e46fefff613ed16146977425c67e32b06d3244031fa9bfa7748f10",
                "inputs": {
                    "flake.lock": {
                        "path": "flake.lock",
                        "gitBlob": "c5cd1da48fe662b28676f9ae9c76c520d21d74c6",
                        "sha256": "sha256:ae08fcfa07459cda5ddaf69c480af1b51b2351b73195b5263fc006ada181970e",
                    }
                },
                "artifact": {"name": FULL_ASSET_NAME, "bytes": 62585992, "sha256": artifact},
            },
            "proof": {"prNumber": 91, "base": "proposals", "tree": APPS_TREE},
            "provider": {
                "repository": repository,
                "releaseId": 411224075,
                "releaseTag": RELEASE_TAG,
                "targetCommitish": APPS_REVISION,
                "runId": 38339283395,
                "runAttempt": 2,
                "artifactId": 11787016196,
                "artifactDigest": "sha256:f9eb3f7ec6f8ef1643c86ca8d88d069c7b8b7e08b386d203afee18ea37e9b208",
                "assets": {
                    FULL_ASSET_NAME: {"id": 635746304, "bytes": 62585992, "sha256": "sha256:" + artifact},
                    "provenance.json": {"id": 635746309, "bytes": 36366, "sha256": "sha256:43867c3dd595b30375194418e4ed0e27531ef3d0a326f96e865e80a2ad6fd615"},
                    "merged-pr-proof.json": {"id": 635746325, "bytes": 434, "sha256": "sha256:50370f82881b04ebe475afc31a9310065c6e305193a1a726497fdb1b7215f9cc"},
                },
            },
        },
    }


def full_material_root(evidence_root: Path) -> Path:
    return evidence_root.parent / f"{evidence_root.name}-full"


def _relative(value: Any, code: str) -> str:
    need(isinstance(value, str) and value and not value.startswith("/") and ".." not in value.split("/"), code)
    return value


def _tree(root: Path) -> str:
    process = run(["git", "rev-parse", "HEAD^{tree}"], root)
    need(process.returncode == 0 and HEX40.fullmatch(process.stdout.strip()) is not None, "closed-evidence-target-tree")
    return process.stdout.strip()


def prepare_target_evidence(acquire: Any, target_id: str, binding: dict[str, Any], target_source: Path, destination: Path) -> None:
    full_root = full_material_root(destination)
    if destination.exists():
        shutil.rmtree(destination)
    if full_root.exists():
        shutil.rmtree(full_root)
    kind = binding["evidenceExecutor"]["kind"]
    if kind == "adapter":
        acquire.write_adapter_evidence(target_id, binding, destination)
        return
    need(kind == "exact-existing-release", "prepare-evidence-executor")
    expected = apps_preflight_binding()
    need(binding.get("evidenceMaterial") == expected["evidenceMaterial"], "prepare-evidence-material")
    need(binding.get("targetSource", {}).get("revision") == APPS_REVISION, "prepare-evidence-candidate")
    acquire.verify_release_evidence(target_source, destination)
    need((full_root / FULL_ASSET_NAME).is_file(), "prepare-full-asset")
    path = destination / "evidence.json"
    evidence = read_object(path, "prepared-evidence")
    evidence["targetId"] = target_id
    evidence["candidate"] = binding["targetSource"]["revision"]
    evidence["executor"] = binding["evidenceExecutor"]
    evidence["receipt"]["targetId"] = target_id
    evidence["receipt"]["provider"] = binding["evidenceMaterial"]["provider"]
    path.write_text(canonical(evidence) + "\n", encoding="utf-8")


def _verify_full_asset(
    evidence_root: Path,
    material: dict[str, Any],
    target_candidate: str,
    saved_manifest: dict[str, Any],
    saved_manifest_path: Path,
    output: Path,
) -> dict[str, Any]:
    full_root = full_material_root(evidence_root)
    need(full_root.is_dir() and not full_root.is_symlink(), "closed-evidence-full-root")
    actual_material_files = {
        path.relative_to(full_root).as_posix()
        for path in full_root.rglob("*")
        if path.is_file()
    }
    need(actual_material_files == {FULL_ASSET_NAME}, "closed-evidence-full-universe")
    archive = full_root / FULL_ASSET_NAME
    provenance_spec = material["provenance"]
    provider = material["provider"]
    artifact_spec = provenance_spec["artifact"]
    asset = provider["assets"][FULL_ASSET_NAME]
    need(artifact_spec["name"] == FULL_ASSET_NAME, "closed-evidence-full-name")
    need(archive.stat().st_size == artifact_spec["bytes"] == asset["bytes"], "closed-evidence-full-bytes")
    archive_digest = sha256_file(archive)
    need(
        archive_digest == asset["sha256"] == "sha256:" + artifact_spec["sha256"],
        "closed-evidence-full-digest",
    )

    with zipfile.ZipFile(archive) as zipped:
        files = [name for name in zipped.namelist() if not name.endswith("/")]
        need(len(files) == len(set(files)), "closed-evidence-full-duplicate")
        candidates: list[tuple[str, dict[str, Any], bytes]] = []
        for name in files:
            if name == "manifest.json" or name.endswith("/manifest.json"):
                raw = zipped.read(name)
                try:
                    value = json.loads(raw)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                if isinstance(value, dict) and value.get("schema") == material["manifest"]["schema"]:
                    candidates.append((name, value, raw))
        need(len(candidates) == 1, "closed-evidence-full-manifest-cardinality")
        manifest_name, manifest, manifest_raw = candidates[0]
        need(manifest == saved_manifest and manifest_raw == saved_manifest_path.read_bytes(), "closed-evidence-full-manifest")
        need(manifest.get("sources", {}).get(material["manifest"]["sourceKey"]) == target_candidate, "closed-evidence-full-candidate")
        prefix = manifest_name[: -len("manifest.json")]
        expected_files = {manifest_name}
        rows = manifest["files"]
        for row in rows:
            relative = row["path"]
            name = prefix + relative
            raw = zipped.read(name)
            need(len(raw) == row["bytes"], "closed-evidence-full-member-bytes")
            need("sha256:" + hashlib.sha256(raw).hexdigest() == "sha256:" + row["sha256"], "closed-evidence-full-member-digest")
            expected_files.add(name)
        need(set(files) == expected_files, "closed-evidence-full-member-universe")
        need(zipped.read(prefix + manifest["auth"]) == output.read_bytes(), "closed-evidence-full-auth-body")

    return {
        "fullMaterialClosed": True,
        "fullMaterialDigest": archive_digest,
        "fullMaterialBytes": archive.stat().st_size,
        "fullMaterialFilesVerified": len(actual_material_files),
        "fullAssetMembersVerified": len(saved_manifest["files"]),
    }


def verify_closed_evidence_input(
    base_verify: Callable[..., dict[str, Any]],
    evidence_root: Path | None,
    binding: dict[str, Any],
    target_id: str,
    target_candidate: str,
    target_source: Path,
) -> dict[str, Any]:
    identity = base_verify(evidence_root, binding, target_id, target_candidate)
    root = evidence_root.resolve() if evidence_root is not None else None
    need(root is not None, "closed-evidence-root")
    full_root = full_material_root(root)
    if identity["mode"] == "adapter":
        need(not full_root.exists(), "closed-evidence-adapter-full-material")
        return {
            **identity,
            "materialClosed": True,
            "materialDigest": None,
            "fullMaterialClosed": True,
            "fullMaterialDigest": None,
            "fullMaterialBytes": 0,
            "fullMaterialFilesVerified": 0,
            "fullAssetMembersVerified": 0,
        }
    material = binding.get("evidenceMaterial")
    need(isinstance(material, dict) and set(material) == {"source", "manifest", "provenance", "proof", "provider"}, "closed-evidence-material")
    target_source = target_source.resolve()
    tree = _tree(target_source)

    source_spec = material["source"]
    native = target_source / _relative(source_spec["path"], "closed-evidence-source-path")
    source = root / "source-artifact.jsonl"
    output = root / "output-artifact.jsonl"
    need(native.is_file() and git_blob_file(native) == source_spec["gitBlob"], "closed-evidence-native-source")
    need(sha256_file(native) == source_spec["sha256"], "closed-evidence-native-digest")
    need(source.read_bytes() == native.read_bytes() == output.read_bytes(), "closed-evidence-native-projection")

    manifest_spec = material["manifest"]
    manifest_path = root / "dist-manifest.json"
    need(sha256_file(manifest_path) == manifest_spec["sha256"], "closed-evidence-manifest-digest")
    manifest = read_object(manifest_path, "closed-evidence-manifest")
    need(manifest.get("schema") == manifest_spec["schema"], "closed-evidence-manifest-schema")
    need(manifest.get("sources", {}).get(manifest_spec["sourceKey"]) == target_candidate, "closed-evidence-manifest-source")
    need(manifest.get("auth") == manifest_spec["authPath"], "closed-evidence-manifest-auth")
    rows = manifest.get("files")
    need(isinstance(rows, list) and len(rows) == manifest_spec["fileCount"], "closed-evidence-manifest-count")
    paths = [row.get("path") for row in rows if isinstance(row, dict)]
    need(len(paths) == len(rows) == len(set(paths)), "closed-evidence-manifest-universe")
    auth = [row for row in rows if row.get("path") == manifest_spec["authPath"]]
    need(len(auth) == 1 and auth[0].get("bytes") == len(output.read_bytes()), "closed-evidence-manifest-auth-row")
    need("sha256:" + str(auth[0].get("sha256")) == sha256_file(output), "closed-evidence-manifest-auth-digest")

    provenance_spec = material["provenance"]
    provenance = read_object(root / "provenance.json", "closed-evidence-provenance")
    target_repository = binding["targetSource"]["repository"]
    provider = material["provider"]
    need(provenance.get("schema") == provenance_spec["schema"], "closed-evidence-provenance-schema")
    need(provenance.get("source") == {"repository": target_repository, "commit": target_candidate, "tree": tree}, "closed-evidence-provenance-source")
    need(provenance.get("producer") == {"repository": provider["repository"], "workflow_ref": provenance_spec["workflowRef"], "run_id": provider["runId"], "run_attempt": provider["runAttempt"]}, "closed-evidence-provenance-producer")
    workflow = target_source / _relative(provenance_spec["workflowPath"], "closed-evidence-workflow-path")
    need(git_blob_file(workflow) == provenance_spec["workflowGitBlob"] and sha256_file(workflow) == provenance_spec["workflowSha256"], "closed-evidence-workflow-source")
    expected_inputs: dict[str, str] = {}
    for name, spec in provenance_spec["inputs"].items():
        input_path = target_source / _relative(spec["path"], "closed-evidence-input-path")
        need(git_blob_file(input_path) == spec["gitBlob"] and sha256_file(input_path) == spec["sha256"], "closed-evidence-input-source")
        expected_inputs[name] = spec["sha256"].removeprefix("sha256:")
    need(provenance.get("input_digests") == expected_inputs, "closed-evidence-provenance-inputs")
    need(provenance.get("artifact") == provenance_spec["artifact"], "closed-evidence-provenance-artifact")
    locator = f"https://github.com/{provider['repository']}/releases/download/{provider['releaseTag']}/{provenance_spec['artifact']['name']}"
    need(provenance.get("locator") == locator and provenance.get("cross_host_bytes_reproducible") is False, "closed-evidence-provenance-locator")

    proof_spec = material["proof"]
    proof = read_object(root / "merged-pr-proof.json", "closed-evidence-proof")
    need(proof.get("pr_number") == proof_spec["prNumber"] and proof.get("base") == proof_spec["base"], "closed-evidence-proof-pr")
    need(proof.get("merge_sha") == target_candidate, "closed-evidence-proof-merge")
    need(proof.get("reviewed_tree") == tree == proof.get("merge_tree") == proof_spec["tree"], "closed-evidence-proof-tree")
    need(HEX40.fullmatch(str(proof.get("reviewed_head"))) is not None and proof.get("merged_at") and proof.get("r_exact_head_verdict_ref"), "closed-evidence-proof-complete")

    receipt = identity.get("receipt")
    need(isinstance(receipt, dict) and receipt.get("kind") == "governance.packageContractBuildReceipt.v2", "closed-evidence-receipt")
    need(receipt.get("authority") is False and receipt.get("targetId") == target_id, "closed-evidence-receipt-boundary")
    need(receipt.get("provider") == provider, "closed-evidence-provider")
    asset = provider["assets"][provenance_spec["artifact"]["name"]]
    need(asset["bytes"] == provenance_spec["artifact"]["bytes"] and asset["sha256"] == "sha256:" + provenance_spec["artifact"]["sha256"], "closed-evidence-provider-artifact")
    full = _verify_full_asset(root, material, target_candidate, manifest, manifest_path, output)
    return {
        **identity,
        "materialClosed": True,
        "materialDigest": digest(material),
        "targetTree": tree,
        "manifestFilesVerified": len(rows),
        **full,
    }


def _rewrite_digest(root: Path, name: str, receipt_key: str) -> None:
    evidence_path = root / "evidence.json"
    evidence = read_object(evidence_path, "negative-evidence")
    evidence["receipt"][receipt_key] = sha256_file(root / name)
    evidence_path.write_text(canonical(evidence) + "\n", encoding="utf-8")


def verify_exact_release_negatives(
    base_verify: Callable[..., dict[str, Any]],
    binding: dict[str, Any],
    target_source: Path,
    evidence_root: Path,
) -> dict[str, Any]:
    closed = verify_closed_evidence_input(
        base_verify,
        evidence_root,
        binding,
        binding["targetId"],
        APPS_REVISION,
        target_source,
    )
    rejected: dict[str, Any] = {
        "fullAssetBodyVerified": closed["fullMaterialClosed"],
        "fullAssetDigest": closed["fullMaterialDigest"],
        "fullAssetBytesVerified": closed["fullMaterialBytes"],
        "fullMaterialFilesVerified": closed["fullMaterialFilesVerified"],
        "fullAssetMembersVerified": closed["fullAssetMembersVerified"],
    }

    def check(name: str, mutate: Callable[[Path], None]) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "evidence"
            shutil.copytree(evidence_root, root)
            source_full = full_material_root(evidence_root)
            if source_full.exists():
                shutil.copytree(source_full, full_material_root(root))
            mutate(root)
            try:
                verify_closed_evidence_input(base_verify, root, binding, binding["targetId"], APPS_REVISION, target_source)
            except (ValueError, FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError, zipfile.BadZipFile, KeyError):
                rejected[name] = True
            else:
                raise ValueError("source3-negative-unexpected-pass:" + name)

    def wrong_body(root: Path) -> None:
        raw = b'{"wrong":true}\n'
        (root / "source-artifact.jsonl").write_bytes(raw)
        (root / "output-artifact.jsonl").write_bytes(raw)
        manifest = read_object(root / "dist-manifest.json", "negative-manifest")
        for row in manifest["files"]:
            if row["path"] == manifest["auth"]:
                row["bytes"] = len(raw)
                row["sha256"] = hashlib.sha256(raw).hexdigest()
        (root / "dist-manifest.json").write_text(canonical(manifest) + "\n", encoding="utf-8")
        for name, key in (("source-artifact.jsonl", "sourceDigest"), ("output-artifact.jsonl", "outputDigest"), ("dist-manifest.json", "manifestDigest")):
            _rewrite_digest(root, name, key)

    def wrong_provenance(root: Path) -> None:
        value = read_object(root / "provenance.json", "negative-provenance")
        value["source"]["tree"] = "0" * 40
        (root / "provenance.json").write_text(canonical(value) + "\n", encoding="utf-8")
        _rewrite_digest(root, "provenance.json", "provenanceDigest")

    def wrong_producer(root: Path) -> None:
        value = read_object(root / "provenance.json", "negative-producer")
        value["producer"]["run_id"] = 0
        (root / "provenance.json").write_text(canonical(value) + "\n", encoding="utf-8")
        _rewrite_digest(root, "provenance.json", "provenanceDigest")

    def wrong_provider(root: Path) -> None:
        path = root / "evidence.json"
        value = read_object(path, "negative-provider")
        value["receipt"]["provider"]["releaseTag"] = "wrong"
        path.write_text(canonical(value) + "\n", encoding="utf-8")

    def wrong_proof(root: Path) -> None:
        value = read_object(root / "merged-pr-proof.json", "negative-proof")
        value["reviewed_tree"] = value["merge_tree"] = "0" * 40
        (root / "merged-pr-proof.json").write_text(canonical(value) + "\n", encoding="utf-8")
        _rewrite_digest(root, "merged-pr-proof.json", "proofDigest")

    def wrong_full_asset(root: Path) -> None:
        path = full_material_root(root) / FULL_ASSET_NAME
        raw = bytearray(path.read_bytes())
        raw[len(raw) // 2] ^= 1
        path.write_bytes(raw)

    def missing_full_asset(root: Path) -> None:
        (full_material_root(root) / FULL_ASSET_NAME).unlink()

    check("selfConsistentWrongBody", wrong_body)
    check("wrongProvenanceTree", wrong_provenance)
    check("wrongProducer", wrong_producer)
    check("wrongProviderIdentity", wrong_provider)
    check("wrongProofTree", wrong_proof)
    check("fullAssetTamper", wrong_full_asset)
    check("missingFullAsset", missing_full_asset)
    return rejected
