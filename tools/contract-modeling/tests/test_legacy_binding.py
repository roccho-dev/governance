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
        "contract_modeling_legacy_binding_tests", path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class LegacyBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([sys.executable, str(TOOL_ROOT / "fixtures/generate.py")], check=True)
        cls.engine = load_engine()
        cls.candidate = subprocess.check_output(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], text=True
        ).strip()

    def test_legacy_row_must_match_policy_source_digest(self):
        rows = self.engine.read_jsonl(TOOL_ROOT / "fixtures/claims.jsonl")
        legacy = next(row for row in rows if row["row_kind"] == "legacy-mapping")
        legacy["payload"]["legacy_source_digest"] = "0" * 64
        with tempfile.TemporaryDirectory() as tmp:
            claims = Path(tmp) / "claims.jsonl"
            claims.write_text(
                "".join(
                    json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
                    for row in rows
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(self.engine.ContractError, "policy source digest"):
                self.engine.evaluate(self.candidate, REPO_ROOT, claims_path=claims)

    def test_legacy_universe_digest_is_order_independent(self):
        rows = self.engine.read_jsonl(TOOL_ROOT / "fixtures/claims.jsonl")
        legacy = [row for row in rows if row["row_kind"] == "legacy-mapping"]
        non_legacy = [row for row in rows if row["row_kind"] != "legacy-mapping"]
        reordered = non_legacy + list(reversed(legacy))
        with tempfile.TemporaryDirectory() as tmp:
            claims = Path(tmp) / "claims.jsonl"
            claims.write_text(
                "".join(
                    json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
                    for row in reordered
                ),
                encoding="utf-8",
            )
            packet = self.engine.evaluate(self.candidate, REPO_ROOT, claims_path=claims)
            self.assertEqual(36, packet["legacy_rows_total"])


if __name__ == "__main__":
    unittest.main()
