from __future__ import annotations

import pathlib
import subprocess
import sys
import unittest


class DecisionCtlFinalGateIntegrationTest(unittest.TestCase):
    def test_focused_decisionctl_suite_is_composed_into_final_gate(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[3]
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                str(root / "packages" / "adrs318-decisionctl" / "tests"),
                "-v",
            ],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "decisionctl focused suite failed inside the accepted final gate\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
