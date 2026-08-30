from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from tools.package_obligations.core import ContractError, canonical_source, load_fixture, validate_fixture

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "fixtures" / "adrs-package-obligations" / "v1"


class FixtureContractTest(unittest.TestCase):
    def setUp(self) -> None:
        fixture = load_fixture(FIXTURE)
        self.manifest = copy.deepcopy(fixture.manifest)
        self.rows = [copy.deepcopy(row) for row in fixture.rows]

    def validate_rows(self, rows):
        source = canonical_source(rows)
        manifest = copy.deepcopy(self.manifest)
        import hashlib
        manifest["source_sha256"] = "sha256:" + hashlib.sha256(source).hexdigest()
        manifest["row_count"] = len(rows)
        manifest["active_package_ids"] = sorted(row["package_id"] for row in rows if row["claim_required"])
        return validate_fixture(manifest, source)

    def test_checked_in_fixture_is_closed_and_current(self):
        fixture = load_fixture(FIXTURE)
        self.assertEqual(len(fixture.rows), fixture.manifest["row_count"])
        self.assertEqual(
            sorted(row["package_id"] for row in fixture.rows if row["claim_required"]),
            ["ops-gov-package-output", "ops-package-responses", "shiftleft-admission"],
        )
        self.assertTrue(all(row["authority"] is False for row in fixture.rows))

    def test_unknown_field_rejects(self):
        self.rows[0]["unexpected"] = True
        with self.assertRaisesRegex(ContractError, "row-fields"):
            self.validate_rows(self.rows)

    def test_duplicate_package_rejects(self):
        duplicate = copy.deepcopy(self.rows[0])
        duplicate["obligation_id"] += ".copy"
        with self.assertRaisesRegex(ContractError, "source-package-duplicate"):
            self.validate_rows(self.rows + [duplicate])

    def test_active_without_test_rejects(self):
        active = next(row for row in self.rows if row["claim_required"])
        active["required_tests"] = []
        with self.assertRaisesRegex(ContractError, "active-package-test-required"):
            self.validate_rows(self.rows)

    def test_inactive_with_test_rejects(self):
        inactive = next(row for row in self.rows if not row["claim_required"])
        inactive["required_tests"] = ["invented-check"]
        with self.assertRaisesRegex(ContractError, "inactive-package-test-forbidden"):
            self.validate_rows(self.rows)

    def test_authority_cannot_be_promoted(self):
        self.rows[0]["authority"] = True
        with self.assertRaisesRegex(ContractError, "authority-must-be-false"):
            self.validate_rows(self.rows)

    def test_missing_row_is_detected_by_manifest_digest(self):
        source = canonical_source(self.rows[:-1])
        with self.assertRaisesRegex(ContractError, "manifest-source-digest-mismatch"):
            validate_fixture(self.manifest, source)

    def test_false_positive_control_accepts_rule_words_in_human_text(self):
        row = next(row for row in self.rows if not row["claim_required"])
        row["requirements"] = ["text may mention authority, adapter, and generated without changing structure"]
        self.validate_rows(self.rows)


if __name__ == "__main__":
    unittest.main()
