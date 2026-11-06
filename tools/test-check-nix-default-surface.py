#!/usr/bin/env python3
"""Exercise the public checker CLI, including its existing --help FILE port."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


CHECKER = Path(__file__).with_name("check-nix-default-surface.py")
VALID_FLAKE = """
mkHelpProgram = pkgs: pkgs.writeShellScriptBin "governance-help" "help";
packages = forEachSystem (pkgs: { bootstrap-input = "fixture"; });
      apps = forEachSystem (pkgs: { help = helpApp; default = helpApp; });
      checks = { nix-default-surface = "tools/check-nix-default-surface.py"; };
"""
VALID_HELP = """governance flake surface
Authority boundary:
  adrs decides accepted rules.
  governance projects accepted inputs.
  generated README/docs/help/man text is not authority
Build:
  nix build .#bootstrap-input
  nix build . -- Intentionally unsupported
Run:
  nix run .
  nix run .#help
Check:
  nix flake check
Dev shells:
  none exposed
Default policy:
  packages.default is forbidden
  apps.default must be the same as apps.help
"""


class CheckerCliTest(unittest.TestCase):
    def run_checker(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CHECKER), *args],
            text=True, capture_output=True, check=False,
        )

    def test_usage_is_available_without_input_files(self) -> None:
        result = self.run_checker("-h")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--flake", result.stdout)
        self.assertIn("--help", result.stdout)
        self.assertNotIn("Traceback", result.stderr)

    def test_existing_consumer_arguments_run_both_checks(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            flake, help_file = root / "flake.nix", root / "help.txt"
            flake.write_text(VALID_FLAKE, encoding="utf-8")
            help_file.write_text(VALID_HELP, encoding="utf-8")
            result = self.run_checker("--flake", str(flake), "--help", str(help_file))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "nix-default-surface: PASS")

            help_file.write_text(VALID_HELP.replace("adrs decides", "missing authority"), encoding="utf-8")
            bad_help = self.run_checker("--flake", str(flake), "--help", str(help_file))
            self.assertEqual(bad_help.returncode, 1, bad_help.stderr)
            self.assertIn("help output missing required fragment: adrs decides", bad_help.stderr)
            self.assertNotIn("nix-default-surface: PASS", bad_help.stdout)

            help_file.write_text(VALID_HELP, encoding="utf-8")
            flake.write_text(VALID_FLAKE.replace('bootstrap-input = "fixture";', 'default = "fixture";'), encoding="utf-8")
            bad_flake = self.run_checker("--flake", str(flake), "--help", str(help_file))
            self.assertEqual(bad_flake.returncode, 1, bad_flake.stderr)
            self.assertIn("packages.default is forbidden", bad_flake.stderr)
            self.assertNotIn("nix-default-surface: PASS", bad_flake.stdout)

    def test_missing_input_does_not_become_pass(self) -> None:
        result = self.run_checker("--flake", "unused.nix")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertNotIn("nix-default-surface: PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
