from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOL_ROOT = REPO_ROOT / "tools/contract-modeling"


def load_engine():
    path = TOOL_ROOT / "bin/engine.py"
    spec = importlib.util.spec_from_file_location("contract_modeling_strict_admission_tests", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class StrictAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([sys.executable, str(TOOL_ROOT / "fixtures/generate.py")], check=True)
        cls.engine = load_engine()
        cls.policy = cls.engine.read_json(TOOL_ROOT / "fixtures/accepted-policy.json")

    def rows(self):
        return self.engine.read_jsonl(TOOL_ROOT / "fixtures/claims.jsonl")

    def test_unknown_semantic_kind_fails_closed(self):
        rows = self.rows()
        rows[0]["semantic_kind"] = "unknown"
        with self.assertRaisesRegex(self.engine.ContractError, "unknown semantic family/kind"):
            self.engine.validate_and_reduce(rows, self.policy)

    def test_nested_derived_field_is_rejected(self):
        rows = self.rows()
        request = next(row for row in rows if row["semantic_family"] == "data-model-v1")
        request["payload"]["purpose"]["approved"] = True
        with self.assertRaisesRegex(self.engine.ContractError, "forbidden trusted derived fields"):
            self.engine.validate_and_reduce(rows, self.policy)

    def test_nested_provider_metadata_is_rejected(self):
        rows = self.rows()
        legacy = next(row for row in rows if row["row_kind"] == "legacy-mapping")
        legacy["payload"]["transport"] = {"url": "transport-only"}
        with self.assertRaisesRegex(self.engine.ContractError, "provider metadata is transport-only"):
            self.engine.validate_and_reduce(rows, self.policy)

    def test_graph_subject_without_parent_is_rejected(self):
        rows = self.rows()
        rows.append(
            {
                "schema_ref": "contract-modeling/envelope.v1",
                "id": "node:pkg:orphan",
                "row_kind": "subject",
                "semantic_family": "graph",
                "semantic_kind": "package",
                "subject_key": "pkg:orphan",
                "payload": {"display_name": "orphan"},
                "supersedes": [],
            }
        )
        with self.assertRaisesRegex(self.engine.ContractError, "missing containment parent"):
            self.engine.validate_and_reduce(rows, self.policy)

    def test_graph_payload_is_closed(self):
        rows = self.rows()
        graph_subject = next(
            row
            for row in rows
            if row["semantic_family"] == "graph" and row["row_kind"] == "subject"
        )
        graph_subject["payload"]["extra"] = True
        with self.assertRaisesRegex(self.engine.ContractError, "closed payload keys required"):
            self.engine.validate_and_reduce(rows, self.policy)


if __name__ == "__main__":
    unittest.main()
