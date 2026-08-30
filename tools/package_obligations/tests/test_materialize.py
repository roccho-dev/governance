from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from tools.package_obligations.core import ContractError, canonical_source, load_fixture, sha256_bytes
from tools.package_obligations.materialize import (
    OUTPUT_FILE,
    RECEIPT_FILE,
    check_materialized,
    materialize,
)

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "fixtures" / "adrs-package-obligations" / "v1"


class MaterializationTest(unittest.TestCase):
    def test_two_runs_are_byte_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first"
            second = root / "second"
            a = materialize(FIXTURE, first)
            b = materialize(FIXTURE, second)
            self.assertEqual(a, b)
            self.assertEqual((first / OUTPUT_FILE).read_bytes(), (second / OUTPUT_FILE).read_bytes())
            self.assertEqual((first / RECEIPT_FILE).read_bytes(), (second / RECEIPT_FILE).read_bytes())
            self.assertEqual(check_materialized(FIXTURE, first), a)

    def test_output_is_exact_validated_source(self):
        fixture = load_fixture(FIXTURE)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out"
            receipt = materialize(FIXTURE, output)
            self.assertEqual((output / OUTPUT_FILE).read_bytes(), fixture.source_bytes)
            self.assertEqual(receipt["output_sha256"], fixture.manifest["source_sha256"])
            self.assertEqual(receipt["row_count"], len(fixture.rows))
            self.assertFalse(receipt["authority"])

    def test_output_tamper_rejects(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out"
            materialize(FIXTURE, output)
            with (output / OUTPUT_FILE).open("ab") as stream:
                stream.write(b"{}\n")
            with self.assertRaisesRegex(ContractError, "materialization-output-byte-drift"):
                check_materialized(FIXTURE, output)

    def test_receipt_tamper_rejects(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out"
            materialize(FIXTURE, output)
            receipt = json.loads((output / RECEIPT_FILE).read_text())
            receipt["row_count"] += 1
            (output / RECEIPT_FILE).write_text(json.dumps(receipt) + "\n")
            with self.assertRaisesRegex(ContractError, "materialization-receipt-drift"):
                check_materialized(FIXTURE, output)

    def test_semantic_mutation_changes_output_digest(self):
        fixture = load_fixture(FIXTURE)
        rows = [copy.deepcopy(row) for row in fixture.rows]
        rows[0]["requirements"] = ["changed semantic requirement"]
        mutated = canonical_source(rows)
        self.assertNotEqual(sha256_bytes(mutated), fixture.manifest["source_sha256"])

    def test_output_cannot_replace_fixture(self):
        with self.assertRaisesRegex(ContractError, "materialization-output-inside-fixture"):
            materialize(FIXTURE, FIXTURE / "generated")


if __name__ == "__main__":
    unittest.main()
