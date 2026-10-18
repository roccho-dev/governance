"""Select retained Cold originals, then use the existing package-contract verifier.

Selection is not admission.  The target's existing binding supplies the trusted
accepted bytes; neither a caller flag nor a captured status can replace them.
The returned JSONL is a disposable evidence projection, not a meaning ledger.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
from pathlib import Path, PurePosixPath
from types import ModuleType
from argparse import Namespace
from typing import Any

from tools.package_contract_port_common import ROOT, digest


MATERIALIZER_BLOB = "f861d0019667ee679da3d374dac8e117adae05d0"
MATERIALIZER_REVISION = "a6284e58ed99243447e135828d983fc07d2d363e"


class ColdInputError(ValueError):
    def __init__(self, reason: str, status: str = "UNKNOWN"):
        super().__init__(reason)
        self.status = status


def require(condition: bool, reason: str, status: str = "UNKNOWN") -> None:
    if not condition:
        raise ColdInputError(reason, status)


class GitReader:
    def __init__(self, root: Path, executable: str):
        self.root = root.resolve()
        self.executable = executable
        require(os.name != "nt" or Path(executable).is_absolute(), "absolute-native-git-required")

    def run(self, *arguments: str) -> bytes:
        location = ["--git-dir=" + str(self.root)] if (self.root / "HEAD").is_file() else ["-C", str(self.root)]
        try:
            process = subprocess.run(
                [self.executable, "--no-optional-locks", "-c", "core.autocrlf=false",
                 "-c", "gc.auto=0", "-c", "maintenance.auto=false", *location, *arguments],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
        except OSError as error:
            raise ColdInputError("native-git-unavailable") from error
        require(process.returncode == 0, "native-git:" + arguments[0])
        return process.stdout

    def held(self, reference: str, revision: str) -> dict[str, str]:
        require(isinstance(revision, str) and bool(re.fullmatch(r"[0-9a-f]{40}", revision)), "fixed-cold-revision-required", "INVALID")
        require(reference == "HEAD" or reference.startswith("refs/"), "explicit-holding-ref-required", "INVALID")
        require(not any(c in reference for c in "\x00\r\n "), "invalid-holding-ref", "INVALID")
        if reference == "HEAD":
            holding = self.run("rev-parse", "--verify", "HEAD^{commit}").decode().strip()
        else:
            # show-ref --verify resolves a literal existing ref, never ~0,
            # reflog syntax, rev expressions or a caller's unrooted object ID.
            holding = self.run("show-ref", "--verify", "--hash", reference).decode().strip()
            holding = self.run("rev-parse", "--verify", holding + "^{commit}").decode().strip()
        self.run("merge-base", "--is-ancestor", revision, holding)
        tree = self.run("rev-parse", revision + "^{tree}").decode().strip()
        return {"ref": reference, "holdingRevision": holding, "revision": revision, "tree": tree}

    def file(self, revision: str, path: str) -> tuple[bytes, str, str]:
        require(isinstance(path, str), "source-path-missing", "INVALID")
        candidate = PurePosixPath(path)
        require(bool(path) and str(candidate) == path and not candidate.is_absolute()
                and ".." not in candidate.parts and "\\" not in path and ":" not in path,
                "noncanonical-source-path", "INVALID")
        entry = self.run("ls-tree", "-z", revision, "--", path).split(b"\0")
        entries = [x for x in entry if x]
        require(len(entries) == 1, "source-tree-entry")
        header, actual_path = entries[0].split(b"\t", 1)
        mode, kind, blob = header.decode().split()
        require(actual_path.decode() == path and kind == "blob" and mode in {"100644", "100755"},
                "source-must-be-regular-native-blob")
        raw = self.run("cat-file", "blob", blob)
        calculated = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        require(calculated == blob, "native-blob-bytes")
        return raw, blob, mode


def _codec(root: Path, git: str) -> ModuleType:
    # This trusted implementation is fixed independently of the selected data
    # commit. A Cold proposal cannot supply, update or choose executable code.
    reader = GitReader(root, git)
    reader.held("HEAD", MATERIALIZER_REVISION)
    raw, blob, _ = reader.file(MATERIALIZER_REVISION, "tools/materialize.py")
    require(blob == MATERIALIZER_BLOB, "trusted-cold-codec-bytes")
    module = ModuleType("adrs_cold_materialize")
    module.__file__ = "adrs-trusted:" + MATERIALIZER_REVISION + ":tools/materialize.py"
    exec(compile(raw, module.__file__, "exec"), module.__dict__)
    return module


def select_cold_record(*, root: Path, code_root: Path, git: str, reference: str, revision: str,
                       path: str, record_id: str, object_id: str | None = None) -> dict[str, Any]:
    reader = GitReader(root, git)
    held = reader.held(reference, revision)
    require(path.startswith("decisions/") and path.endswith(".jsonl"), "cold-meaning-source-path", "INVALID")
    raw, blob, mode = reader.file(revision, path)
    codec = _codec(code_root, git)
    try:
        rows = [codec.parse(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    except (codec.MaterializationError, json.JSONDecodeError, UnicodeError) as error:
        raise ColdInputError("invalid-cold-json:" + str(error), "INVALID") from error
    require(all(isinstance(row, dict) for row in rows), "cold-object-rows", "INVALID")
    selected = [row for row in rows if row.get("raw_id", row.get("id")) == record_id]
    require(bool(selected), "cold-record-missing")
    if len(selected) > 1:
        require(False, "cold-record-duplicate" if all(x == selected[0] for x in selected)
                else "cold-record-conflict", "INVALID")
    source = selected[0]
    if source.get("kind") == "source_content":
        provenance = source.get("provenance", {})
        require(isinstance(provenance, dict), "cold-provenance-shape", "INVALID")
        require(provenance.get("repo") == "roccho-dev/adrs", "cold-original-owner")
        original_revision, original_path = provenance.get("commit"), provenance.get("original_path")
        reader.held(reference, original_revision)
        original, original_blob, original_mode = reader.file(original_revision, original_path)
        require(provenance.get("mode") == original_mode, "cold-original-native-mode")
        content = source.get("content")
        require(isinstance(content, dict) and isinstance(content.get("media_type"), str),
                "cold-content-shape", "INVALID")
        if content.get("encoding") == "utf-8":
            blocks = content.get("blocks")
            require(isinstance(blocks, list) and all(isinstance(block, dict)
                    and isinstance(block.get("id"), str) and isinstance(block.get("statement"), str)
                    for block in blocks), "cold-content-block-shape", "INVALID")
        elif content.get("encoding") == "base64":
            require(isinstance(content.get("data"), str), "cold-content-base64-shape", "INVALID")
        else:
            require(False, "cold-content-encoding", "INVALID")
        try:
            decoded = codec.decode(source)
        except (codec.MaterializationError, KeyError, TypeError, UnicodeError, ValueError) as error:
            raise ColdInputError("invalid-cold-original-content", "INVALID") from error
        require(decoded == original, "cold-original-native-bytes")
        require(isinstance(source.get("relations"), list), "cold-relations-shape", "INVALID")
        require(any(rel.get("kind") == "preserves_original" and rel.get("repo") == provenance["repo"]
                    and rel.get("commit") == original_revision and rel.get("path") == original_path
                    for rel in source.get("relations", []) if isinstance(rel, dict)), "cold-original-relation")
        try:
            answer = codec.query(source, original_id=object_id)
        except (json.JSONDecodeError, UnicodeError) as error:
            raise ColdInputError("invalid-cold-original-format", "INVALID") from error
        except codec.MaterializationError as error:
            raise ColdInputError("cold-object-selection:" + str(error)) from error
        value = answer["objects"]
    else:
        try:
            answer = codec.query(source, original_id=object_id)
        except codec.MaterializationError as error:
            raise ColdInputError("cold-object-selection:" + str(error)) from error
        value, original_blob = answer["object"], blob
    return {"source": {**held, "repository": "roccho-dev/adrs", "path": path, "gitBlob": blob, "mode": mode,
                       "digest": "sha256:" + hashlib.sha256(raw).hexdigest(), "raw_id": record_id,
                       "object_id": object_id},
            "record": source, "object": value, "originalBlob": original_blob,
            "relations": source.get("relations", []), "codecBlob": MATERIALIZER_BLOB}


def existing_final() -> ModuleType:
    path = ROOT / "tools/check-package-final-scope-purpose-join.py"
    spec = importlib.util.spec_from_file_location("cold_existing_final", path)
    require(spec is not None and spec.loader is not None, "existing-final-import")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _accepted_inputs(target_id: str, root: Path, git: str, checker: Any) -> tuple[Any, dict, dict, dict]:
    try:
        module, binding, identity = checker.load_target(target_id)
    except ValueError as error:
        if not str(error).startswith("package-contract-bundle:"):
            raise
        raise ColdInputError("unsupported-or-invalid-target-binding:" + str(error)) from error
    source = binding["acceptedRequirementSource"]
    reader = GitReader(root, git)
    actual_head = reader.run("rev-parse", "HEAD").decode().strip()
    require(actual_head == source["revision"], "accepted-native-head")
    values = {}
    for role, spec in source["allowedPaths"].items():
        raw, blob, _ = reader.file(source["revision"], spec["path"])
        require(blob == spec["gitBlob"], "accepted-native-blob:" + role)
        values[role] = json.loads(raw)
    return module, binding, identity, values


def _bind_admitted(selected: dict, decision: dict, cold_reader: GitReader, holding_ref: str,
                   approved_source: dict) -> dict:
    value = selected["object"]
    if value == decision:
        require(approved_source["repository"] == "roccho-dev/adrs", "direct-accepted-owner")
        cold_reader.held(holding_ref, approved_source["revision"])
        spec = approved_source["allowedPaths"]["acceptedDecision"]
        native, blob, _ = cold_reader.file(approved_source["revision"], spec["path"])
        require(blob == spec["gitBlob"] and json.loads(native) == value, "actual-adopted-original")
        return {"selection": "exact-bound-accepted-object", "repository": approved_source["repository"],
                "revision": approved_source["revision"], "path": spec["path"], "gitBlob": blob,
                "meaningDigest": digest(value.get("meaning_identity", value))}
    # Existing approved projection names the actual ADRS contract, not a new
    # admission asserted by the selected original or by a command-line boolean.
    required = ("acceptedMerge", "sourcePath", "contractCanonicalDigest", "issue")
    require(all(isinstance(decision.get(key), str) for key in required), "unsupported-or-unadmitted-cold-object")
    repository = decision["issue"].split("#", 1)[0]
    require(repository == "roccho-dev/adrs", "approved-original-owner")
    cold_reader.held(holding_ref, decision["acceptedMerge"])
    accepted_raw, accepted_blob, _ = cold_reader.file(decision["acceptedMerge"], decision["sourcePath"])
    actual = json.loads(accepted_raw)
    require(digest(actual) == "sha256:" + decision["contractCanonicalDigest"], "approved-original-meaning-digest")
    require(value == actual, "cold-object-differs-from-actual-adopted-original")
    provenance = selected["record"].get("provenance", {})
    require(provenance.get("original_path") == decision["sourcePath"], "approved-original-path")
    return {"selection": "approved-projection-to-actual-original", "repository": repository,
            "revision": decision["acceptedMerge"], "path": decision["sourcePath"],
            "gitBlob": accepted_blob, "meaningDigest": digest(actual)}


def check_cold_record(*, cold_root: Path, code_root: Path, git: str, cold_ref: str, cold_revision: str,
                      cold_path: str, record_id: str, target_id: str, bundle: Path,
                      target_source: Path, accepted_requirement_source: Path,
                      governance_policy_source: Path, contract_runtime_source: Path,
                      evidence_input: Path, governance_candidate: str,
                      object_id: str | None = None, target_candidate: str | None = None) -> dict[str, Any]:
    selected = select_cold_record(root=cold_root, code_root=code_root, git=git, reference=cold_ref, revision=cold_revision,
                                  path=cold_path, record_id=record_id, object_id=object_id)
    final = existing_final()
    checker = final.load_checker()
    module, binding, identity, accepted = _accepted_inputs(target_id, accepted_requirement_source, git, checker)
    require(target_candidate is None or target_candidate == binding["targetSource"]["revision"],
            "explicit-target-candidate-mismatch")
    admission = _bind_admitted(selected, accepted["acceptedDecision"], GitReader(cold_root, git), cold_ref,
                               binding["acceptedRequirementSource"])
    from tools.package_contract_port_common import check_token
    _, required = module.required_contract(accepted["acceptedDecision"], accepted["acceptedRollout"], digest, check_token)
    # The actual final check-package entry loads the canonical corrected checker
    # (including full evidence material and import guards), not its lower helper.
    try:
        final_result = final.run_package_check(Namespace(
            candidate_sha=governance_candidate, package_contract_bundle=bundle,
            package_contract_target_source=target_source,
            package_contract_accepted_requirement_source=accepted_requirement_source,
            package_contract_governance_policy_source=governance_policy_source,
            package_contract_runtime_source=contract_runtime_source,
            package_contract_evidence_input=evidence_input, package_contract_target_id=target_id,
            expected_target_candidate=binding["targetSource"]["revision"],
        ))
    except ValueError as error:
        if not str(error).startswith(("package-contract:", "package-contract-bundle:")):
            raise  # An unexpected programming failure must remain a failure.
        raise ColdInputError("existing-final:" + str(error)) from error
    except OSError as error:
        # The existing consumer reads caller-owned bundle/source/Receipt bodies.
        # Missing or unreadable material is acquisition failure, not completion.
        # Logic errors are deliberately outside this narrowly scoped boundary.
        raise ColdInputError("existing-final-input-unreadable:" + type(error).__name__) from error
    member = final_result["packageContractClosure"]
    require(member["obligationId"] == binding["obligationId"]
            and member["acceptedRequirementDigest"] == required["obligation_digest"], "consumer-required-binding")
    payload = {"coldSource": selected["source"], "admittedSource": admission,
               "acceptedProjection": binding["acceptedRequirementSource"],
               "required": {"id": binding["obligationId"], "contract": required},
               "consumerResult": final_result, "adapterIdentity": identity,
               "transform": {"codecRevision": MATERIALIZER_REVISION, "codecGitBlob": MATERIALIZER_BLOB,
                             "coldInputDigest": "sha256:" + hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
               "coverage": {"scope": "selected target binding only; not all record/rollout/repository obligations",
                            "expected": [binding["obligationId"]], "checked": [member["obligationId"]], "missing": []}}
    return {"schema": "adr_raw_event.v1", "raw_id": "derived.contract-result." + digest(payload)[7:],
            "kind": "fact", "authority": False, "status": member["contractDiffStatus"],
            "relations": [{"kind": "references", "raw_id": record_id, "source": selected["source"]}],
            "payload": payload,
            "admission_boundary": "Derived evidence projection only; this result does not admit meaning or operational adoption."}


def readback_result(actual: dict, path: Path) -> None:
    """Recompute first; a self-rehashed stored result does not prove itself."""
    try:
        def unique(pairs):
            output = {}
            for key, value in pairs:
                require(key not in output, "result-duplicate-key", "INVALID")
                output[key] = value
            return output
        stored = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ColdInputError("result-unreadable") from error
    require(stored == actual, "same-record-result-readback-mismatch")
