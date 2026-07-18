from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CHECKER = REPO_ROOT / "tools/check-contract-modeling-production-migration.py"


class ProductionMigrationTests(unittest.TestCase):
    def test_selftest_rejects_all_destructive_cases(self) -> None:
        result = subprocess.run(
            [sys.executable, str(CHECKER), "selftest"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        value = json.loads(result.stdout)
        self.assertEqual("pass", value["status"])
        self.assertEqual(10, value["destructiveCaseCount"])

    def test_exact_candidate_is_cutover_eligible_but_not_pre_effect_complete(self) -> None:
        candidate = subprocess.check_output(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], text=True
        ).strip()
        with tempfile.TemporaryDirectory() as temporary:
            result = subprocess.run(
                [
                    sys.executable,
                    str(CHECKER),
                    "check",
                    "--candidate-sha",
                    candidate,
                    "--out",
                    temporary,
                ],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            receipt = json.loads(result.stdout)
            self.assertEqual("candidate-pass", receipt["status"])
            self.assertFalse(receipt["migrationComplete"])
            self.assertTrue(receipt["effectReadbackRequired"])
            report = json.loads(
                (Path(temporary) / "production-migration-candidate.json").read_text()
            )
            self.assertTrue(report["productionCutoverEligible"])
            self.assertTrue(report["migrationCompleteAfterEffectReadback"])
            self.assertEqual(0, report["legacyActiveConsumerCount"])


if __name__ == "__main__":
    unittest.main()
