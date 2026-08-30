from __future__ import annotations

import io
import json
import shutil
import tarfile
import tempfile
import unittest
from pathlib import Path

from tools.gov_release.package_output import PackageOutputError, check_archive, check_directory
from tools.package_obligations.core import load_fixture
from tools.package_obligations.materialize import OUTPUT_FILE, RECEIPT_FILE, materialize

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "fixtures" / "adrs-package-obligations" / "v1"
DOC_PACKET = ROOT / "docs" / "gov-package-output"


class PackageOutputReleaseTest(unittest.TestCase):
    def make_packet(self, root: Path) -> Path:
        packet = root / "packet"
        shutil.copytree(DOC_PACKET, packet)
        generated = root / "generated"
        materialize(FIXTURE, generated)
        shutil.copy2(generated / OUTPUT_FILE, packet / OUTPUT_FILE)
        shutil.copy2(generated / RECEIPT_FILE, packet / RECEIPT_FILE)
        return packet

    def make_archive(self, packet: Path, archive_path: Path) -> None:
        with tarfile.open(archive_path, "w:gz") as archive:
            for path in sorted(packet.rglob("*")):
                archive.add(path, arcname="./" + path.relative_to(packet).as_posix(), recursive=False)

    def test_directory_and_archive_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            packet = self.make_packet(root)
            report = check_directory(packet, FIXTURE)
            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["row_count"], load_fixture(FIXTURE).manifest["row_count"])
            archive = root / "packet.tar.gz"
            self.make_archive(packet, archive)
            archived = check_archive(archive, FIXTURE)
            self.assertEqual(archived["package_obligations_sha256"], report["package_obligations_sha256"])

    def test_missing_obligations_rejects(self):
        with tempfile.TemporaryDirectory() as tmp:
            packet = self.make_packet(Path(tmp))
            (packet / OUTPUT_FILE).unlink()
            with self.assertRaisesRegex(PackageOutputError, "regular-file-required"):
                check_directory(packet, FIXTURE)

    def test_receipt_tamper_rejects(self):
        with tempfile.TemporaryDirectory() as tmp:
            packet = self.make_packet(Path(tmp))
            receipt = json.loads((packet / RECEIPT_FILE).read_text())
            receipt["row_count"] += 1
            (packet / RECEIPT_FILE).write_text(json.dumps(receipt) + "\n")
            with self.assertRaisesRegex(PackageOutputError, "materialization-receipt-drift"):
                check_directory(packet, FIXTURE)

    def test_manifest_must_declare_generated_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            packet = self.make_packet(Path(tmp))
            manifest = json.loads((packet / "manifest.json").read_text())
            manifest["packetFiles"].remove(OUTPUT_FILE)
            (packet / "manifest.json").write_text(json.dumps(manifest) + "\n")
            with self.assertRaisesRegex(PackageOutputError, "packet-file-not-declared"):
                check_directory(packet, FIXTURE)

    def test_archive_traversal_rejects(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive_path = Path(tmp) / "bad.tar.gz"
            with tarfile.open(archive_path, "w:gz") as archive:
                info = tarfile.TarInfo("../escape")
                data = b"escape"
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
            with self.assertRaisesRegex(PackageOutputError, "archive-member-path"):
                check_archive(archive_path, FIXTURE)

    def test_archive_symlink_rejects(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive_path = Path(tmp) / "bad.tar.gz"
            with tarfile.open(archive_path, "w:gz") as archive:
                info = tarfile.TarInfo("package-obligations.jsonl")
                info.type = tarfile.SYMTYPE
                info.linkname = "/etc/passwd"
                archive.addfile(info)
            with self.assertRaisesRegex(PackageOutputError, "archive-member-type"):
                check_archive(archive_path, FIXTURE)


if __name__ == "__main__":
    unittest.main()
