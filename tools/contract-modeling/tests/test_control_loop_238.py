from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOL_ROOT = REPO_ROOT / "tools/contract-modeling"
DELTA = TOOL_ROOT / "fixtures/control-loop-238.jsonl"

EXPECTED_DECISIONS = {
    "238-01-control-loop-core": "create_new_model",
    "238-02-obligation": "extend_existing",
    "238-03-work-attempt": "extend_existing",
    "238-04-work-event": "extend_existing",
    "238-05-dispatch-projection": "add_projection",
    "238-06-claim-query": "add_query_contract",
    "238-07-result-receipt": "extend_existing",
    "238-08-observation": "extend_existing",
    "238-09-control-bundle": "extend_existing",
    "238-10-queue-migration-gap": "add_destructive_fixture",
    "238-11-authority-ambiguity": "quarantine",
    "238-12-raw-direct-queue-read": "reject",
    "238-13-semantic-gap": "add_semantic_term",
}
EXPECTED_PACKAGES = [
    "pkg:adrs:accepted-decision-ledger",
    "pkg:diagrams:semantic-visual-roundtrip",
    "pkg:edits:intent-submit-adapter",
    "pkg:envs:local-control-runtime",
    "pkg:governance:impact-obligation-compiler",
    "pkg:hq:transition-kernel",
    "pkg:hq:work-lifecycle-ledger",
    "pkg:ops:dispatch-queue-projector",
    "pkg:ops:legacy-queue-compatibility",
    "pkg:ops:local-admission-gate",
    "pkg:ops:observation-reconciler",
    "pkg:ops:worker-effect-executor",
    "pkg:ui:control-surface-projector",
    "pkg:ui:intent-submit-adapter",
]
EXPECTED_PURPOSE_PATH = [
    "purpose:CL238:P0",
    "purpose:CL238:P1",
    "purpose:CL238:P2",
    "purpose:CL238:P3",
    "purpose:CL238:P4",
    "purpose:CL238:P5",
    "purpose:CL238:P6",
    "purpose:M0",
]


def load_epoch():
    path = TOOL_ROOT / "bin/epoch.py"
    spec = importlib.util.spec_from_file_location("contract_modeling_control_loop_238", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ControlLoop238ModelingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([sys.executable, str(TOOL_ROOT / "fixtures/generate.py")], check=True)
        cls.engine = load_epoch()
        cls.candidate = subprocess.check_output(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], text=True
        ).strip()
        cls.base_rows = cls.engine.read_jsonl(TOOL_ROOT / "fixtures/claims.jsonl")
        cls.delta_rows = cls.engine.read_jsonl(DELTA)
        cls.rows = cls.base_rows + cls.delta_rows
        cls.policy = cls.engine.read_json(TOOL_ROOT / "fixtures/accepted-policy.json")

    def evaluate(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claims.jsonl"
            path.write_text(
                "".join(
                    json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
                    for row in self.rows
                ),
                encoding="utf-8",
            )
            return self.engine.evaluate(
                self.candidate,
                REPO_ROOT,
                claims_path=path,
                require_duckdb=True,
            )

    def test_jsonl_models_the_control_loop_and_derives_expected_outcomes(self):
        packet = self.evaluate()
        decisions = {
            row["request_id"]: row["decision"]
            for row in packet["decisions"]
            if row["request_id"].startswith("238-")
        }
        self.assertEqual(EXPECTED_DECISIONS, decisions)
        self.assertEqual(
            EXPECTED_PURPOSE_PATH,
            packet["purpose_paths"]["purpose:CL238:P0"],
        )
        self.assertIn(
            "roccho-dev/hq/transition-kernel/transition-kernel-core/intent-submit",
            packet["display_paths"].values(),
        )
        self.assertIn(
            "roccho-dev/ops/dispatch-queue-projector/dispatch-projector-core/dispatch-rebuild",
            packet["display_paths"].values(),
        )
        self.assertTrue(packet["replay_equal"])
        self.assertFalse(packet["authority"])
        self.assertFalse(packet["migration_complete"])
        self.assertFalse(packet["all_repositories_enforced"])
        self.assertFalse(packet["business_outcome_achieved"])

    def test_reuse_planned_and_deprecated_package_claims_are_explicit_but_not_admitted(self):
        graph = self.engine.validate_and_reduce(self.rows, self.policy)
        claims = {
            row["payload"]["package_id"]: row["payload"]
            for row in graph.active_by_subject.values()
            if row["semantic_family"] == "package-contract-v1"
            and row["row_kind"] == "claim"
            and row["payload"]["package_id"] in EXPECTED_PACKAGES
        }
        self.assertEqual(set(EXPECTED_PACKAGES), set(claims))
        lifecycle_counts = {}
        for payload in claims.values():
            lifecycle_counts[payload["lifecycle"]] = lifecycle_counts.get(payload["lifecycle"], 0) + 1
        self.assertEqual({"active": 4, "planned": 8, "deprecated": 2}, lifecycle_counts)

        packet = self.evaluate()
        admitted = {row["package_id"] for row in packet["required_packages"]}
        self.assertTrue(set(EXPECTED_PACKAGES).isdisjoint(admitted))

    def test_native_obligation_work_and_dispatch_semantic_kinds_are_not_yet_supported(self):
        for semantic_kind in ("obligation", "work-attempt", "dispatch-queue"):
            with self.subTest(semantic_kind=semantic_kind):
                bad = copy.deepcopy(self.rows)
                bad.append(
                    {
                        "schema_ref": "contract-modeling/envelope.v1",
                        "id": f"unsupported:{semantic_kind}",
                        "row_kind": "subject",
                        "semantic_family": "graph",
                        "semantic_kind": semantic_kind,
                        "subject_key": f"unsupported:{semantic_kind}",
                        "payload": {"display_name": semantic_kind},
                        "supersedes": [],
                    }
                )
                with self.assertRaisesRegex(
                    self.engine.ContractError,
                    rf"unknown semantic family/kind graph/{semantic_kind}",
                ):
                    self.engine.validate_and_reduce(bad, self.policy)


if __name__ == "__main__":
    unittest.main()
