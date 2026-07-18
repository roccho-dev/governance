from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOL_ROOT = REPO_ROOT / "tools/contract-modeling"


def load_engine():
    path = TOOL_ROOT / "bin/epoch.py"
    spec = importlib.util.spec_from_file_location(
        "contract_modeling_compiler_semantics_tests", path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_rows(path: Path, rows):
    path.write_text(
        "".join(
            json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


class CompilerSemanticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([sys.executable, str(TOOL_ROOT / "fixtures/generate.py")], check=True)
        cls.engine = load_engine()
        cls.policy = cls.engine.read_json(TOOL_ROOT / "fixtures/accepted-policy.json")
        cls.candidate = subprocess.check_output(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], text=True
        ).strip()

    def rows(self):
        return self.engine.read_jsonl(TOOL_ROOT / "fixtures/claims.jsonl")

    def test_normal_batch_need_not_exercise_all_eight_outputs(self):
        rows = [
            row
            for row in self.rows()
            if row["semantic_family"] != "data-model-v1"
            or row["payload"]["request_id"] == "01-extend"
        ]
        graph = self.engine.validate_and_reduce(rows, self.policy)
        decisions = self.engine.derive_admission(graph, self.policy)
        self.assertEqual(["extend_existing"], [row["decision"] for row in decisions])

    def test_purpose_digest_binds_the_actual_edge_path(self):
        graph = self.engine.validate_and_reduce(self.rows(), self.policy)
        decision = self.engine.derive_admission(graph, self.policy)[0]
        expected = self.engine.digest_value(
            [
                "purpose:P0",
                "purpose:P1",
                "purpose:P2",
                "purpose:P3",
                "purpose:P4",
                "purpose:M0",
            ]
        )
        self.assertEqual(expected, decision["purpose_path_digest"])

    def test_quarantine_preserves_pinned_previous_current(self):
        packet = self.engine.evaluate(self.candidate, REPO_ROOT)
        previous = next(
            row
            for row in packet["previous_current"]
            if row["subject_key"] == "request:07-ambiguous"
        )
        current = next(
            row
            for row in packet["current_state"]
            if row["subject_key"] == "request:07-ambiguous"
        )
        self.assertEqual(previous, current)
        self.assertEqual(
            ["request:07-ambiguous"], packet["quarantine_preserved_subjects"]
        )

    def test_receipt_must_bind_exact_package_contract(self):
        rows = self.rows()
        receipt = next(
            row
            for row in rows
            if row["semantic_kind"] == "effect-receipt"
            and row["payload"]["receipt_id"] == "receipt:code-governance"
        )
        receipt["payload"]["contract_digest"] = "0" * 64
        with tempfile.TemporaryDirectory() as tmp:
            claims = Path(tmp) / "claims.jsonl"
            write_rows(claims, rows)
            with self.assertRaisesRegex(self.engine.ContractError, "contract digest mismatch"):
                self.engine.evaluate(self.candidate, REPO_ROOT, claims_path=claims)

    def test_stale_receipt_is_rejected(self):
        rows = self.rows()
        receipt = next(
            row
            for row in rows
            if row["semantic_kind"] == "effect-receipt"
            and row["payload"]["receipt_id"] == "receipt:code-governance"
        )
        receipt["payload"]["expires_on"] = "2026-07-17"
        with tempfile.TemporaryDirectory() as tmp:
            claims = Path(tmp) / "claims.jsonl"
            write_rows(claims, rows)
            with self.assertRaisesRegex(self.engine.ContractError, "stale receipt"):
                self.engine.evaluate(self.candidate, REPO_ROOT, claims_path=claims)

    def test_full_replay_matches_actual_incremental_application(self):
        packet = self.engine.evaluate(self.candidate, REPO_ROOT)
        self.assertTrue(packet["replay_equal"])
        self.assertEqual(packet["current_digest"], packet["incremental_digest"])

    def test_previous_current_must_be_promotion_derived(self):
        policy = dict(self.policy)
        previous = [
            {
                "current_epoch": "epoch:v0",
                "decision": "extend_existing",
                "generated_by": "manual-edit",
                "promotion_id": "promotion:previous",
                "subject_key": "request:07-ambiguous",
            }
        ]
        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as tmp:
            root = Path(tmp)
            previous_path = root / "previous.json"
            previous_path.write_text(
                json.dumps(previous, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            policy["previous_current"] = {
                "path": previous_path.relative_to(REPO_ROOT).as_posix(),
                "digest": self.engine.digest_value(previous),
            }
            policy_path = root / "policy.json"
            policy_path.write_text(
                json.dumps(policy, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(self.engine.ContractError, "not promotion-derived"):
                self.engine.evaluate(
                    self.candidate,
                    REPO_ROOT,
                    policy_path=policy_path,
                )


if __name__ == "__main__":
    unittest.main()
