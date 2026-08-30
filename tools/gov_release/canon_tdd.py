from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any


class CanonTddError(ValueError):
    def __init__(self, diagnostics: list[str]):
        super().__init__(";".join(diagnostics))
        self.diagnostics = diagnostics


SCOPE = "p1-rule-evolution-foundation"
KIND = "governance.canonTddFinalEvidence.v1"
OUTPUT_KIND = "governance.canonTddFinalGreen.v1"
DECISION_ID = "01M18BMZDPXHY9MCV9QNJWNQ6W"
GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
NAR_HASH = re.compile(r"^sha256-[A-Za-z0-9+/=]{20,}$")
PROHIBITED_KEYS = {
    "status",
    "phase",
    "stage",
    "progress",
    "partial",
    "candidate_status",
    "local_status",
    "merge_status",
    "completion_percentage",
}
PROHIBITED_VALUES = {
    "pass",
    "passed",
    "success",
    "successful",
    "partial",
    "candidate-pass",
    "blocked",
    "in-progress",
    "complete-so-far",
    "green-so-far",
}
FIXTURE_CLASSES = ["good", "bad", "false-positive", "false-negative"]
TOP_LEVEL = {
    "kind",
    "scope",
    "accepted_rule",
    "governance",
    "ops",
    "gate_self_proof",
    "toolchain",
    "final_effect",
    "publication",
    "replay",
    "residuals",
    "claim_ceiling",
}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def _need(condition: bool, code: str, diagnostics: list[str]) -> None:
    if not condition:
        diagnostics.append(code)


def _exact_keys(value: Any, keys: set[str], prefix: str, diagnostics: list[str]) -> None:
    _need(isinstance(value, dict), f"{prefix}:object-required", diagnostics)
    if isinstance(value, dict):
        missing = sorted(keys - set(value))
        extra = sorted(set(value) - keys)
        diagnostics.extend(f"{prefix}:missing:{key}" for key in missing)
        diagnostics.extend(f"{prefix}:extra:{key}" for key in extra)


def _scan_prohibited(value: Any, path: str, diagnostics: list[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in PROHIBITED_KEYS:
                diagnostics.append(f"intermediate-output-key:{path}.{key}")
            _scan_prohibited(child, f"{path}.{key}", diagnostics)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _scan_prohibited(child, f"{path}[{index}]", diagnostics)
    elif isinstance(value, str) and value.lower() in PROHIBITED_VALUES:
        diagnostics.append(f"intermediate-output-value:{path}")


def _git(value: Any, code: str, diagnostics: list[str]) -> None:
    _need(isinstance(value, str) and GIT_SHA.fullmatch(value) is not None, code, diagnostics)


def _sha(value: Any, code: str, diagnostics: list[str]) -> None:
    _need(isinstance(value, str) and SHA256.fullmatch(value) is not None, code, diagnostics)


def _positive_int(value: Any, code: str, diagnostics: list[str]) -> None:
    _need(isinstance(value, int) and not isinstance(value, bool) and value > 0, code, diagnostics)


def _zero(value: Any, code: str, diagnostics: list[str]) -> None:
    _need(value == 0 and isinstance(value, int) and not isinstance(value, bool), code, diagnostics)


def _true(value: Any, code: str, diagnostics: list[str]) -> None:
    _need(value is True, code, diagnostics)


def _false(value: Any, code: str, diagnostics: list[str]) -> None:
    _need(value is False, code, diagnostics)


def validate_final_evidence(value: Any) -> dict[str, Any]:
    diagnostics: list[str] = []
    _exact_keys(value, TOP_LEVEL, "root", diagnostics)
    if not isinstance(value, dict):
        raise CanonTddError(sorted(set(diagnostics)))
    _scan_prohibited(value, "root", diagnostics)
    _need(value.get("kind") == KIND, "root:kind", diagnostics)
    _need(value.get("scope") == SCOPE, "root:scope", diagnostics)

    rule = value.get("accepted_rule")
    rule_keys = {"decision_id", "repository", "commit", "tree", "path", "digest"}
    _exact_keys(rule, rule_keys, "accepted_rule", diagnostics)
    if isinstance(rule, dict):
        _need(rule.get("decision_id") == DECISION_ID, "accepted_rule:decision-id", diagnostics)
        _need(rule.get("repository") == "roccho-dev/adrs", "accepted_rule:repository", diagnostics)
        _git(rule.get("commit"), "accepted_rule:commit", diagnostics)
        _git(rule.get("tree"), "accepted_rule:tree", diagnostics)
        _need(rule.get("path") == f"adr/src/{DECISION_ID}-evidence-gated-rule-evolution-canon-tdd.cue", "accepted_rule:path", diagnostics)
        _sha(rule.get("digest"), "accepted_rule:digest", diagnostics)

    gov = value.get("governance")
    gov_keys = {
        "repository", "commit", "tree", "obligation_root", "obligation_count",
        "missing", "extra", "duplicate", "unknown", "stale", "build_root_a",
        "build_root_b", "final_join_root",
    }
    _exact_keys(gov, gov_keys, "governance", diagnostics)
    if isinstance(gov, dict):
        _need(gov.get("repository") == "roccho-dev/governance", "governance:repository", diagnostics)
        _git(gov.get("commit"), "governance:commit", diagnostics)
        _git(gov.get("tree"), "governance:tree", diagnostics)
        for key in ("obligation_root", "build_root_a", "build_root_b", "final_join_root"):
            _sha(gov.get(key), f"governance:{key}", diagnostics)
        _positive_int(gov.get("obligation_count"), "governance:obligation-count", diagnostics)
        for key in ("missing", "extra", "duplicate", "unknown", "stale"):
            _zero(gov.get(key), f"governance:{key}", diagnostics)
        _need(gov.get("build_root_a") == gov.get("build_root_b"), "governance:nondeterministic-build", diagnostics)

    ops = value.get("ops")
    ops_keys = {
        "repository", "commit", "tree", "package_claim_root", "observation_root",
        "finding_root", "receipt_root", "required_observation_count", "required_unobserved_count",
    }
    _exact_keys(ops, ops_keys, "ops", diagnostics)
    if isinstance(ops, dict):
        _need(ops.get("repository") == "roccho-dev/ops", "ops:repository", diagnostics)
        _git(ops.get("commit"), "ops:commit", diagnostics)
        _git(ops.get("tree"), "ops:tree", diagnostics)
        for key in ("package_claim_root", "observation_root", "finding_root", "receipt_root"):
            _sha(ops.get(key), f"ops:{key}", diagnostics)
        _positive_int(ops.get("required_observation_count"), "ops:required-observation-count", diagnostics)
        _zero(ops.get("required_unobserved_count"), "ops:required-unobserved-count", diagnostics)

    proof = value.get("gate_self_proof")
    proof_keys = {
        "gate_digest", "rules", "rule_ids", "fixture_classes", "missing_fixture_classes",
        "mutation_hits", "mutation_misses", "good_cases", "bad_cases", "false_positive_cases",
        "false_negative_cases", "bad_rejected", "false_negative_rejected", "good_accepted",
        "false_positive_accepted", "repair_replays", "replay_root_a", "replay_root_b",
    }
    _exact_keys(proof, proof_keys, "gate_self_proof", diagnostics)
    if isinstance(proof, dict):
        _sha(proof.get("gate_digest"), "gate_self_proof:gate-digest", diagnostics)
        rules = proof.get("rules")
        _positive_int(rules, "gate_self_proof:rules", diagnostics)
        ids = proof.get("rule_ids")
        _need(isinstance(ids, list) and len(ids) == rules and len(set(ids)) == len(ids) and all(isinstance(item, str) and item for item in ids), "gate_self_proof:rule-ids", diagnostics)
        _need(proof.get("fixture_classes") == FIXTURE_CLASSES, "gate_self_proof:fixture-classes", diagnostics)
        _zero(proof.get("missing_fixture_classes"), "gate_self_proof:missing-fixture-classes", diagnostics)
        for key in ("mutation_hits", "good_cases", "bad_cases", "false_positive_cases", "false_negative_cases", "bad_rejected", "false_negative_rejected", "good_accepted", "false_positive_accepted", "repair_replays"):
            _need(proof.get(key) == rules, f"gate_self_proof:{key}", diagnostics)
        _zero(proof.get("mutation_misses"), "gate_self_proof:mutation-misses", diagnostics)
        _sha(proof.get("replay_root_a"), "gate_self_proof:replay-root-a", diagnostics)
        _sha(proof.get("replay_root_b"), "gate_self_proof:replay-root-b", diagnostics)
        _need(proof.get("replay_root_a") == proof.get("replay_root_b"), "gate_self_proof:nondeterministic-replay", diagnostics)

    toolchain = value.get("toolchain")
    toolchain_keys = {"nix_version", "nar_hash", "required_tools"}
    _exact_keys(toolchain, toolchain_keys, "toolchain", diagnostics)
    if isinstance(toolchain, dict):
        _need(isinstance(toolchain.get("nix_version"), str) and toolchain["nix_version"].strip(), "toolchain:nix-version", diagnostics)
        _need(isinstance(toolchain.get("nar_hash"), str) and NAR_HASH.fullmatch(toolchain["nar_hash"]) is not None, "toolchain:nar-hash", diagnostics)
        tools = toolchain.get("required_tools")
        _need(isinstance(tools, list) and len(tools) > 0, "toolchain:required-tools", diagnostics)
        if isinstance(tools, list):
            ids: list[str] = []
            for index, row in enumerate(tools):
                _exact_keys(row, {"id", "digest"}, f"toolchain:required-tools[{index}]", diagnostics)
                if isinstance(row, dict):
                    _need(isinstance(row.get("id"), str) and row["id"], f"toolchain:required-tools[{index}]:id", diagnostics)
                    _sha(row.get("digest"), f"toolchain:required-tools[{index}]:digest", diagnostics)
                    if isinstance(row.get("id"), str):
                        ids.append(row["id"])
            _need(len(ids) == len(set(ids)), "toolchain:required-tools-duplicate", diagnostics)

    effect = value.get("final_effect")
    effect_keys = {
        "repository", "merge_commit", "merge_tree", "remote_commit", "remote_tree",
        "preserved_members", "undeclared_changes", "readback_root",
    }
    _exact_keys(effect, effect_keys, "final_effect", diagnostics)
    if isinstance(effect, dict):
        _need(effect.get("repository") == "roccho-dev/governance", "final_effect:repository", diagnostics)
        for key in ("merge_commit", "merge_tree", "remote_commit", "remote_tree"):
            _git(effect.get(key), f"final_effect:{key}", diagnostics)
        _need(effect.get("merge_commit") == effect.get("remote_commit"), "final_effect:commit-readback", diagnostics)
        _need(effect.get("merge_tree") == effect.get("remote_tree"), "final_effect:tree-readback", diagnostics)
        _need(not isinstance(gov, dict) or effect.get("merge_commit") == gov.get("commit"), "final_effect:governance-commit", diagnostics)
        _need(not isinstance(gov, dict) or effect.get("merge_tree") == gov.get("tree"), "final_effect:governance-tree", diagnostics)
        _true(effect.get("preserved_members"), "final_effect:preserved-members", diagnostics)
        _zero(effect.get("undeclared_changes"), "final_effect:undeclared-changes", diagnostics)
        _sha(effect.get("readback_root"), "final_effect:readback-root", diagnostics)

    publication = value.get("publication")
    publication_keys = {
        "repository", "tag", "asset_name", "asset_sha256", "remote_asset_sha256",
        "bytes", "manifest_digest", "remote_manifest_digest",
    }
    _exact_keys(publication, publication_keys, "publication", diagnostics)
    if isinstance(publication, dict):
        _need(publication.get("repository") == "roccho-dev/governance", "publication:repository", diagnostics)
        _need(isinstance(publication.get("tag"), str) and publication["tag"].startswith("p1-final/"), "publication:tag", diagnostics)
        _need(publication.get("asset_name") == "p1-final-green.json", "publication:asset-name", diagnostics)
        _sha(publication.get("asset_sha256"), "publication:asset-sha256", diagnostics)
        _sha(publication.get("remote_asset_sha256"), "publication:remote-asset-sha256", diagnostics)
        _need(publication.get("asset_sha256") == publication.get("remote_asset_sha256"), "publication:asset-readback", diagnostics)
        _positive_int(publication.get("bytes"), "publication:bytes", diagnostics)
        _sha(publication.get("manifest_digest"), "publication:manifest-digest", diagnostics)
        _sha(publication.get("remote_manifest_digest"), "publication:remote-manifest-digest", diagnostics)
        _need(publication.get("manifest_digest") == publication.get("remote_manifest_digest"), "publication:manifest-readback", diagnostics)

    replay = value.get("replay")
    replay_keys = {"artifact_sha256", "fresh_evaluator", "source_clone_used", "repair_used", "output_root", "expected_output_root"}
    _exact_keys(replay, replay_keys, "replay", diagnostics)
    if isinstance(replay, dict):
        _sha(replay.get("artifact_sha256"), "replay:artifact-sha256", diagnostics)
        _true(replay.get("fresh_evaluator"), "replay:fresh-evaluator", diagnostics)
        _false(replay.get("source_clone_used"), "replay:source-clone-used", diagnostics)
        _false(replay.get("repair_used"), "replay:repair-used", diagnostics)
        _sha(replay.get("output_root"), "replay:output-root", diagnostics)
        _sha(replay.get("expected_output_root"), "replay:expected-output-root", diagnostics)
        _need(replay.get("output_root") == replay.get("expected_output_root"), "replay:output-root-mismatch", diagnostics)
        _need(not isinstance(gov, dict) or replay.get("expected_output_root") == gov.get("final_join_root"), "replay:final-join-root", diagnostics)

    residuals = value.get("residuals")
    _need(residuals == [], "residuals:not-empty", diagnostics)

    ceiling = value.get("claim_ceiling")
    ceiling_keys = {"p2_monitoring_complete", "production_cutover", "business_outcome_achieved", "corporate_sale_outcome_achieved"}
    _exact_keys(ceiling, ceiling_keys, "claim_ceiling", diagnostics)
    if isinstance(ceiling, dict):
        for key in ceiling_keys:
            _false(ceiling.get(key), f"claim_ceiling:{key}", diagnostics)

    if diagnostics:
        raise CanonTddError(sorted(set(diagnostics)))

    roots = {
        "acceptedRule": rule["digest"],
        "obligations": gov["obligation_root"],
        "packageClaims": ops["package_claim_root"],
        "observations": ops["observation_root"],
        "findings": ops["finding_root"],
        "receipts": ops["receipt_root"],
        "gate": proof["gate_digest"],
        "finalJoin": gov["final_join_root"],
        "finalReadback": effect["readback_root"],
    }
    artifact = {
        "kind": OUTPUT_KIND,
        "scope": SCOPE,
        "verdict": "GREEN",
        "acceptedRule": {
            "decisionId": rule["decision_id"],
            "commit": rule["commit"],
            "tree": rule["tree"],
            "digest": rule["digest"],
        },
        "finalIdentities": {
            "governanceCommit": gov["commit"],
            "governanceTree": gov["tree"],
            "opsCommit": ops["commit"],
            "opsTree": ops["tree"],
        },
        "evidenceRoots": roots,
        "toolchain": {
            "nixVersion": toolchain["nix_version"],
            "narHash": toolchain["nar_hash"],
            "requiredTools": toolchain["required_tools"],
        },
        "publication": {
            "tag": publication["tag"],
            "assetName": publication["asset_name"],
            "assetSha256": publication["asset_sha256"],
            "manifestDigest": publication["manifest_digest"],
        },
        "replay": {
            "artifactSha256": replay["artifact_sha256"],
            "outputRoot": replay["output_root"],
        },
        "claimCeiling": ceiling,
        "authority": False,
    }
    artifact["closureDigest"] = digest(artifact)
    return artifact


def write_final(evidence_path: Path, output_path: Path) -> dict[str, Any]:
    output_path = output_path.resolve()
    if output_path.exists() or output_path.is_symlink():
        if output_path.is_dir() and not output_path.is_symlink():
            raise CanonTddError(["output:regular-file-path-required"])
        output_path.unlink()
    try:
        value = json.loads(evidence_path.read_text(encoding="utf-8"))
        artifact = validate_final_evidence(value)
    except CanonTddError:
        raise
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        raise CanonTddError([f"evidence:unreadable:{type(exc).__name__}"]) from exc
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{output_path.name}.", dir=output_path.parent)
    os.close(fd)
    tmp = Path(temporary)
    try:
        tmp.write_bytes(canonical_bytes(artifact) + b"\n")
        os.replace(tmp, output_path)
    finally:
        if tmp.exists():
            tmp.unlink()
    return artifact


def diagnostic_document(diagnostics: list[str]) -> dict[str, Any]:
    return {
        "kind": "governance.canonTddDiagnostic.v1",
        "scope": SCOPE,
        "diagnostics": sorted(set(diagnostics)),
        "canonicalVerdictEmitted": False,
    }
