#!/usr/bin/env python3
"""Check governance's Nix default surface contract.

This is intentionally small and repo-local.  ADRs own the rule meaning;
this script is a non-authority governance check implementation.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _packages_block(flake: str) -> str:
    marker = "packages = forEachSystem"
    start = flake.find(marker)
    if start < 0:
        raise AssertionError("missing packages forEachSystem block")
    end_markers = [
        pos for pos in [
            flake.find("\n      apps =", start),
            flake.find("\n      checks =", start),
            flake.find("\n      devShells =", start),
        ]
        if pos >= 0
    ]
    end = min(end_markers) if end_markers else len(flake)
    return flake[start:end]


def check_flake(flake: str) -> list[str]:
    errors: list[str] = []

    packages = _packages_block(flake)
    if re.search(r"(^|[^A-Za-z0-9_-])default\s*=", packages):
        errors.append("packages.default is forbidden without an accepted exception")

    required_fragments = [
        "apps = forEachSystem",
        "help = helpApp;",
        "default = helpApp;",
        "mkHelpProgram",
        "nix-default-surface",
        "tools/check-nix-default-surface.py",
    ]
    for fragment in required_fragments:
        if fragment not in flake:
            errors.append(f"missing flake surface fragment: {fragment}")

    forbidden_fragments = [
        "curl ",
        "wget ",
        "gh ",
        "git push",
        "git commit",
        "date ",
    ]
    for fragment in forbidden_fragments:
        if fragment in flake:
            errors.append(f"help/check surface must not depend on hidden or remote behavior: {fragment.strip()}")

    return errors


def check_help(help_text: str) -> list[str]:
    errors: list[str] = []
    required = [
        "governance flake surface",
        "Authority boundary:",
        "adrs decides",
        "governance projects",
        "generated README/docs/help/man text is not authority",
        "Build:",
        "nix build .#bootstrap-input",
        "nix build .",
        "Intentionally unsupported",
        "Run:",
        "nix run .",
        "nix run .#help",
        "Check:",
        "nix flake check",
        "Dev shells:",
        "none exposed",
        "Default policy:",
        "packages.default is forbidden",
        "apps.default must be the same as apps.help",
    ]
    for fragment in required:
        if fragment not in help_text:
            errors.append(f"help output missing required fragment: {fragment}")

    forbidden = [
        "authoritative",
        "run migration",
        "push",
        "credential",
        "secret",
    ]
    lowered = help_text.lower()
    for fragment in forbidden:
        if fragment in lowered:
            errors.append(f"help output contains forbidden implication: {fragment}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--flake", required=True)
    parser.add_argument("--help", required=True)
    args = parser.parse_args()

    errors = []
    errors.extend(check_flake(_read(args.flake)))
    errors.extend(check_help(_read(args.help)))

    if errors:
        for error in errors:
            print(f"nix-default-surface: FAIL: {error}", file=sys.stderr)
        return 1

    print("nix-default-surface: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
