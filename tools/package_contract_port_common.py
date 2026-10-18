from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TARGET_DIR = ROOT / "tools/package_contract_targets"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
TARGET_ID = re.compile(r"^[a-z][a-z0-9-]*$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
STATUS_EXIT = {"CLOSED": 0, "OPEN": 2, "INVALID": 3, "UNKNOWN": 4}
REQUIRED_NEGATIVE = {
    "contract-drift": "OPEN",
    "missing-observation": "OPEN",
    "wrong-candidate": "OPEN",
    "missing-admission": "UNKNOWN",
}
COMMON_CHECKER_PATH = "tools/check-package-contract-closure-bundle.py"
RUNTIME_ROLES = ("comparatorCli", "comparatorCore")


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def git_blob_file(path: Path) -> str:
    raw = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def digest(value: Any) -> str:
    return sha256_bytes(canonical(value).encode())


def read_object(path: Path, label: str) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(label + "-not-object")
    return value


def need(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError("package-contract-bundle:" + code)


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def check_token(value: str) -> str:
    token = value.replace(" / ", "/").replace(" ", "")
    need(token != "" and " " not in token, "check-token")
    return token


def _inside_root(path: Path) -> bool:
    try:
        path.resolve().relative_to(ROOT)
        return True
    except ValueError:
        return False


def validate_provider_relation(binding: dict[str, Any]) -> None:
    target = binding.get("targetSource")
    need(isinstance(target, dict), "target-source-binding")
    target_repo = target.get("repository")
    provider_repo = binding.get("providerRepository")
    need(isinstance(target_repo, str) and target_repo != "", "target-source-repository")
    need(isinstance(provider_repo, str) and provider_repo != "", "provider-repository")
    if target_repo == provider_repo:
        return
    need(
        binding.get("providerAlias")
        == {
            "logicalRepository": binding.get("logicalRepository"),
            "providerRepository": provider_repo,
            "targetRepository": target_repo,
            "relation": "current-provider-for-logical-contract",
            "authority": False,
        },
        "target-provider-relation",
    )


def validate_binding_shape(binding: dict[str, Any], source_paths: dict[str, str]) -> None:
    validate_provider_relation(binding)
    runtime = binding.get("contractRuntimeSource")
    roots = binding.get("sourceRoots")
    executor = binding.get("evidenceExecutor")
    lower = binding.get("lowerVerifier")
    need(isinstance(runtime, dict), "runtime-source-binding")
    need(isinstance(roots, dict) and set(roots) == set(source_paths), "source-root-universe")
    need(set(roots.values()) <= {"target", "runtime"}, "source-root-kind")
    need(
        isinstance(executor, dict)
        and set(executor) == {"kind", "operation", "readback", "grade"}
        and executor.get("kind") in {"adapter", "exact-existing-release"}
        and isinstance(executor.get("operation"), str)
        and executor.get("operation") != ""
        and executor.get("readback") is True
        and executor.get("grade") in {"source", "real"},
        "evidence-executor",
    )
    need(isinstance(lower, dict) and lower.get("mode") in {"required", "none"}, "lower-verifier-mode")
    if lower["mode"] == "required":
        need(set(lower) == {"mode", "sourceRole"} and lower["sourceRole"] in source_paths, "lower-verifier-shape")
    else:
        need(set(lower) == {"mode"}, "lower-verifier-shape")
    runtime_roles = {role for role, root in roots.items() if root == "runtime"}
    allowed = runtime.get("allowedPaths")
    need(
        isinstance(runtime.get("repository"), str)
        and isinstance(runtime.get("revision"), str)
        and HEX40.fullmatch(runtime["revision"]) is not None
        and runtime.get("accessClass") in {"public-read", "same-repo-read", "adrs-reader-v1"},
        "runtime-source-identity",
    )
    need(isinstance(allowed, dict) and set(allowed) == runtime_roles, "runtime-path-universe")
    for role in runtime_roles:
        spec = allowed[role]
        need(
            isinstance(spec, dict)
            and set(spec) == {"path", "gitBlob"}
            and spec["path"] == source_paths[role]
            and re.fullmatch(r"[0-9a-f]{40}", str(spec["gitBlob"])) is not None,
            "runtime-path:" + role,
        )


def target_paths(target_id: str) -> tuple[Path, Path]:
    need(TARGET_ID.fullmatch(target_id) is not None, "target-id")
    adapter = TARGET_DIR / f"{target_id}.py"
    binding = TARGET_DIR / f"{target_id}.target.json"
    need(_inside_root(adapter) and _inside_root(binding), "target-path")
    need(adapter.is_file() and not adapter.is_symlink(), "adapter-file")
    need(binding.is_file() and not binding.is_symlink(), "target-binding-file")
    return adapter, binding


def load_target(target_id: str) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    adapter_path, binding_path = target_paths(target_id)
    binding = read_object(binding_path, "target-binding")
    need(binding.get("kind") == "governance.packageContractTarget.v1", "target-binding-kind")
    need(binding.get("targetId") == target_id, "target-binding-id")
    expected_adapter = adapter_path.relative_to(ROOT).as_posix()
    need(binding.get("adapterPath") == expected_adapter, "target-binding-adapter")
    spec = importlib.util.spec_from_file_location(f"package_contract_target_{target_id}", adapter_path)
    need(spec is not None and spec.loader is not None, "adapter-import")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source_paths = getattr(module, "SOURCE_PATHS", None)
    need(isinstance(source_paths, dict) and source_paths, "adapter-source-paths")
    validate_binding_shape(binding, source_paths)
    description = module.describe()
    for key in ("targetId", "logicalRepository", "providerRepository", "claimCeiling", "obligationId"):
        need(description.get(key) == binding.get(key), "adapter-binding:" + key)
    need(description.get("statusExit") == STATUS_EXIT, "adapter-status-exit")
    need(getattr(module, "EXPECTED_NEGATIVE", None) == REQUIRED_NEGATIVE, "adapter-negative-contract")
    return module, binding, {
        "adapterPath": expected_adapter,
        "adapterDigest": sha256_file(adapter_path),
        "targetBindingPath": binding_path.relative_to(ROOT).as_posix(),
        "targetBindingDigest": sha256_file(binding_path),
    }


def discover_targets() -> list[str]:
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    py_ids = {p.stem for p in TARGET_DIR.glob("*.py") if p.name != "__init__.py"}
    json_ids = {p.name[: -len(".target.json")] for p in TARGET_DIR.glob("*.target.json")}
    need(py_ids == json_ids, "adapter-binding-set")
    targets = sorted(py_ids)
    for target_id in targets:
        load_target(target_id)
    return targets


def verify_git_head(root: Path, expected: str, label: str) -> None:
    need(root.is_dir(), label + "-root")
    process = run(["git", "rev-parse", "HEAD"], root)
    need(process.returncode == 0 and process.stdout.strip() == expected, label + "-revision")


def verify_manifest(bundle: Path) -> None:
    rows = json.loads((bundle / "bundle-manifest.json").read_text(encoding="utf-8"))
    need(isinstance(rows, list), "manifest-shape")
    listed = []
    for row in rows:
        need(isinstance(row, dict) and set(row) == {"path", "sha256"}, "manifest-row")
        path = row["path"]
        need(isinstance(path, str) and not path.startswith("/") and ".." not in path.split("/"), "manifest-path")
        native = bundle / path
        need(native.is_file() and not native.is_symlink(), "manifest-file:" + path)
        need(row["sha256"] == sha256_file(native), "manifest-digest:" + path)
        listed.append(path)
    actual = sorted(
        p.relative_to(bundle).as_posix()
        for p in bundle.rglob("*")
        if p.is_file() and p.name != "bundle-manifest.json"
    )
    need(sorted(listed) == actual and len(listed) == len(set(listed)), "manifest-universe")


def verify_source_binding(
    bindings: dict[str, Any],
    key: str,
    repository: str,
    revision: str,
    source_path: str,
    native: Path | None,
    bundle: Path,
    expected_git_blob: str | None = None,
) -> dict[str, Any]:
    row = bindings.get(key)
    need(isinstance(row, dict), "source-binding:" + key)
    source = row.get("source")
    need(isinstance(source, dict), "source-descriptor:" + key)
    need(source.get("repository") == repository, "source-repository:" + key)
    need(source.get("revision") == revision, "source-revision:" + key)
    need(source.get("path") == source_path, "source-path:" + key)
    bundle_path = row.get("bundlePath")
    need(isinstance(bundle_path, str) and bundle_path != "", "source-bundle-path:" + key)
    carried = bundle / bundle_path
    need(carried.is_file() and not carried.is_symlink(), "source-carried:" + key)
    need(source.get("digest") == sha256_file(carried), "source-digest:" + key)
    if expected_git_blob is not None:
        need(git_blob_file(carried) == expected_git_blob, "source-git-blob:" + key)
    if native is not None:
        need(native.is_file() and not native.is_symlink(), "source-native:" + key)
        need(carried.read_bytes() == native.read_bytes(), "source-bytes:" + key)
    return source


def verify_evidence_input(
    evidence_root: Path | None,
    binding: dict[str, Any],
    target_id: str,
    target_candidate: str,
) -> dict[str, Any]:
    need(evidence_root is not None, "evidence-input-root")
    evidence_root = evidence_root.resolve()
    need(evidence_root.is_dir(), "evidence-input-root")
    evidence_path = evidence_root / "evidence.json"
    need(evidence_path.is_file() and not evidence_path.is_symlink(), "evidence-input-file")
    evidence = read_object(evidence_path, "evidence-input")
    need(evidence.get("kind") == "governance.packageContractEvidenceInput.v1", "evidence-input-kind")
    need(evidence.get("authority") is False, "evidence-input-authority")
    need(evidence.get("targetId") == target_id, "evidence-input-target")
    need(evidence.get("candidate") == target_candidate, "evidence-input-candidate")
    need(evidence.get("executor") == binding["evidenceExecutor"], "evidence-input-executor")
    mode = evidence.get("mode")
    if mode == "adapter":
        need(binding["evidenceExecutor"]["kind"] == "adapter", "evidence-input-mode")
        expected_files = {"evidence.json"}
        receipt = None
    elif mode == "exact-existing-release":
        need(binding["evidenceExecutor"]["kind"] == "exact-existing-release", "evidence-input-mode")
        expected_files = {
            "evidence.json",
            "source-artifact.jsonl",
            "output-artifact.jsonl",
            "dist-manifest.json",
            "provenance.json",
            "merged-pr-proof.json",
        }
        source = evidence_root / "source-artifact.jsonl"
        output = evidence_root / "output-artifact.jsonl"
        manifest_path = evidence_root / "dist-manifest.json"
        provenance_path = evidence_root / "provenance.json"
        proof_path = evidence_root / "merged-pr-proof.json"
        need(source.read_bytes() == output.read_bytes(), "evidence-input-projection")
        receipt = evidence.get("receipt")
        need(isinstance(receipt, dict), "evidence-input-receipt")
        need(receipt.get("candidate") == target_candidate, "evidence-input-receipt-candidate")
        executor = binding["evidenceExecutor"]
        need(receipt.get("operation") == executor["operation"], "evidence-input-operation")
        need(receipt.get("grade") == executor["grade"], "evidence-input-grade")
        need(receipt.get("status") == "PASS" and receipt.get("readback") == "PASS", "evidence-input-result")
        need(receipt.get("sourceDigest") == sha256_file(source), "evidence-input-source-digest")
        need(receipt.get("outputDigest") == sha256_file(output), "evidence-input-output-digest")
        need(receipt.get("manifestDigest") == sha256_file(manifest_path), "evidence-input-manifest-digest")
        need(receipt.get("provenanceDigest") == sha256_file(provenance_path), "evidence-input-provenance-digest")
        need(receipt.get("proofDigest") == sha256_file(proof_path), "evidence-input-proof-digest")
        manifest = read_object(manifest_path, "evidence-input-manifest")
        need(manifest.get("schema") == "voice-ui-dist/2", "evidence-input-manifest-schema")
        need(manifest.get("sources", {}).get("apps") == target_candidate, "evidence-input-manifest-candidate")
        need(manifest.get("auth") == ".envs/artifact.jsonl", "evidence-input-manifest-auth")
        provenance = read_object(provenance_path, "evidence-input-provenance")
        proof = read_object(proof_path, "evidence-input-proof")
        need(provenance.get("source", {}).get("commit") == target_candidate, "evidence-input-provenance-candidate")
        need(proof.get("merge_sha") == target_candidate, "evidence-input-proof-candidate")
        need(proof.get("reviewed_tree") == proof.get("merge_tree"), "evidence-input-proof-tree")
    else:
        raise ValueError("package-contract-bundle:evidence-input-mode")
    actual_files = {
        p.relative_to(evidence_root).as_posix()
        for p in evidence_root.rglob("*")
        if p.is_file()
    }
    need(actual_files == expected_files, "evidence-input-universe")
    return {
        "kind": evidence["kind"],
        "mode": mode,
        "candidate": target_candidate,
        "executor": binding["evidenceExecutor"],
        "digest": sha256_file(evidence_path),
        "filesVerified": len(actual_files),
        "receipt": receipt,
    }


def replay_comparator(
    bundle: Path,
    bindings: dict[str, Any],
    source_paths: dict[str, str],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, int]]:
    with tempfile.TemporaryDirectory(prefix="contract-runtime-") as temporary:
        runtime = Path(temporary)
        for role in RUNTIME_ROLES:
            destination = runtime / source_paths[role]
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(bundle / bindings[role]["bundlePath"], destination)
        cli = runtime / source_paths["comparatorCli"]

        def one(input_path: Path, admission_path: Path, result_path: Path, label: str):
            process = run([sys.executable, str(cli), "--input", str(input_path), "--admission", str(admission_path)], runtime)
            need(process.stdout.strip() != "", "comparator-output:" + label)
            actual = json.loads(process.stdout)
            stored = read_object(result_path, "comparator-result:" + label)
            need(actual == stored, "comparator-result:" + label)
            status = actual.get("status")
            need(status in STATUS_EXIT and process.returncode == STATUS_EXIT[status], "comparator-exit:" + label)
            return actual, process.returncode

        positive, positive_exit = one(
            bundle / "contract-diff-input.json",
            bundle / "contract-diff-admission.json",
            bundle / "contract-diff-positive.json",
            "positive",
        )
        negative: dict[str, dict[str, Any]] = {}
        exits = {"positive": positive_exit}
        for name, expected in REQUIRED_NEGATIVE.items():
            result, code = one(
                bundle / f"negative-{name}-input.json",
                bundle / f"negative-{name}-admission.json",
                bundle / f"contract-diff-negative-{name}.json",
                name,
            )
            need(result.get("status") == expected, "negative-status:" + name)
            negative[name] = result
            exits[name] = code
        return positive, negative, exits
