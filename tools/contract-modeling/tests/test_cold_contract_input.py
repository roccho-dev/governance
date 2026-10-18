"""Cold selection boundaries and an opt-in, CI-required real two-origin proof.

The location config is test transport only: it contains no admission booleans,
replacement bindings or generated meaning. The real proof uses existing target
bindings, native Git originals and the actual final/check-package entry.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools import package_contract_port_cold as cold
from tools.package_contract_port_common import canonical, digest

ARTIFACTS = ROOT / ".artifacts"
ARTIFACTS.mkdir(exist_ok=True)
GIT = os.environ.get("COLD_GIT", shutil.which("git") or "git")


def git(root: Path, *args: str, data: bytes | None = None) -> bytes:
    process = subprocess.run(
        [GIT, "--no-optional-locks", "-c", "core.autocrlf=false", "-c", "gc.auto=0",
         "-c", "maintenance.auto=false", "-c", "user.name=Cold fixture",
         "-c", "user.email=cold-fixture@example.invalid", "-C", str(root), *args],
        input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if process.returncode:
        raise AssertionError(process.stderr.decode(errors="replace"))
    return process.stdout


class NativeBoundaries(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="cold-native-", dir=ARTIFACTS)
        self.root = Path(self.temporary.name).resolve()
        self.assertEqual(self.root.parent, ARTIFACTS.resolve())
        git(self.root, "init", "--quiet")
        (self.root / "source.jsonl").write_bytes(b'{"id":"one"}\n')
        git(self.root, "add", "source.jsonl")
        git(self.root, "commit", "--quiet", "-m", "Synthetic native source fixture")
        self.revision = git(self.root, "rev-parse", "HEAD").decode().strip()
        self.reader = cold.GitReader(self.root, GIT)

    def tearDown(self):
        self.temporary.cleanup()

    def test_fixed_native_bytes_and_tree(self):
        held = self.reader.held("HEAD", self.revision)
        raw, blob, mode = self.reader.file(self.revision, "source.jsonl")
        self.assertEqual(raw, b'{"id":"one"}\n')
        self.assertEqual(mode, "100644")
        self.assertEqual(blob, hashlib.sha1(b"blob 13\0" + raw).hexdigest())
        self.assertEqual(len(held["tree"]), 40)

    def test_revision_expression_is_not_a_holding_ref(self):
        reference = git(self.root, "symbolic-ref", "HEAD").decode().strip()
        for expression in (reference + "~0", reference + "@{0}", self.revision):
            with self.subTest(expression=expression), self.assertRaises(cold.ColdInputError):
                self.reader.held(expression, self.revision)

    def test_path_traversal_and_symlink_are_not_source_files(self):
        for path in ("../source.jsonl", "source.jsonl/../source.jsonl", "C:/source", ""):
            with self.subTest(path=path), self.assertRaises(cold.ColdInputError):
                self.reader.file(self.revision, path)
        blob = git(self.root, "hash-object", "-w", "--stdin", data=b"source.jsonl").decode().strip()
        git(self.root, "update-index", "--add", "--cacheinfo", "120000", blob, "link")
        tree = git(self.root, "write-tree").decode().strip()
        linked = git(self.root, "commit-tree", tree, "-p", self.revision,
                     data=b"Synthetic symlink fixture\n").decode().strip()
        with self.assertRaisesRegex(cold.ColdInputError, "regular-native-blob"):
            self.reader.file(linked, "link")


class ActualColdPath(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config_path = os.environ.get("COLD_INPUT_PROOF_CONFIG")
        if not config_path:
            raise unittest.SkipTest("real Cold packet locations are required; phase4 CI supplies them")
        cls.config = json.loads(Path(config_path).read_text(encoding="utf-8"))
        cls.baselines = {}
        for target in cls.config["targets"]:
            if os.name == "nt" and target == "ops":
                continue  # The unchanged Linux receipt producer writes native newlines.
            cls.baselines[target] = cls.check(target)

    @classmethod
    def check(cls, target, **changes):
        item = cls.config["targets"][target]
        values = {
            "cold_root": Path(cls.config["coldRoot"]), "code_root": Path(cls.config["codeRoot"]),
            "git": GIT, "cold_ref": cls.config["coldRef"],
            "cold_revision": cls.config["coldRevision"], "cold_path": item["path"],
            "record_id": item["recordId"], "target_id": target,
            "bundle": Path(item["bundle"]), "target_source": Path(item["targetSource"]),
            "accepted_requirement_source": Path(item["acceptedSource"]),
            "governance_policy_source": Path(item["policySource"]),
            "contract_runtime_source": Path(item["runtimeSource"]),
            "evidence_input": Path(item["evidenceInput"]),
            "governance_candidate": cls.config["governanceCandidate"],
        }
        values.update(changes)
        return cold.check_cold_record(**values)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="cold-real-boundary-", dir=ARTIFACTS)
        self.root = Path(self.temporary.name).resolve()
        self.assertEqual(self.root.parent, ARTIFACTS.resolve())

    def tearDown(self):
        self.temporary.cleanup()

    def original(self, target):
        item = self.config["targets"][target]
        reader = cold.GitReader(Path(self.config["coldRoot"]), GIT)
        return reader.file(self.config["coldRevision"], item["path"])[0]

    def edited(self, changes):
        """A synthetic unadmitted deltaS, retaining real immutable ancestor objects."""
        # Git's immutable loose objects are read-only on Windows. Keep each
        # delta separate and let TemporaryDirectory perform its scoped cleanup.
        repo = Path(tempfile.mkdtemp(prefix="cold-", dir=self.root))
        git(repo, "init", "--quiet")
        source = Path(self.config["coldRoot"])
        common = git(source, "rev-parse", "--git-common-dir").decode().strip()
        common_path = Path(common) if Path(common).is_absolute() else source / common
        objects = (common_path.resolve() / "objects").as_posix()
        (repo / ".git/objects/info/alternates").write_text(objects + "\n", encoding="utf-8", newline="\n")
        base = self.config["coldRevision"]
        git(repo, "read-tree", base)
        for path, raw in changes.items():
            blob = git(repo, "hash-object", "-w", "--stdin", data=raw).decode().strip()
            git(repo, "update-index", "--add", "--cacheinfo", "100644", blob, path)
        tree = git(repo, "write-tree").decode().strip()
        revision = git(repo, "commit-tree", tree, "-p", base,
                       data=b"Synthetic unadmitted preservation delta; no semantic adoption\n").decode().strip()
        git(repo, "update-ref", "refs/heads/cold-proof", revision)
        return {"cold_root": repo, "cold_ref": "refs/heads/cold-proof", "cold_revision": revision}

    def test_actual_direct_original(self):
        result = self.baselines["apps"]
        self.assertEqual(result["status"], "CLOSED")
        self.assertFalse(result["authority"])
        self.assertEqual(result["payload"]["coverage"]["missing"], [])
        member = result["payload"]["consumerResult"]["packageContractClosure"]
        self.assertTrue(member["comparatorReplayed"] and member["receiptReplayed"])
        self.assertEqual(member["negativeExit"]["contract-drift"], 2)
        self.assertEqual(member["negativeExit"]["missing-admission"], 4)

    def test_real_pre_adoption_source_cannot_reuse_the_later_closed_packet(self):
        # Actual first parent of ADRS PR642, not an invented accepted flag.
        before = "896851b2e21451d2f5d4999f6687a6be387a747c"
        with self.assertRaisesRegex(cold.ColdInputError, "source-tree-entry") as caught:
            self.check("apps", cold_revision=before)
        self.assertEqual(caught.exception.status, "UNKNOWN")
        after = self.baselines["apps"]
        self.assertEqual(after["payload"]["admittedSource"]["revision"],
                         "862313008ad19a743034599792d9a8b6e470e4cf")
        self.assertEqual(after["status"], "CLOSED")

    @unittest.skipIf(os.name == "nt", "unchanged Ops receipt byte replay requires Linux; phase4 CI is required")
    def test_actual_captured_original(self):
        result = self.baselines["ops"]
        self.assertEqual(result["status"], "CLOSED")
        self.assertEqual(result["payload"]["admittedSource"]["selection"],
                         "approved-projection-to-actual-original")
        self.assertEqual(result["payload"]["consumerResult"]["remaining"], 0)

    def test_another_record_id_uses_the_same_existing_codec_and_consumer(self):
        item = self.config["targets"]["apps"]
        raw = self.original("apps").decode("utf-8")
        record_id = "preserved.second-record-for-the-same-original"
        record = {
            "schema": "adr_raw_event.v1", "raw_id": record_id, "kind": "source_content",
            "provenance": {"repo": "roccho-dev/adrs", "commit": item["acceptedRevision"],
                           "original_path": item["path"], "mode": "100644"},
            "content": {"encoding": "utf-8", "media_type": "application/x-ndjson",
                        "blocks": [{"id": record_id + ".section", "statement": raw}]},
            "relations": [{"kind": "preserves_original", "repo": "roccho-dev/adrs",
                           "commit": item["acceptedRevision"], "path": item["path"]}],
        }
        path = "decisions/retained-original-example.jsonl"
        selected = self.edited({path: (canonical(record) + "\n").encode()})
        result = self.check("apps", **selected, cold_path=path, record_id=record_id,
                            object_id=item["recordId"])
        self.assertEqual(result["status"], "CLOSED")
        self.assertEqual(result["relations"][0]["raw_id"], record_id)
        self.assertEqual(result["payload"]["required"], self.baselines["apps"]["payload"]["required"])

    def test_unadmitted_addition_does_not_change_required_or_adopt_itself(self):
        item = self.config["targets"]["apps"]
        proposal = {"schema": "adr_raw_event.v1", "raw_id": "new-unadmitted-proposal",
                    "kind": "proposal", "status": "Accepted", "accepted": True,
                    "statement": "Synthetic proposal: a label does not grant admission."}
        selected = self.edited({item["path"]: self.original("apps") + (canonical(proposal) + "\n").encode()})
        unchanged = self.check("apps", **selected)
        self.assertEqual(unchanged["payload"]["required"], self.baselines["apps"]["payload"]["required"])
        self.assertEqual(unchanged["payload"]["admittedSource"], self.baselines["apps"]["payload"]["admittedSource"])
        with self.assertRaisesRegex(cold.ColdInputError, "unadmitted"):
            self.check("apps", **selected, record_id=proposal["raw_id"])

    def test_missing_record_and_required_kind_remain_incomplete(self):
        with self.assertRaisesRegex(cold.ColdInputError, "record-missing") as caught:
            self.check("apps", record_id="not-recorded")
        self.assertEqual(caught.exception.status, "UNKNOWN")
        with self.assertRaisesRegex(cold.ColdInputError, "unsupported-or-invalid-target-binding"):
            self.check("apps", target_id="not-a-bound-target")

    def test_existing_final_rejects_wrong_candidate_and_source_bytes(self):
        with self.assertRaises(cold.ColdInputError):
            self.check("apps", governance_candidate="f" * 40)
        with self.assertRaisesRegex(cold.ColdInputError, "explicit-target-candidate-mismatch"):
            self.check("apps", target_candidate="f" * 40)
        bundle = self.root / "bundle"
        shutil.copytree(Path(self.config["targets"]["apps"]["bundle"]), bundle)
        source = bundle / "sources/adrs/apps-requirement-decision.jsonl"
        source.write_bytes(source.read_bytes() + b"\n")
        with self.assertRaises(cold.ColdInputError):
            self.check("apps", bundle=bundle)

    def test_cli_does_not_ignore_an_explicit_wrong_target_candidate(self):
        item = self.config["targets"]["apps"]
        arguments = [sys.executable, str(ROOT / "tools/check-package-contract-closure-bundle.py"),
                     "cold-check", "--target-id", "apps", "--target-candidate", "f" * 40,
                     "--cold-source", self.config["coldRoot"], "--cold-code-source", self.config["codeRoot"],
                     "--cold-ref", self.config["coldRef"], "--cold-revision", self.config["coldRevision"],
                     "--cold-path", item["path"], "--cold-record-id", item["recordId"],
                     "--git-executable", GIT, "--governance-candidate", self.config["governanceCandidate"]]
        for option, key in (("bundle", "bundle"), ("target-source", "targetSource"),
                            ("accepted-requirement-source", "acceptedSource"),
                            ("governance-policy-source", "policySource"),
                            ("contract-runtime-source", "runtimeSource"), ("evidence-input", "evidenceInput")):
            arguments.extend(["--" + option, item[key]])
        result = subprocess.run(arguments, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "UNKNOWN")
        self.assertEqual(report["payload"]["reason"], "explicit-target-candidate-mismatch")
        self.assertEqual(report["payload"]["requestedColdSource"]["path"], item["path"])
        self.assertEqual(report["payload"]["coverage"]["missingTargets"], ["apps"])

    def test_duplicate_and_conflicting_immutable_ids_are_invalid(self):
        item = self.config["targets"]["apps"]
        raw = self.original("apps")
        changed = json.loads(raw)
        changed["status"] = "contradictory content under the same immutable ID"
        for suffix, reason in ((raw, "duplicate"), ((canonical(changed) + "\n").encode(), "conflict")):
            with self.subTest(reason=reason):
                selected = self.edited({item["path"]: raw + suffix})
                with self.assertRaisesRegex(cold.ColdInputError, "record-" + reason) as caught:
                    self.check("apps", **selected)
                self.assertEqual(caught.exception.status, "INVALID")

    def test_invalid_json_utf8_and_duplicate_keys_are_invalid(self):
        item = self.config["targets"]["apps"]
        for raw in (b'{"broken":\n', b'\xff\n', b'{"raw_id":"x","raw_id":"y"}\n'):
            with self.subTest(raw=raw):
                selected = self.edited({item["path"]: raw})
                with self.assertRaises(cold.ColdInputError) as caught:
                    self.check("apps", **selected)
                self.assertEqual(caught.exception.status, "INVALID")

    def test_cold_data_cannot_choose_transform_code(self):
        selected = self.edited({"tools/materialize.py": b'raise RuntimeError("unadmitted data code ran")\n'})
        result = self.check("apps", **selected)
        self.assertEqual(result["status"], "CLOSED")
        self.assertEqual(result["payload"]["transform"]["codecGitBlob"], cold.MATERIALIZER_BLOB)

    def test_captured_shape_mode_and_original_bytes_are_checked(self):
        item = self.config["targets"]["ops"]
        rows = [json.loads(line) for line in self.original("ops").decode().splitlines() if line]
        index = next(i for i, row in enumerate(rows) if row.get("raw_id") == item["recordId"])
        cases = [("provenance", lambda row: row.update(provenance=[])),
                 ("blocks", lambda row: row["content"].update(blocks=["text"])),
                 ("mode", lambda row: row["provenance"].update(mode="100755")),
                 ("body", lambda row: row["content"]["blocks"][0].update(statement="{}"))]
        for name, mutate in cases:
            with self.subTest(name=name):
                changed = copy.deepcopy(rows)
                mutate(changed[index])
                selected = self.edited({item["path"]: ("".join(canonical(row) + "\n" for row in changed)).encode()})
                with self.assertRaises(cold.ColdInputError):
                    self.check("ops", **selected)

    def test_preserved_format_mismatch_is_structured_invalid_input(self):
        reader = cold.GitReader(Path(self.config["coldRoot"]), GIT)
        raw = reader.file(self.config["coldRevision"], "README.md")[0]
        record_id = "preserved.markdown-misdeclared-as-json"
        source = {"schema": "adr_raw_event.v1", "raw_id": record_id, "kind": "source_content",
                  "provenance": {"repo": "roccho-dev/adrs", "commit": self.config["coldRevision"],
                                 "original_path": "README.md", "mode": "100644"},
                  "content": {"encoding": "utf-8", "media_type": "application/json",
                              "blocks": [{"id": "section", "statement": raw.decode("utf-8")}]},
                  "relations": [{"kind": "preserves_original", "repo": "roccho-dev/adrs",
                                 "commit": self.config["coldRevision"], "path": "README.md"}]}
        path = "decisions/format-boundary.jsonl"
        selected = self.edited({path: (canonical(source) + "\n").encode()})
        with self.assertRaises(cold.ColdInputError) as caught:
            self.check("apps", **selected, cold_path=path, record_id=record_id)
        self.assertEqual(caught.exception.status, "INVALID")

    def test_missing_original_evidence_body_is_unknown(self):
        source = Path(self.config["targets"]["apps"]["evidenceInput"])
        evidence = self.root / "evidence"
        shutil.copytree(source, evidence)
        shutil.copytree(source.parent / (source.name + "-full"), self.root / "evidence-full")
        (evidence / "source-artifact.jsonl").unlink()
        with self.assertRaises(cold.ColdInputError) as caught:
            self.check("apps", evidence_input=evidence)
        self.assertEqual(caught.exception.status, "UNKNOWN")

    def test_stored_self_rehashed_result_cannot_replace_recomputation(self):
        actual = self.baselines["apps"]
        altered = copy.deepcopy(actual)
        member = altered["payload"]["consumerResult"]["packageContractClosure"]
        member["targetCandidate"] = "f" * 40
        member["memberDigest"] = digest({key: value for key, value in member.items() if key != "memberDigest"})
        altered["payload"]["consumerResult"]["packageContractClosureDigest"] = member["memberDigest"]
        altered["raw_id"] = "derived.contract-result." + digest(altered["payload"])[7:]
        path = self.root / "result.jsonl"
        path.write_text(canonical(altered) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(cold.ColdInputError, "result-readback-mismatch"):
            cold.readback_result(actual, path)
        path.write_text(canonical(actual) + "\n", encoding="utf-8")
        cold.readback_result(actual, path)

    def test_existing_core_invalid_state_is_preserved(self):
        item = self.config["targets"]["apps"]
        packet = json.loads((Path(item["bundle"]) / "contract-diff-input.json").read_text(encoding="utf-8"))
        packet["kind"] = "not-the-supported-input-kind"
        path = self.root / "invalid-input.json"
        path.write_text(canonical(packet), encoding="utf-8")
        cli = Path(item["runtimeSource"]) / "packages/contract-diff/bin/contract-diff.py"
        result = subprocess.run([sys.executable, str(cli), "--input", str(path), "--admission",
                                 str(Path(item["bundle"]) / "contract-diff-admission.json")],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(result.returncode, 3, result.stderr + result.stdout)
        self.assertEqual(json.loads(result.stdout)["status"], "INVALID")


if __name__ == "__main__":
    program = unittest.main(exit=False)
    result = program.result
    output = os.environ.get("COLD_INPUT_PROOF_OUTPUT")
    if output:
        destination = Path(output)
        destination.mkdir(parents=True, exist_ok=True)
        baselines = getattr(ActualColdPath, "baselines", {})
        for target, baseline in baselines.items():
            (destination / (target + ".jsonl")).write_text(canonical(baseline) + "\n", encoding="utf-8")
        report = {"authority": False, "testsRun": result.testsRun,
                  "failures": len(result.failures), "errors": len(result.errors),
                  "skipped": len(result.skipped), "checkedTargets": sorted(baselines),
                  "claimCeiling": "existing two target bindings; not all Cold records or operational adoption"}
        (destination / "result.json").write_text(canonical(report) + "\n", encoding="utf-8")
    raise SystemExit(0 if result.wasSuccessful() else 1)
