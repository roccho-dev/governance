from __future__ import annotations

import importlib.util
import json
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOL_ROOT = REPO_ROOT / "tools/contract-modeling"
DISPOSITIONS = {"mapped", "retired", "quarantined"}


def load_engine():
    path = TOOL_ROOT / "bin/contract_modeling.py"
    spec = importlib.util.spec_from_file_location("contract_modeling_engine_tests", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ContractModelingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([sys.executable, str(TOOL_ROOT / "fixtures/generate.py")], check=True)
        cls.engine = load_engine()
        cls.candidate = subprocess.check_output(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], text=True
        ).strip()

    def test_all_eight_admission_outputs_are_derived(self):
        policy = self.engine.read_json(TOOL_ROOT / "fixtures/accepted-policy.json")
        rows = self.engine.read_jsonl(TOOL_ROOT / "fixtures/claims.jsonl")
        graph = self.engine.validate_and_reduce(rows, policy)
        decisions = self.engine.derive_admission(graph, policy)
        self.assertEqual(set(self.engine.DECISIONS), {row["decision"] for row in decisions})
        self.assertTrue(all("approved" in row and "reason" in row for row in decisions))

    def test_recursive_paths_and_legacy_mapping_are_complete(self):
        policy = self.engine.read_json(TOOL_ROOT / "fixtures/accepted-policy.json")
        rows = self.engine.read_jsonl(TOOL_ROOT / "fixtures/claims.jsonl")
        graph = self.engine.validate_and_reduce(rows, policy)
        self.assertIn(
            "roccho-dev/governance/code-governance/engine/reducer/evaluate",
            graph.display_paths.values(),
        )
        legacy = self.engine._legacy_rows(graph)
        self.assertEqual(36, len(legacy))
        self.assertTrue(all(row["disposition"] in DISPOSITIONS for row in legacy))
        self.assertTrue(all(row["owner"] and row["reason"] for row in legacy))

    def test_order_independent_exact_evaluator(self):
        original = self.engine.read_jsonl(TOOL_ROOT / "fixtures/claims.jsonl")
        shuffled = list(original)
        random.Random(234).shuffle(shuffled)
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            shuffled_path = tmp_path / "shuffled.jsonl"
            shuffled_path.write_text(
                "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in shuffled),
                encoding="utf-8",
            )
            first = tmp_path / "first.json"
            second = tmp_path / "second.json"
            base = [
                sys.executable,
                str(TOOL_ROOT / "bin/evaluate_exact.py"),
                "--candidate-sha", self.candidate,
                "--repo-root", str(REPO_ROOT),
                "--out",
            ]
            subprocess.run(base + [str(first)], check=True, stdout=subprocess.DEVNULL)
            subprocess.run(
                base + [str(second), "--claims", str(shuffled_path)],
                check=True,
                stdout=subprocess.DEVNULL,
            )
            self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_exact_sha_selftest_and_model_only_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt = Path(tmp) / "receipt.json"
            subprocess.run(
                [
                    sys.executable,
                    str(TOOL_ROOT / "bin/run_selftest.py"),
                    "--candidate-sha", self.candidate,
                    "--repo-root", str(REPO_ROOT),
                    "--require-duckdb",
                    "--out", str(receipt),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
            )
            value = json.loads(receipt.read_text(encoding="utf-8"))
            self.assertEqual("pass", value["status"])
            self.assertGreaterEqual(value["destructive_cases"], 26)
            self.assertEqual("pass", value["model_only_package"])
            self.assertFalse(value["migration_complete"])
            self.assertFalse(value["business_outcome_achieved"])


if __name__ == "__main__":
    unittest.main()
