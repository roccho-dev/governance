#!/usr/bin/env python3
"""Check producer-to-verifier source custody through the public CLI."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PRODUCER = Path(__file__).with_name("check-package-gov-package-output-provenance.py")
ROLES = {
    "packages": "packages.jsonl",
    "assertions": "assertions.jsonl",
    "receipts": "receipts.jsonl",
    "readmeProjectionReceipt": "readmeProjectionReceipt.jsonl",
    "providerCi": "provider-ci.jsonl",
    "findings": "findings.jsonl",
    "admission": "admission.jsonl",
}


class ProducerSourceCustodyTest(unittest.TestCase):
    def run_tool(self, cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(PRODUCER), *args],
            cwd=cwd, text=True, capture_output=True, check=False,
        )

    def prepare(self, root: Path) -> tuple[Path, Path]:
        source = root / "immutable-inputs"
        source.mkdir()
        readme = source / "README.md"
        readme.write_text("# Selected downstream source\n", encoding="utf-8")
        config = source / "config.json"
        config.write_text(json.dumps({
            "kind": "govPackageOutputProducer.config.v1",
            "repoId": "roccho-dev/example",
            "repoClass": "feature_repo",
            "producer": {
                "producerRepo": "roccho-dev/governance",
                "producerRev": "selected-producer",
                "producerDigest": "sha256:selected-producer",
            },
            "inputs": {
                **{role: {"content": json.dumps({"kind": "fixture", "role": role}) + "\n"} for role in ROLES},
                "sourcePaths": [{"role": "repoReadme", "path": str(readme), "required": True}],
            },
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return config, readme

    def verify(self, cwd: Path, packet: Path) -> subprocess.CompletedProcess[str]:
        return self.run_tool(cwd, "verify", "--packet", str(packet), "--producer-rev", "selected-producer", "--producer-digest", "sha256:selected-producer", "--require-pass")

    def test_config_survives_builder_cwd_and_sources_are_still_checked(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            config, readme = self.prepare(root)
            builder = root / "temporary-builder"
            builder.mkdir()
            packet = root / "packet"
            build = self.run_tool(builder, "build", "--config", str(config), "--out", str(packet))
            self.assertEqual(build.returncode, 0, build.stderr)
            shutil.rmtree(builder)
            verifier = root / "independent-verifier"
            verifier.mkdir()

            clean = self.verify(verifier, packet)
            self.assertEqual(clean.returncode, 0, clean.stdout + clean.stderr)
            self.assertEqual(json.loads(clean.stdout)["outcome"], "pass")

            config_original = config.read_bytes()
            config.write_bytes(config_original + b" ")
            changed_config = self.verify(verifier, packet)
            self.assertEqual(changed_config.returncode, 1, changed_config.stdout + changed_config.stderr)
            self.assertIn("inputDigestMismatch", changed_config.stdout)
            config.write_bytes(config_original)

            readme.write_text("# Changed source\n", encoding="utf-8")
            changed_source = self.verify(verifier, packet)
            self.assertEqual(changed_source.returncode, 1, changed_source.stdout + changed_source.stderr)
            self.assertIn("inputDigestMismatch", changed_source.stdout)
            readme.unlink()
            missing_source = self.verify(verifier, packet)
            self.assertEqual(missing_source.returncode, 1, missing_source.stdout + missing_source.stderr)
            self.assertIn("missingSourceInput", missing_source.stdout)

    def test_missing_config_is_not_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            config, _ = self.prepare(root)
            packet = root / "packet"
            build = self.run_tool(root, "build", "--config", str(config), "--out", str(packet))
            self.assertEqual(build.returncode, 0, build.stderr)
            config.unlink()
            missing = self.verify(root, packet)
            self.assertEqual(missing.returncode, 1, missing.stdout + missing.stderr)
            self.assertIn("missingSourceInput", missing.stdout)

    def test_config_uses_the_documented_normalized_text_digest(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            config, _ = self.prepare(root)
            config.write_bytes(config.read_bytes().rstrip(b"\n"))
            packet = root / "packet"
            build = self.run_tool(root, "build", "--config", str(config), "--out", str(packet))
            self.assertEqual(build.returncode, 0, build.stderr)
            clean = self.verify(root, packet)
            self.assertEqual(clean.returncode, 0, clean.stdout + clean.stderr)


if __name__ == "__main__":
    unittest.main()
