from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable


class ReleaseError(ValueError):
    pass


def need(ok: bool, code: str) -> None:
    if not ok:
        raise ReleaseError(code)


def canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


def is_digest(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 71
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


MANIFEST_FIELDS = {
    "kind",
    "releaseId",
    "sequence",
    "previousReleaseDigest",
    "supersedesReleaseDigest",
    "acceptedDecisionDigest",
    "govEngineDigest",
    "nixOutputDigest",
    "status",
}

PROVIDER_FIELDS = {
    "githubRunId",
    "githubArtifactId",
    "githubReleaseId",
    "githubActor",
    "githubIssueNumber",
    "url",
}


def validate_manifest(
    value: dict[str, Any],
    *,
    expected_decision_digest: str | None = None,
    expected_engine_digest: str | None = None,
    expected_nix_output_digest: str | None = None,
) -> str:
    need(set(value) == MANIFEST_FIELDS, "manifest-extra-or-missing-field")
    need(value.get("kind") == "govReleaseManifest.v1", "manifest-kind")
    need(isinstance(value.get("releaseId"), str) and bool(value["releaseId"]), "release-id")
    need(isinstance(value.get("sequence"), int) and value["sequence"] >= 0, "sequence")
    need(value.get("status") == "adopted", "status")
    for field in ("acceptedDecisionDigest", "govEngineDigest", "nixOutputDigest"):
        need(is_digest(value.get(field)), field + "-format")
    for field in ("previousReleaseDigest", "supersedesReleaseDigest"):
        need(value.get(field) is None or is_digest(value[field]), field + "-format")
    need(not (PROVIDER_FIELDS & set(value)), "provider-metadata")
    if expected_decision_digest is not None:
        need(value["acceptedDecisionDigest"] == expected_decision_digest, "accepted-decision-digest")
    if expected_engine_digest is not None:
        need(value["govEngineDigest"] == expected_engine_digest, "gov-engine-digest")
    if expected_nix_output_digest is not None:
        need(value["nixOutputDigest"] == expected_nix_output_digest, "nix-output-digest")
    return digest(value)


def make_manifest(
    *,
    release_id: str,
    sequence: int,
    previous_release_digest: str | None,
    supersedes_release_digest: str | None,
    accepted_decision_digest: str,
    gov_engine_digest: str,
    nix_output_digest: str,
) -> dict[str, Any]:
    value = {
        "kind": "govReleaseManifest.v1",
        "releaseId": release_id,
        "sequence": sequence,
        "previousReleaseDigest": previous_release_digest,
        "supersedesReleaseDigest": supersedes_release_digest,
        "acceptedDecisionDigest": accepted_decision_digest,
        "govEngineDigest": gov_engine_digest,
        "nixOutputDigest": nix_output_digest,
        "status": "adopted",
    }
    validate_manifest(value)
    return value


def reduce_manifests(manifests: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(manifests)
    need(bool(rows), "release-empty")
    by_sequence: dict[int, tuple[str, dict[str, Any]]] = {}
    by_digest: dict[str, dict[str, Any]] = {}
    release_ids: set[str] = set()
    for value in rows:
        release_digest = validate_manifest(value)
        sequence = value["sequence"]
        release_id = value["releaseId"]
        need(sequence not in by_sequence, "duplicate-sequence")
        need(release_id not in release_ids, "duplicate-release-id")
        by_sequence[sequence] = (release_digest, value)
        by_digest[release_digest] = value
        release_ids.add(release_id)
    sequences = sorted(by_sequence)
    need(sequences == list(range(len(sequences))), "sequence-gap")
    for sequence in sequences:
        release_digest, value = by_sequence[sequence]
        if sequence == 0:
            need(value["previousReleaseDigest"] is None, "genesis-previous")
        else:
            previous_digest, _ = by_sequence[sequence - 1]
            need(value["previousReleaseDigest"] == previous_digest, "previous-release-digest")
        supersedes = value["supersedesReleaseDigest"]
        if supersedes is not None:
            need(supersedes in by_digest, "unknown-supersedes")
            need(by_digest[supersedes]["sequence"] < sequence, "supersedes-not-previous")
    selected_digest, selected = by_sequence[sequences[-1]]
    return {
        "kind": "govReleaseSelectedProjection.v1",
        "status": "pass",
        "selectedReleaseId": selected["releaseId"],
        "selectedReleaseDigest": selected_digest,
        "sequence": selected["sequence"],
        "acceptedDecisionDigest": selected["acceptedDecisionDigest"],
        "govEngineDigest": selected["govEngineDigest"],
        "nixOutputDigest": selected["nixOutputDigest"],
        "authority": False,
    }


def make_engine_descriptor(*, repository: str, commit_sha: str) -> dict[str, Any]:
    need(bool(repository), "engine-repository")
    need(len(commit_sha) == 40 and all(c in "0123456789abcdef" for c in commit_sha), "engine-commit")
    return {
        "kind": "govEngineDescriptor.v1",
        "repository": repository,
        "commitSha": commit_sha,
    }


def make_nix_output_descriptor(*, package: str, nar_hash: str) -> dict[str, Any]:
    need(bool(package), "nix-package")
    need(isinstance(nar_hash, str) and nar_hash.startswith("sha256-"), "nix-nar-hash")
    return {
        "kind": "govNixOutputDescriptor.v1",
        "package": package,
        "narHash": nar_hash,
    }


def make_eligibility(
    *,
    candidate_sha: str,
    accepted_decision_digest: str,
    gate_report: dict[str, Any],
    claim_set_digest: str,
    receipt_set_digest: str,
) -> dict[str, Any]:
    need(len(candidate_sha) == 40 and all(c in "0123456789abcdef" for c in candidate_sha), "candidate-sha")
    need(is_digest(accepted_decision_digest), "decision-digest")
    need(is_digest(claim_set_digest), "claim-set-digest")
    need(is_digest(receipt_set_digest), "receipt-set-digest")
    need(gate_report.get("status") == "pass", "gate-status")
    need(gate_report.get("decision") == "allow", "gate-decision")
    need(gate_report.get("candidateSha") == candidate_sha, "gate-candidate")
    value = {
        "kind": "govReleaseEligibility.v1",
        "status": "pass",
        "candidateSha": candidate_sha,
        "acceptedDecisionDigest": accepted_decision_digest,
        "gateReportDigest": digest(gate_report),
        "claimSetDigest": claim_set_digest,
        "receiptSetDigest": receipt_set_digest,
        "releaseEligible": True,
        "releasePublished": False,
        "operationalAdoptionEffect": False,
        "authority": False,
    }
    value["eligibilityDigest"] = digest(value)
    return value


def validate_readback(
    receipt: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    release_digest = validate_manifest(manifest)
    need(receipt.get("kind") == "govReleaseReadbackReceipt.v1", "receipt-kind")
    need(receipt.get("status") == "pass", "receipt-status")
    need(receipt.get("releaseId") == manifest["releaseId"], "receipt-release-id")
    need(receipt.get("releaseDigest") == release_digest, "receipt-release-digest")
    need(receipt.get("observedManifestDigest") == release_digest, "receipt-observed-digest")
    need(receipt.get("adopted") is True, "receipt-adopted")
    need(receipt.get("authority") is False, "receipt-authority")
    return {
        "kind": "govReleaseAdoptionReadback.v1",
        "status": "pass",
        "releaseId": manifest["releaseId"],
        "releaseDigest": release_digest,
        "adopted": True,
        "authority": False,
    }
