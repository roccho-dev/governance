from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from tools.package_obligations.core import canonical_json, load_fixture, sha256_bytes
from tools.package_obligations.join import JoinError, join_packet

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "fixtures" / "adrs-package-obligations" / "v1"
OPS_COMMIT = "1" * 40
OPS_TREE = "git-tree-sha1:" + "2" * 40
RELEASE = "sha256:" + "3" * 64
ACCEPTED = "sha256:" + "4" * 64


def digest(value):
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def normalized(row):
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


def write_json(path: Path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows):
    path.write_text("".join(canonical_json(row) + "\n" for row in rows), encoding="utf-8")


def make_fixture(root: Path):
    source = load_fixture(FIXTURE)
    active = copy.deepcopy(next(row for row in source.rows if row["package_id"] == "ops-package-responses"))
    inactive = copy.deepcopy(next(row for row in source.rows if not row["claim_required"]))
    obligations = sorted([active, inactive], key=lambda row: row["package_id"])
    obligations_file = root / "obligations.jsonl"
    write_jsonl(obligations_file, obligations)

    output = root / "output"
    output.mkdir()
    logs = output / "logs" / active["package_id"]
    logs.mkdir(parents=True)
    stdout = b"pass\n"
    stderr = b""
    (logs / "check.stdout").write_bytes(stdout)
    (logs / "check.stderr").write_bytes(stderr)
    evidence_base = {
        "kind": "ops.packageTestEvidence.v1",
        "evidence_id": "evidence.active",
        "package_id": active["package_id"],
        "test_id": active["required_tests"][0],
        "status": "pass",
        "exit_code": 0,
        "outputs": [{"path_digest": "sha256-fixture", "file_count": 1, "bytes": 1}],
        "stdout_digest": sha256_bytes(stdout),
        "stderr_digest": sha256_bytes(stderr),
        "log_refs": {
            "stdout": f"logs/{active['package_id']}/check.stdout",
            "stderr": f"logs/{active['package_id']}/check.stderr",
        },
        "authority": False,
    }
    evidence = {**evidence_base, "evidence_digest": digest(evidence_base)}

    package_rows = []
    assertion_rows = []
    receipt_rows = []
    admission_rows = []
    for obligation in obligations:
        package_id = obligation["package_id"]
        is_active = obligation["claim_required"]
        status = "candidate-pass" if is_active else "out-of-scope"
        receipt_status = "pass" if is_active else "out-of-scope"
        od = digest(normalized(obligation))
        package_rows.append({
            "kind": "govPackageRow.v1", "repoId": "roccho-dev/ops", "packageId": package_id,
            "packagePath": obligation["package_path"], "purposeRef": obligation["adrs_ref"],
            "contractRefs": [obligation["obligation_id"]], "status": status,
            "governanceReleaseDigest": RELEASE, "acceptedDecisionDigest": ACCEPTED, "nonAuthority": True,
        })
        assertion_rows.append({
            "kind": "govPackageAssertion.v1", "repoId": "roccho-dev/ops", "packageId": package_id,
            "obligationId": obligation["obligation_id"], "obligationDigest": od, "status": status,
            "governanceReleaseDigest": RELEASE, "acceptedDecisionDigest": ACCEPTED, "authority": False,
        })
        receipt_rows.append({
            "kind": "govPackageReceipt.v1", "repoId": "roccho-dev/ops", "packageId": package_id,
            "receiptDigest": "sha256:" + ("5" if is_active else "6") * 64,
            "governanceReleaseDigest": RELEASE, "acceptedDecisionDigest": ACCEPTED,
            "obligationId": obligation["obligation_id"], "obligationDigest": od,
            "repoCommit": OPS_COMMIT, "repoTree": OPS_TREE,
            "packageSource": {"objects": [{"path": obligation["package_path"], "type": "tree", "object_id": "git-tree-sha1:" + "7" * 40}]},
            "entrypoints": [{"kind": "source", "exists": True, "digest": "sha256:" + "8" * 64}] if is_active else [],
            "requiredTests": [{"test_id": active["required_tests"][0], "evidence_ref": evidence["evidence_id"], "evidence_digest": evidence["evidence_digest"]}] if is_active else [],
            "evidence": [evidence] if is_active else [], "residualRefs": [], "status": receipt_status, "authority": False,
        })
        admission_rows.append({
            "kind": "govPackageAdmission.v1", "repoId": "roccho-dev/ops", "packageId": package_id,
            "status": status, "active": False, "governanceReleaseDigest": RELEASE, "authority": False,
        })

    files = {
        "packages.jsonl": package_rows,
        "assertions.jsonl": assertion_rows,
        "receipts.jsonl": receipt_rows,
        "findings.jsonl": [],
        "admission.jsonl": admission_rows,
    }
    for name, rows in files.items():
        write_jsonl(output / name, rows)
    manifest = {
        "kind": "govPackageOutput.v1", "repoId": "roccho-dev/ops", "projectionMode": "exact-release-execution",
        "nonAuthority": True, "status": "pass", "governanceReleaseDigest": RELEASE,
        "acceptedDecisionDigest": ACCEPTED, "opsCommit": OPS_COMMIT, "opsTree": OPS_TREE,
        "packetFiles": ["manifest.json", *files],
        "rowCounts": {"packages": 2, "assertions": 2, "receipts": 2, "findings": 0, "admission": 2},
    }
    write_json(output / "manifest.json", manifest)
    return obligations_file, output, {"active": active["package_id"], "inactive": inactive["package_id"]}


class JoinTest(unittest.TestCase):
    def test_positive_exact_join(self):
        with tempfile.TemporaryDirectory() as tmp:
            obligations, output, _ = make_fixture(Path(tmp))
            report = join_packet(obligations, output, expected_ops_commit=OPS_COMMIT, expected_release_digest=RELEASE)
            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["activeCount"], 1)
            self.assertEqual(report["outOfScopeCount"], 1)
            self.assertFalse(report["organizationActiveMinted"])

    def test_missing_receipt_rejects(self):
        with tempfile.TemporaryDirectory() as tmp:
            obligations, output, _ = make_fixture(Path(tmp))
            rows = (output / "receipts.jsonl").read_text().splitlines()[:-1]
            (output / "receipts.jsonl").write_text("\n".join(rows) + "\n")
            with self.assertRaisesRegex(JoinError, "manifest-row-count-drift|receipt-package-set"):
                join_packet(obligations, output)

    def test_obligation_digest_tamper_rejects(self):
        with tempfile.TemporaryDirectory() as tmp:
            obligations, output, ids = make_fixture(Path(tmp))
            rows = [json.loads(line) for line in (output / "assertions.jsonl").read_text().splitlines()]
            next(row for row in rows if row["packageId"] == ids["active"])["obligationDigest"] = "sha256:" + "0" * 64
            write_jsonl(output / "assertions.jsonl", rows)
            with self.assertRaisesRegex(JoinError, "assertion-obligation-drift"):
                join_packet(obligations, output)

    def test_active_admission_rejects(self):
        with tempfile.TemporaryDirectory() as tmp:
            obligations, output, ids = make_fixture(Path(tmp))
            rows = [json.loads(line) for line in (output / "admission.jsonl").read_text().splitlines()]
            next(row for row in rows if row["packageId"] == ids["active"])["active"] = True
            write_jsonl(output / "admission.jsonl", rows)
            with self.assertRaisesRegex(JoinError, "admission-state"):
                join_packet(obligations, output)

    def test_inactive_candidate_pass_rejects(self):
        with tempfile.TemporaryDirectory() as tmp:
            obligations, output, ids = make_fixture(Path(tmp))
            rows = [json.loads(line) for line in (output / "packages.jsonl").read_text().splitlines()]
            next(row for row in rows if row["packageId"] == ids["inactive"])["status"] = "candidate-pass"
            write_jsonl(output / "packages.jsonl", rows)
            with self.assertRaisesRegex(JoinError, "package-status-drift"):
                join_packet(obligations, output)

    def test_duplicate_receipt_rejects(self):
        with tempfile.TemporaryDirectory() as tmp:
            obligations, output, _ = make_fixture(Path(tmp))
            rows = [json.loads(line) for line in (output / "receipts.jsonl").read_text().splitlines()]
            rows.append(copy.deepcopy(rows[0]))
            write_jsonl(output / "receipts.jsonl", rows)
            manifest = json.loads((output / "manifest.json").read_text())
            manifest["rowCounts"]["receipts"] = 3
            write_json(output / "manifest.json", manifest)
            with self.assertRaisesRegex(JoinError, "receipt-duplicate"):
                join_packet(obligations, output)

    def test_evidence_log_tamper_rejects(self):
        with tempfile.TemporaryDirectory() as tmp:
            obligations, output, ids = make_fixture(Path(tmp))
            log = output / "logs" / ids["active"] / "check.stdout"
            log.write_text("tamper\n")
            with self.assertRaisesRegex(JoinError, "evidence-log-digest"):
                join_packet(obligations, output)

    def test_blocking_finding_rejects(self):
        with tempfile.TemporaryDirectory() as tmp:
            obligations, output, ids = make_fixture(Path(tmp))
            write_jsonl(output / "findings.jsonl", [{"kind": "govPackageFinding.v1", "packageId": ids["active"], "blocking": True, "authority": False}])
            manifest = json.loads((output / "manifest.json").read_text())
            manifest["rowCounts"]["findings"] = 1
            write_json(output / "manifest.json", manifest)
            with self.assertRaisesRegex(JoinError, "blocking-findings-present"):
                join_packet(obligations, output)


if __name__ == "__main__":
    unittest.main()
