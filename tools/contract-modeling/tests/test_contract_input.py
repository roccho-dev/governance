"""Synthetic inputs only. No private repository, network, Release or artifact.

The trusted existing Ops comparator is read at a fixed public Git object. The
fixture's admission and its literal receipt grade are test configuration, never
actual ADRS admission, a provider execution or real-current evidence.
"""
from __future__ import annotations

import copy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools import contract_input as port
from tools.package_contract_port_cold import GitReader
from tools.package_contract_port_common import canonical, check_token, digest, STATUS_EXIT
from tools.package_contract_targets import ops

ARTIFACTS = ROOT / ".artifacts/contract-input-fixtures"
GIT = os.environ.get("CONTRACT_INPUT_GIT", shutil.which("git") or "git")
RUNTIME_REVISION = "5eb98c82417b399978c1e38aebab5e3fb39752d4"
RUNTIME_BLOB = "9613c92deb6ee12b335863a36261268976ad9cc5"
REPOSITORY = "fixture/record-owner"
RECORD = "fixture.meaning.1"


def raw(value):
    return (canonical(value) + "\n").encode()


def pin(revision, path, body):
    return port.SourcePin(REPOSITORY, revision, path, "sha256:" + hashlib.sha256(body).hexdigest())


def run_git(root, *args, data=None):
    result = subprocess.run([GIT, "--no-optional-locks", "-c", "core.autocrlf=false",
        "-c", "gc.auto=0", "-c", "maintenance.auto=false", "-c", "user.name=Fixture",
        "-c", "user.email=fixture@example.invalid", "-C", str(root), *args],
        input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise AssertionError(result.stderr.decode(errors="replace"))
    return result.stdout


def commit(root, files):
    for path, body in files.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
    run_git(root, "add", "--", *files)
    run_git(root, "commit", "--quiet", "--allow-empty", "-m", "Synthetic fixture generation")
    return run_git(root, "rev-parse", "HEAD").decode().strip()


def setUpModule():
    global core, runtime_cli
    location = os.environ.get("CONTRACT_INPUT_RUNTIME_ROOT")
    if not location:
        raise RuntimeError("CONTRACT_INPUT_RUNTIME_ROOT must name the existing public Ops fixed read view")
    reader = GitReader(Path(location), GIT)
    reader.held("HEAD", RUNTIME_REVISION)
    body, blob, _ = reader.file(RUNTIME_REVISION, "packages/contract-diff/core.py")
    if blob != RUNTIME_BLOB:
        raise AssertionError("trusted public comparator blob differs")
    if (Path(location) / "packages/contract-diff/core.py").read_bytes() != body:
        raise AssertionError("public runtime checkout differs from its fixed native core")
    cli_body, cli_blob, _ = reader.file(RUNTIME_REVISION, "packages/contract-diff/bin/contract-diff.py")
    runtime_cli = Path(location) / "packages/contract-diff/bin/contract-diff.py"
    if cli_blob != "e06a74b4323f2772fbbb69fac9ba543c4326b97b" or runtime_cli.read_bytes() != cli_body:
        raise AssertionError("public runtime CLI differs from its fixed native source")
    core = ModuleType("fixture_existing_contract_diff")
    core.__file__ = "public-ops:" + RUNTIME_REVISION + ":packages/contract-diff/core.py"
    exec(compile(body, core.__file__, "exec"), core.__dict__)


class InputFixtures(unittest.TestCase):
    def setUp(self):
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="owned-", dir=ARTIFACTS)
        self.root = Path(self.temp.name).resolve()
        self.assertEqual(self.root.parent, ARTIFACTS.resolve())
        self.no_network = patch.object(socket, "socket", side_effect=AssertionError("network forbidden"))
        self.no_network.start()
        self.commands = []
        original_run = subprocess.run
        def local_git_only(args, *a, **kw):
            if args[0] == GIT:
                self.assertFalse(set(args) & {"fetch", "clone", "push", "ls-remote"})
            else:
                self.assertEqual(args[:2], [sys.executable, str(runtime_cli)])
                self.assertEqual(args[2::2], ["--input", "--admission"])
                for value in args[3::2]:
                    self.assertEqual(Path(value).resolve().parent, self.root)
            self.commands.append(list(args))
            return original_run(args, *a, **kw)
        self.process_guard = patch.object(subprocess, "run", side_effect=local_git_only)
        self.process_guard.start()
        run_git(self.root, "init", "--quiet", "--initial-branch=fixture")
        self.make_fixture()

    def tearDown(self):
        self.process_guard.stop()
        self.no_network.stop()
        # Only this test's owned directory can be recursively cleaned.
        self.assertEqual(self.root.parent, ARTIFACTS.resolve())
        self.temp.cleanup()

    def make_fixture(self):
        # Independent provision and expected contract; never copy adapter output.
        body = {"capability": "final-ci-migration-consumer", "consumer": "roccho-dev/ops",
            "stage": "migration-consumer-known-mismatch",
            "target": {"provider": "github", "resource": "gov-final-scope-purpose-join/gate", "account": "proposals"},
            "slot": ops.OBLIGATION_ID, "binding": "sha256:" + "d" * 64,
            "profile": [{"role": "final-ci-receipt", "operation": "check", "readback": True, "grade": "real"}]}
        self.expected_required = {"obligation_digest": digest(body), **body}
        provider_raw = raw(self.expected_required)
        provider_rev = commit(self.root, {"provider.json": provider_raw})
        provider_source = pin(provider_rev, "provider.json", provider_raw).descriptor()
        self.candidate = provider_rev
        observations = [{"id": ops.OBLIGATION_ID, "attempt": "fixture-run", "epoch": "fixture-epoch",
                         "refs": {ops.ROLE: "fixture-receipt"}}]
        receipts = [{"id": "fixture-receipt", "obligation_id": ops.OBLIGATION_ID, "role": ops.ROLE,
            "attempt": "fixture-run", "epoch": "fixture-epoch", "source": provider_source,
            "target": body["target"], "slot": body["slot"], "operation": "check",
            "status": "PASS", "readback": "PASS", "grade": "real"}]
        obs_raw, receipt_raw = raw(observations), raw(receipts)
        evidence_rev = commit(self.root, {"observations.json": obs_raw, "receipts.json": receipt_raw})
        decision = {"stableRequiredCheck": "gov-final-scope-purpose-join / gate", "contractCanonicalDigest": "d" * 64}
        rollout = {"repositories": [{"assertionId": ops.OBLIGATION_ID, "repository": "roccho-dev/ops",
            "acceptedBundleDigest": "sha256:" + "d" * 64, "role": body["stage"], "branch": "proposals"}]}
        self.record = {"schema": "adr_raw_event.v1", "raw_id": RECORD, "kind": "claim", "authority": False,
                       "status": "synthetic-not-admitted", "payload": {"decision": decision, "rollout": rollout}}
        meaning_raw = raw(self.record)
        meaning_rev = commit(self.root, {"meaning.jsonl": meaning_raw})
        self.meaning_pin = pin(meaning_rev, "meaning.jsonl", meaning_raw)
        self.meaning_reader = self.git_reader(meaning_rev)
        selected, _ = port.select_jsonl_record(self.meaning_reader, self.meaning_pin, RECORD, core)
        _, required = ops.required_contract(selected["payload"]["decision"], selected["payload"]["rollout"], digest, check_token)
        self.assertEqual(required, self.expected_required)
        self.packet = {"kind": "contractDiffInput.v1",
            "required": {"source": self.meaning_pin.descriptor(), "rows": [{"id": ops.OBLIGATION_ID, "contract": required}]},
            "provided": {"source": provider_source, "rows": [{"id": ops.OBLIGATION_ID, "contract": copy.deepcopy(self.expected_required)}]},
            "observations": {"source": pin(evidence_rev, "observations.json", obs_raw).descriptor(), "rows": observations},
            "receipts": {"source": pin(evidence_rev, "receipts.json", receipt_raw).descriptor(), "rows": receipts}}
        self.admission = {"kind": "contractDiffAdmission.v1", "scope": {"id": "fixture-only",
            "authority": self.meaning_pin.descriptor(), "epoch": "fixture-epoch", "allow_empty": False,
            "grade": "fixture", "excluded_ids": []},
            "universe": [{"id": ops.OBLIGATION_ID, "obligation_digest": self.expected_required["obligation_digest"],
                          "profile": copy.deepcopy(self.expected_required["profile"])}],
            "inventory": {}, "evidence": {"fixture-receipt": core.digest(receipts[0])}}
        self.select_fixture_inventory(self.packet, self.admission)
        self.publish_inputs(self.packet, self.admission)

    def git_reader(self, revision):
        tree = run_git(self.root, "rev-parse", revision + "^{tree}").decode().strip()
        return port.GitObjectReader(self.root, GIT, repository=REPOSITORY,
            holding_ref="refs/heads/fixture", revision=revision, tree=tree)

    def publish_inputs(self, packet, admission):
        p, a = raw(packet), raw(admission)
        revision = commit(self.root, {"packet.json": p, "admission.json": a})
        self.packet_pin, self.admission_pin = pin(revision, "packet.json", p), pin(revision, "admission.json", a)
        self.input_reader = self.git_reader(revision)
        self.memory = port.BytesReader(lambda spec: port.SuppliedBody(
            {self.packet_pin: p, self.admission_pin: a, self.meaning_pin: raw(self.record)}[spec], spec, True))

    @staticmethod
    def select_fixture_inventory(packet, admission):
        # Explicit fixture acquisition oracle, not production admission or an
        # expectation manufactured by the input-port implementation.
        admission["inventory"] = {key: {"source": copy.deepcopy(packet[key]["source"]),
            "rows_digest": core.row_digest(packet[key]["rows"]), "count": len(packet[key]["rows"])}
            for key in core.COLLECTIONS}

    def compare(self, reader):
        return port.compare_inputs(packet_reader=reader, packet_pin=self.packet_pin,
            admission_reader=reader, admission_pin=self.admission_pin, consumer=core)

    def assert_boundary(self, callback, reason, status="UNKNOWN"):
        with self.assertRaisesRegex(port.InputBoundaryError, reason) as raised:
            callback()
        self.assertEqual((raised.exception.status, raised.exception.exit_code), (status, STATUS_EXIT[status]))

    def test_jsonl_required_consumer_same_record_and_native_result(self):
        memory_record, memory_meaning = port.select_jsonl_record(self.memory, self.meaning_pin, RECORD, core)
        self.assertEqual(memory_record, self.record)
        self.assertFalse(memory_meaning.retained)
        native_result, readbacks = self.compare(self.input_reader)
        memory_result, memory_readbacks = self.compare(self.memory)
        self.assertEqual(native_result, memory_result)
        self.assertEqual(native_result["status"], "CLOSED")
        self.assertEqual(native_result["grade"], "fixture")
        self.assertFalse(native_result["authority"])
        self.assertTrue(all(x.retained for x in readbacks.values()))
        self.assertTrue(all(not x.retained and x.native is None for x in memory_readbacks.values()))
        result_record = {"schema": "adr_raw_event.v1", "raw_id": "derived.fixture.result", "kind": "fact",
            "authority": False, "status": native_result["status"],
            "relations": [{"kind": "references", "raw_id": RECORD, "source": self.meaning_pin.descriptor()}],
            "payload": {"consumerResult": native_result, "required": self.expected_required,
                        "candidate": self.candidate, "claimCeiling": "SYNTHETIC_FIXTURE_ONLY"}}
        result_raw = raw(result_record)
        revision = commit(self.root, {"result.jsonl": result_raw})
        stored, proof = port.select_jsonl_record(self.git_reader(revision), pin(revision, "result.jsonl", result_raw),
                                               "derived.fixture.result", core)
        recomputed, _ = self.compare(self.input_reader)
        self.assertTrue(proof.retained)
        self.assertEqual(stored["payload"]["consumerResult"], recomputed)
        self.assertEqual(stored["payload"]["required"], self.expected_required)
        self.assertEqual(stored["payload"]["candidate"], self.candidate)
        self.assertEqual(stored["relations"][0]["source"], self.meaning_pin.descriptor())

    def test_all_four_states_are_exact_existing_comparator_results(self):
        for state in ("CLOSED", "OPEN", "INVALID", "UNKNOWN"):
            with self.subTest(state=state):
                p, a = copy.deepcopy(self.packet), copy.deepcopy(self.admission)
                if state == "OPEN":
                    p["provided"]["rows"][0]["contract"]["stage"] = "different"
                    self.select_fixture_inventory(p, a)
                elif state == "INVALID":
                    p["provided"]["rows"].append(copy.deepcopy(p["provided"]["rows"][0]))
                    self.select_fixture_inventory(p, a)
                elif state == "UNKNOWN":
                    a = {}
                self.publish_inputs(p, a)
                result, _ = self.compare(self.input_reader)
                other, _ = self.compare(self.memory)
                self.assertEqual(result, core.compare(p, a))
                self.assertEqual(other, result)
                self.assertEqual(result["status"], state)
                cli = subprocess.run([sys.executable, str(runtime_cli), "--input", str(self.root / "packet.json"),
                    "--admission", str(self.root / "admission.json")], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.assertEqual(cli.returncode, STATUS_EXIT[state])
                self.assertEqual(json.loads(cli.stdout), result)

    def test_ref_is_resolved_once_not_per_file(self):
        fixed = self.input_reader
        old_pin = self.packet_pin
        commit(self.root, {"packet.json": b'{"changed":true}\n'})
        self.assertEqual(port.read_json(fixed, old_pin, core)[0], self.packet)
        ref_reads = [args for args in self.commands if "show-ref" in args]
        before = len(ref_reads)
        port.read_json(fixed, self.admission_pin, core)
        self.assertEqual(len([args for args in self.commands if "show-ref" in args]), before)

    def test_source_identity_cannot_be_self_resigned(self):
        original = raw(self.packet)
        for changes in ({"repository": "fixture/wrong"}, {"revision": "f" * 40}, {"path": "other.json"},
                        {"digest": "sha256:" + "0" * 64}):
            with self.subTest(changes=changes):
                supplied = replace(self.packet_pin, **changes)
                reader = port.BytesReader(lambda _: port.SuppliedBody(original, supplied, True))
                self.assert_boundary(lambda: port.read_json(reader, self.packet_pin, core), "input-source-mismatch")
        tampered = original.replace(b"CLOSED", b"OPEN") + b" "
        reader = port.BytesReader(lambda _: port.SuppliedBody(tampered, self.packet_pin, True))
        self.assert_boundary(lambda: port.read_json(reader, self.packet_pin, core), "input-digest-mismatch")

    def test_unknown_origin_partial_and_missing_bytes_are_not_completion(self):
        for value, reason in ((port.SuppliedBody(raw(self.packet), None, True), "input-origin-unknown"),
                              (port.SuppliedBody(raw(self.packet), self.packet_pin, False), "input-acquisition-incomplete")):
            self.assert_boundary(lambda: port.read_json(port.BytesReader(lambda _: value), self.packet_pin, core), reason)
        self.assert_boundary(lambda: port.read_json(port.BytesReader(lambda _: {}["absent"]), self.packet_pin, core),
                             "input-bytes-missing")
        def unreadable(_):
            raise PermissionError("synthetic unreadable source")
        self.assert_boundary(lambda: port.read_json(port.BytesReader(unreadable), self.packet_pin, core),
                             "input-bytes-unreadable:PermissionError")
        self.assert_boundary(lambda: port.select_jsonl_record(self.meaning_reader, self.meaning_pin, "absent", core),
                             "jsonl-record-missing")
        self.assert_boundary(lambda: port.select_jsonl_record(self.meaning_reader, self.meaning_pin, None, core),
                             "jsonl-record-id", "INVALID")

    def test_duplicate_keys_jsonl_conflict_and_utf8_are_invalid(self):
        for body in (b'{"kind":1,"kind":2}', b'{"x":NaN}', b'\xff'):
            p = pin(self.packet_pin.revision, "bad.json", body)
            r = port.BytesReader(lambda _: port.SuppliedBody(body, p, True))
            self.assert_boundary(lambda: port.read_json(r, p, core), "input-", "INVALID")
        conflicting = raw(self.record) + raw({**self.record, "status": "other"})
        p = pin(self.meaning_pin.revision, "conflict.jsonl", conflicting)
        r = port.BytesReader(lambda _: port.SuppliedBody(conflicting, p, True))
        self.assert_boundary(lambda: port.select_jsonl_record(r, p, RECORD, core), "duplicate-or-conflict", "INVALID")

    def test_wrong_repo_revision_tree_and_unheld_revision_are_rejected(self):
        for changes, reason in (({"repository": "fixture/wrong"}, "repository-mismatch"),
                                ({"revision": "f" * 40}, "revision-mismatch")):
            self.assert_boundary(lambda: port.read_json(self.input_reader, replace(self.packet_pin, **changes), core), reason)
        self.assert_boundary(lambda: port.GitObjectReader(self.root, GIT, repository=REPOSITORY,
            holding_ref="refs/heads/fixture", revision=self.packet_pin.revision, tree="0" * 40), "tree-mismatch")
        self.assert_boundary(lambda: port.GitObjectReader(self.root, GIT, repository=REPOSITORY,
            holding_ref="refs/heads/fixture~0", revision=self.packet_pin.revision, tree="0" * 40), "git:native-git")

    def test_paths_and_native_symlinks_are_rejected(self):
        for path in ("../x", "x/../y", "/x", "C:/x", "x\\y", "x\x00y", "x\ny"):
            with self.subTest(path=path):
                self.assert_boundary(lambda: replace(self.packet_pin, path=path), "source-canonical-path", "INVALID")
        blob = run_git(self.root, "hash-object", "-w", "--stdin", data=b"packet.json").decode().strip()
        run_git(self.root, "update-index", "--add", "--cacheinfo", "120000", blob, "link")
        tree = run_git(self.root, "write-tree").decode().strip()
        revision = run_git(self.root, "commit-tree", tree, "-p", self.packet_pin.revision,
                           data=b"Synthetic symlink fixture\n").decode().strip()
        run_git(self.root, "update-ref", "refs/heads/fixture", revision)
        reader = self.git_reader(revision)
        self.assert_boundary(lambda: port.read_json(reader, pin(revision, "link", b"packet.json"), core),
                             "source-must-be-regular-native-blob")

    def test_stale_candidate_and_partial_collections_stay_nonpass(self):
        for field in ("candidate", "partial"):
            p = copy.deepcopy(self.packet)
            if field == "candidate":
                p["provided"]["source"]["revision"] = "f" * 40
            else:
                p["provided"]["rows"] = []
            # Pin the changed packet as an acquired input, but keep independent
            # trusted admission unchanged. Rehashing the packet is insufficient.
            self.publish_inputs(p, self.admission)
            result, _ = self.compare(self.memory)
            self.assertEqual(result["status"], "UNKNOWN")

    def test_data_cannot_select_validator_or_claim_native_retention(self):
        p = copy.deepcopy(self.packet)
        p["validator"] = "untrusted-code.py"
        self.publish_inputs(p, self.admission)
        result, _ = self.compare(self.memory)
        self.assertEqual(result["status"], "INVALID")
        forged = port.Readback(raw(self.packet), self.packet_pin, "native-git-objects", True, {})
        self.assert_boundary(lambda: port.read_json(port.BytesReader(lambda _: forged), self.packet_pin, core),
                             "input-receiver-shape", "INVALID")
        p = copy.deepcopy(self.packet)
        p["accepted"] = True
        p["admission"] = copy.deepcopy(self.admission)
        self.publish_inputs(p, {})
        self.assertEqual(self.compare(self.memory)[0]["status"], "UNKNOWN")

    def test_rehashed_result_does_not_replace_independent_input_pin(self):
        result, _ = self.compare(self.input_reader)
        changed = raw({**result, "status": "OPEN"})
        expected = pin(self.packet_pin.revision, "result.json", raw(result))
        resigned = pin(expected.revision, expected.path, changed)
        reader = port.BytesReader(lambda _: port.SuppliedBody(changed, resigned, True))
        self.assert_boundary(lambda: port.read_json(reader, expected, core), "input-source-mismatch")


if __name__ == "__main__":
    unittest.main()
