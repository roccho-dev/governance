from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .core import ContractError, canonical_json, parse_canonical_jsonl, sha256_bytes

DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
GIT_TREE_RE = re.compile(r"^git-tree-sha1:[0-9a-f]{40}$")


class JoinError(ContractError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise JoinError(f"json-regular-file-required:{path.name}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise JoinError(f"json-object-required:{path.name}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file() or path.is_symlink():
        raise JoinError(f"jsonl-regular-file-required:{path.name}")
    raw = path.read_bytes()
    if raw and not raw.endswith(b"\n"):
        raise JoinError(f"jsonl-final-newline:{path.name}")
    rows: list[dict[str, Any]] = []
    for index, line in enumerate(raw.splitlines(), start=1):
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise JoinError(f"jsonl-parse:{path.name}:{index}:{exc}") from exc
        if not isinstance(row, dict):
            raise JoinError(f"jsonl-object-required:{path.name}:{index}")
        rows.append(row)
    return rows


def _unique(rows: list[dict[str, Any]], field: str, label: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        value = row.get(field)
        if not isinstance(value, str) or not value:
            raise JoinError(f"{label}-id-required:{field}")
        if value in out:
            raise JoinError(f"{label}-duplicate:{value}")
        out[value] = row
    return out


def _digest(value: Any) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def _normalized_obligation(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "packageObligation.v1",
        "obligation_id": row["obligation_id"],
        "adrs_ref": row["adrs_ref"],
        "target_universe_id": row["target_universe_id"],
        "repo_locator": row["repo_locator"],
        "authority_surface": row["authority_surface"],
        "package_id": row["package_id"],
        "package_path": row["package_path"],
        "owner_role": row["owner_role"],
        "goals": row["goals"],
        "non_goals": row["non_goals"],
        "requirements": row["requirements"],
        "required_tests": row["required_tests"],
        "claim_required": row["claim_required"],
        "receipt_required": row["receipt_required"],
        "residual_required": row["residual_required"],
        "freshness_policy": row["freshness_policy"],
        "route_policy": row["route_policy"],
        "authority": False,
    }


def _check_log(output_dir: Path, evidence: dict[str, Any], stream: str) -> None:
    refs = evidence.get("log_refs")
    if not isinstance(refs, dict):
        raise JoinError(f"evidence-log-refs:{evidence.get('evidence_id')}")
    ref = refs.get(stream)
    if not isinstance(ref, str) or not ref or Path(ref).is_absolute() or ".." in Path(ref).parts:
        raise JoinError(f"evidence-log-ref:{evidence.get('evidence_id')}:{stream}")
    target = (output_dir / ref).resolve()
    root = output_dir.resolve()
    if root not in target.parents or not target.is_file() or target.is_symlink():
        raise JoinError(f"evidence-log-missing:{evidence.get('evidence_id')}:{stream}")
    expected = evidence.get(f"{stream}_digest")
    if not isinstance(expected, str) or not DIGEST_RE.fullmatch(expected):
        raise JoinError(f"evidence-log-digest-shape:{evidence.get('evidence_id')}:{stream}")
    if sha256_bytes(target.read_bytes()) != expected:
        raise JoinError(f"evidence-log-digest:{evidence.get('evidence_id')}:{stream}")


def _check_evidence(output_dir: Path, package_id: str, evidence: dict[str, Any]) -> None:
    if evidence.get("kind") != "ops.packageTestEvidence.v1" or evidence.get("authority") is not False:
        raise JoinError(f"evidence-boundary:{package_id}")
    if evidence.get("package_id") != package_id or evidence.get("status") != "pass" or evidence.get("exit_code") != 0:
        raise JoinError(f"evidence-state:{package_id}")
    digest = evidence.get("evidence_digest")
    if not isinstance(digest, str) or not DIGEST_RE.fullmatch(digest):
        raise JoinError(f"evidence-digest-shape:{package_id}")
    base = dict(evidence)
    del base["evidence_digest"]
    if _digest(base) != digest:
        raise JoinError(f"evidence-digest:{package_id}")
    _check_log(output_dir, evidence, "stdout")
    _check_log(output_dir, evidence, "stderr")
    outputs = evidence.get("outputs")
    if not isinstance(outputs, list) or not outputs:
        raise JoinError(f"evidence-output-required:{package_id}")


def join_packet(
    obligations_file: Path,
    output_dir: Path,
    *,
    expected_ops_commit: str | None = None,
    expected_release_digest: str | None = None,
) -> dict[str, Any]:
    obligations_file = obligations_file.resolve()
    output_dir = output_dir.resolve()
    if not obligations_file.is_file() or obligations_file.is_symlink():
        raise JoinError("obligations-regular-file-required")
    obligations_raw = obligations_file.read_bytes()
    obligations = parse_canonical_jsonl(obligations_raw)
    obligations_by_package = {row["package_id"]: row for row in obligations}
    if len(obligations_by_package) != len(obligations):
        raise JoinError("obligation-package-duplicate")

    manifest = _read_json(output_dir / "manifest.json")
    required_files = {
        "packages": "packages.jsonl",
        "assertions": "assertions.jsonl",
        "receipts": "receipts.jsonl",
        "findings": "findings.jsonl",
        "admission": "admission.jsonl",
    }
    packet_files = manifest.get("packetFiles")
    if manifest.get("kind") != "govPackageOutput.v1" or manifest.get("repoId") != "roccho-dev/ops":
        raise JoinError("manifest-identity")
    if manifest.get("projectionMode") != "exact-release-execution" or manifest.get("nonAuthority") is not True or manifest.get("status") != "pass":
        raise JoinError("manifest-state")
    if not isinstance(packet_files, list) or any(name not in packet_files for name in required_files.values()):
        raise JoinError("manifest-packet-files")
    release_digest = manifest.get("governanceReleaseDigest")
    accepted_digest = manifest.get("acceptedDecisionDigest")
    ops_commit = manifest.get("opsCommit")
    ops_tree = manifest.get("opsTree")
    if not isinstance(release_digest, str) or not DIGEST_RE.fullmatch(release_digest):
        raise JoinError("manifest-release-digest")
    if not isinstance(accepted_digest, str) or not DIGEST_RE.fullmatch(accepted_digest):
        raise JoinError("manifest-accepted-digest")
    if not isinstance(ops_commit, str) or not GIT_SHA_RE.fullmatch(ops_commit):
        raise JoinError("manifest-ops-commit")
    if not isinstance(ops_tree, str) or not GIT_TREE_RE.fullmatch(ops_tree):
        raise JoinError("manifest-ops-tree")
    if expected_ops_commit is not None and ops_commit != expected_ops_commit:
        raise JoinError(f"ops-commit-mismatch:{ops_commit}:{expected_ops_commit}")
    if expected_release_digest is not None and release_digest != expected_release_digest:
        raise JoinError(f"release-digest-mismatch:{release_digest}:{expected_release_digest}")

    rows = {name: _read_jsonl(output_dir / file) for name, file in required_files.items()}
    row_counts = manifest.get("rowCounts")
    if not isinstance(row_counts, dict):
        raise JoinError("manifest-row-counts")
    for name, values in rows.items():
        if row_counts.get(name) != len(values):
            raise JoinError(f"manifest-row-count-drift:{name}")

    packages = _unique(rows["packages"], "packageId", "package")
    assertions = _unique(rows["assertions"], "packageId", "assertion")
    receipts = _unique(rows["receipts"], "packageId", "receipt")
    admissions = _unique(rows["admission"], "packageId", "admission")
    expected_ids = set(obligations_by_package)
    for label, mapping in (("package", packages), ("assertion", assertions), ("receipt", receipts), ("admission", admissions)):
        actual = set(mapping)
        if actual != expected_ids:
            raise JoinError(f"{label}-package-set:missing={sorted(expected_ids-actual)}:extra={sorted(actual-expected_ids)}")
    if rows["findings"]:
        raise JoinError("blocking-findings-present")

    active_count = 0
    evidence_count = 0
    out_of_scope_count = 0
    for package_id in sorted(expected_ids):
        obligation = obligations_by_package[package_id]
        obligation_digest = _digest(_normalized_obligation(obligation))
        package = packages[package_id]
        assertion = assertions[package_id]
        receipt = receipts[package_id]
        admission = admissions[package_id]
        active = obligation["claim_required"] is True
        expected_status = "candidate-pass" if active else "out-of-scope"
        expected_receipt_status = "pass" if active else "out-of-scope"
        active_count += int(active)
        out_of_scope_count += int(not active)

        if package.get("kind") != "govPackageRow.v1" or package.get("repoId") != "roccho-dev/ops" or package.get("nonAuthority") is not True:
            raise JoinError(f"package-boundary:{package_id}")
        if package.get("packagePath") != obligation["package_path"] or package.get("purposeRef") != obligation["adrs_ref"]:
            raise JoinError(f"package-contract-drift:{package_id}")
        if package.get("contractRefs") != [obligation["obligation_id"]] or package.get("status") != expected_status:
            raise JoinError(f"package-status-drift:{package_id}")
        if package.get("governanceReleaseDigest") != release_digest or package.get("acceptedDecisionDigest") != accepted_digest:
            raise JoinError(f"package-release-drift:{package_id}")

        if assertion.get("kind") != "govPackageAssertion.v1" or assertion.get("repoId") != "roccho-dev/ops" or assertion.get("authority") is not False:
            raise JoinError(f"assertion-boundary:{package_id}")
        if assertion.get("obligationId") != obligation["obligation_id"] or assertion.get("obligationDigest") != obligation_digest or assertion.get("status") != expected_status:
            raise JoinError(f"assertion-obligation-drift:{package_id}")
        if assertion.get("governanceReleaseDigest") != release_digest or assertion.get("acceptedDecisionDigest") != accepted_digest:
            raise JoinError(f"assertion-release-drift:{package_id}")

        if receipt.get("kind") != "govPackageReceipt.v1" or receipt.get("repoId") != "roccho-dev/ops" or receipt.get("authority") is not False:
            raise JoinError(f"receipt-boundary:{package_id}")
        if receipt.get("status") != expected_receipt_status or receipt.get("obligationId") != obligation["obligation_id"] or receipt.get("obligationDigest") != obligation_digest:
            raise JoinError(f"receipt-obligation-drift:{package_id}")
        if receipt.get("governanceReleaseDigest") != release_digest or receipt.get("acceptedDecisionDigest") != accepted_digest:
            raise JoinError(f"receipt-release-drift:{package_id}")
        if receipt.get("repoCommit") != ops_commit or receipt.get("repoTree") != ops_tree:
            raise JoinError(f"receipt-source-drift:{package_id}")
        if not isinstance(receipt.get("receiptDigest"), str) or not DIGEST_RE.fullmatch(receipt["receiptDigest"]):
            raise JoinError(f"receipt-digest-shape:{package_id}")
        required_tests = receipt.get("requiredTests")
        evidence = receipt.get("evidence")
        residual_refs = receipt.get("residualRefs")
        if not isinstance(required_tests, list) or not isinstance(evidence, list) or not isinstance(residual_refs, list):
            raise JoinError(f"receipt-array-shape:{package_id}")
        if residual_refs:
            raise JoinError(f"receipt-residual-present:{package_id}")
        if active:
            ids = [row.get("test_id") for row in required_tests]
            if ids != obligation["required_tests"] or len(evidence) != len(ids):
                raise JoinError(f"receipt-required-test-drift:{package_id}")
            evidence_by_id = _unique(evidence, "evidence_id", f"evidence:{package_id}")
            for required in required_tests:
                evidence_id = required.get("evidence_ref")
                evidence_digest = required.get("evidence_digest")
                observed = evidence_by_id.get(evidence_id)
                if observed is None or observed.get("evidence_digest") != evidence_digest or observed.get("test_id") != required.get("test_id"):
                    raise JoinError(f"receipt-evidence-binding:{package_id}")
                _check_evidence(output_dir, package_id, observed)
            evidence_count += len(evidence)
            if not isinstance(receipt.get("packageSource"), dict) or not receipt["packageSource"].get("objects"):
                raise JoinError(f"receipt-package-source:{package_id}")
            if not isinstance(receipt.get("entrypoints"), list) or not receipt["entrypoints"]:
                raise JoinError(f"receipt-entrypoints:{package_id}")
        else:
            if required_tests or evidence:
                raise JoinError(f"out-of-scope-evidence:{package_id}")

        if admission.get("kind") != "govPackageAdmission.v1" or admission.get("repoId") != "roccho-dev/ops" or admission.get("authority") is not False:
            raise JoinError(f"admission-boundary:{package_id}")
        if admission.get("status") != expected_status or admission.get("active") is not False or admission.get("governanceReleaseDigest") != release_digest:
            raise JoinError(f"admission-state:{package_id}")

    return {
        "kind": "governance.packageObligationExecutionJoin.v1",
        "status": "pass",
        "decision": "candidate-pass",
        "repo": "roccho-dev/ops",
        "governanceReleaseDigest": release_digest,
        "acceptedDecisionDigest": accepted_digest,
        "opsCommit": ops_commit,
        "opsTree": ops_tree,
        "obligationsSha256": sha256_bytes(obligations_raw),
        "rowCount": len(obligations),
        "activeCount": active_count,
        "outOfScopeCount": out_of_scope_count,
        "evidenceCount": evidence_count,
        "findingCount": 0,
        "organizationActiveMinted": False,
        "authority": False,
        "boundary": "exact obligation execution is candidate evidence only; final organization admission and accepted meaning remain external",
    }
