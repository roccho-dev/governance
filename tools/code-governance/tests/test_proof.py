from __future__ import annotations

import ast
import copy
import json
import os
import random
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))

from adapters.github_pages import AdapterError as PageAdapterError, capture as page_capture
from adapters.file_jsonl import capture as file_capture
from adapters.local_tree import capture as local_capture
from adapters.git_tree import capture as git_capture
from engine.common import canonical_json, digest_file, read_json, read_jsonl
from engine.ledger import LedgerError, seal_text
from engine.pipeline import run as pipeline_run
from engine.reducer import ReduceError, reduce_rows
from engine.tree import TreeError, build_manifest

PYTHON = Path(os.environ.get("PROOF_PYTHON", sys.executable))
NIX_BIN = os.environ.get("NIX_BIN")
FORBIDDEN_PROVIDER_WORDS = ("github", "issue", "comment", "actions", "ssh")


class ProviderNeutralProof(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = read_json(ROOT / "schema.json")
        cls.rows = read_jsonl(ROOT / "out/transports/live/ledger.jsonl")
        cls.packet = ROOT / "out/evaluations/live-local/semantic-packet.json"

    def test_three_transport_inputs_have_identical_canonical_ledger(self) -> None:
        paths = [ROOT / "out/transports/live/ledger.jsonl", ROOT / "out/transports/synthetic-b/ledger.jsonl", ROOT / "out/transports/file/ledger.jsonl"]
        self.assertEqual(len({digest_file(path) for path in paths}), 1)
        self.assertEqual(len({path.read_bytes() for path in paths}), 1)

    def test_transport_receipts_are_distinct(self) -> None:
        paths = [ROOT / "out/transports/live/transport-receipt.json", ROOT / "out/transports/synthetic-b/transport-receipt.json", ROOT / "out/transports/file/transport-receipt.json"]
        self.assertEqual(len({digest_file(path) for path in paths}), 3)

    def test_transport_metadata_is_absent_from_semantic_rows(self) -> None:
        forbidden = {"repository", "issue", "comment_id", "actor_login", "created_at", "updated_at", "run_id", "ssh_url"}
        for row in self.rows:
            self.assertTrue(forbidden.isdisjoint(row), row)

    def test_file_adapter_normalizes_order_whitespace_and_crlf(self) -> None:
        with tempfile.TemporaryDirectory(prefix="file-adapter-") as tmp:
            output = Path(tmp) / "out"
            file_capture(ROOT / "out/generated/ledger/variant.jsonl", output)
            self.assertEqual((output / "ledger.jsonl").read_bytes(), (ROOT / "out/transports/live/ledger.jsonl").read_bytes())

    def test_page_adapter_rejects_missing_page(self) -> None:
        with tempfile.TemporaryDirectory(prefix="missing-page-") as tmp:
            pages = Path(tmp) / "pages"
            shutil.copytree(ROOT / "out/generated/github-a", pages)
            (pages / "page-0002.json").rename(pages / "page-0003.json")
            with self.assertRaises(PageAdapterError):
                page_capture(pages, "r/a", 1, "fixture-writer-a", Path(tmp) / "out")

    def test_page_adapter_rejects_edited_trusted_event(self) -> None:
        with tempfile.TemporaryDirectory(prefix="edited-event-") as tmp:
            pages = Path(tmp) / "pages"
            shutil.copytree(ROOT / "out/generated/github-a", pages)
            page_path = pages / "page-0001.json"
            page = json.loads(page_path.read_text())
            trusted = next(c for c in page["comments"] if c["author"]["login"] == "fixture-writer-a")
            trusted["updated_at"] = "2099-01-01T00:00:00Z"
            page_path.write_text(json.dumps(page, sort_keys=True, separators=(",", ":")) + "\n")
            with self.assertRaises(PageAdapterError):
                page_capture(pages, "r/a", 1, "fixture-writer-a", Path(tmp) / "out")

    def test_page_adapter_rejects_deleted_previous_event(self) -> None:
        with tempfile.TemporaryDirectory(prefix="deleted-event-") as tmp:
            tmp_path = Path(tmp)
            previous = tmp_path / "previous"
            current_pages = tmp_path / "current"
            page_capture(ROOT / "out/generated/github-a-previous", "roccho-dev/adrs", 999, "fixture-writer-a", previous)
            shutil.copytree(ROOT / "out/generated/github-a", current_pages)
            page_path = current_pages / "page-0001.json"
            page = json.loads(page_path.read_text())
            page["comments"] = [c for c in page["comments"] if c["id"] != 1001]
            page_path.write_text(json.dumps(page, sort_keys=True, separators=(",", ":")) + "\n")
            with self.assertRaises(PageAdapterError):
                page_capture(current_pages, "roccho-dev/adrs", 999, "fixture-writer-a", tmp_path / "out", previous / "transport-receipt.json")

    def test_duplicate_semantic_event_is_rejected_by_sealer(self) -> None:
        row = canonical_json(self.rows[0])
        with tempfile.TemporaryDirectory(prefix="duplicate-row-") as tmp:
            with self.assertRaises(LedgerError):
                seal_text(row + "\n" + row + "\n", Path(tmp) / "ledger.jsonl")

    def test_schema_rejects_unknown_field(self) -> None:
        rows = copy.deepcopy(self.rows)
        rows[0]["unknown"] = True
        with self.assertRaises(ReduceError):
            reduce_rows(rows, self.schema)

    def test_reducer_rejects_duplicate_event_id(self) -> None:
        rows = copy.deepcopy(self.rows)
        rows.append(copy.deepcopy(rows[0]))
        with self.assertRaises(ReduceError):
            reduce_rows(rows, self.schema)

    def test_reducer_rejects_active_subject_fork(self) -> None:
        rows = copy.deepcopy(self.rows)
        active = next(row for row in rows if row["id"] == "event:purpose.p0.2")
        fork = copy.deepcopy(active)
        fork["id"] = "event:purpose.p0.fork"
        fork["supersedes"] = []
        rows.append(fork)
        with self.assertRaises(ReduceError):
            reduce_rows(rows, self.schema)

    def test_reducer_is_order_invariant_for_many_shuffles(self) -> None:
        expected = canonical_json(reduce_rows(copy.deepcopy(self.rows), self.schema))
        for seed in range(50):
            rows = copy.deepcopy(self.rows)
            random.Random(seed).shuffle(rows)
            self.assertEqual(canonical_json(reduce_rows(rows, self.schema)), expected)

    def test_reducer_rejects_missing_superseded_event(self) -> None:
        rows = copy.deepcopy(self.rows)
        event = next(row for row in rows if row["id"] == "event:purpose.p0.2")
        event["supersedes"] = ["event:not-present"]
        with self.assertRaises(ReduceError):
            reduce_rows(rows, self.schema)

    def test_reducer_rejects_cross_subject_supersession(self) -> None:
        rows = copy.deepcopy(self.rows)
        event = next(row for row in rows if row["id"] == "event:purpose.p0.2")
        event["supersedes"] = ["event:purpose.p1.1"]
        with self.assertRaises(ReduceError):
            reduce_rows(rows, self.schema)

    def test_reducer_rejects_purpose_cycle(self) -> None:
        rows = copy.deepcopy(self.rows)
        edge = next(row for row in rows if row["subject_key"] == "edge:purpose.P4-M0")
        edge["payload"]["to_subject"] = "purpose:P2"
        with self.assertRaises(ReduceError):
            reduce_rows(rows, self.schema)

    def test_indirect_purpose_edge_requires_mechanism(self) -> None:
        rows = copy.deepcopy(self.rows)
        edge = next(row for row in rows if row["subject_key"] == "edge:purpose.P2-P3")
        del edge["payload"]["mechanism"]
        with self.assertRaises(ReduceError):
            reduce_rows(rows, self.schema)

    def test_every_rule_requires_purpose(self) -> None:
        rows = [row for row in copy.deepcopy(self.rows) if row["subject_key"] != "edge:rule-purpose:path.data"]
        with self.assertRaises(ReduceError):
            reduce_rows(rows, self.schema)

    def test_three_source_adapters_have_identical_tree(self) -> None:
        paths = [ROOT / "out/sources/local/tree.json", ROOT / "out/sources/git-path/tree.json", ROOT / "out/sources/git-file/tree.json"]
        self.assertEqual(len({path.read_bytes() for path in paths}), 1)

    def test_source_transport_receipts_are_distinct(self) -> None:
        paths = [ROOT / "out/sources/local/transport-receipt.json", ROOT / "out/sources/git-path/transport-receipt.json", ROOT / "out/sources/git-file/transport-receipt.json"]
        self.assertEqual(len({digest_file(path) for path in paths}), 3)

    def test_tree_digest_changes_on_byte_mutation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tree-mutation-") as tmp:
            root = Path(tmp) / "tree"
            shutil.copytree(ROOT / "out/sources/local/snapshot", root)
            before = build_manifest(root)["tree_sha256"]
            target = root / "fixtures/code/pass-clean/core/data/model.go"
            target.write_text(target.read_text() + "\n// semantic tree mutation\n")
            after = build_manifest(root)["tree_sha256"]
            self.assertNotEqual(before, after)

    def test_absolute_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tree-symlink-") as tmp:
            root = Path(tmp)
            (root / "bad").symlink_to("/etc/passwd")
            with self.assertRaises(TreeError):
                build_manifest(root)

    def test_three_provider_combinations_have_identical_semantic_packet(self) -> None:
        paths = [ROOT / "out/evaluations/live-local/semantic-packet.json", ROOT / "out/evaluations/synthetic-b-git-path/semantic-packet.json", ROOT / "out/evaluations/file-git-file/semantic-packet.json"]
        self.assertEqual(len({path.read_bytes() for path in paths}), 1)

    def test_semantic_packet_has_no_provider_specific_vocabulary(self) -> None:
        text = self.packet.read_text(encoding="utf-8").lower()
        for word in FORBIDDEN_PROVIDER_WORDS:
            self.assertNotIn(word, text)
        for value in ("roccho-dev/adrs", "mirror/example", "portable-ledger-bot"):
            self.assertNotIn(value, text)

    def test_engine_source_has_no_provider_specific_vocabulary(self) -> None:
        for path in sorted((ROOT / "engine").glob("*.py")):
            text = path.read_text(encoding="utf-8").lower()
            for word in FORBIDDEN_PROVIDER_WORDS:
                self.assertNotIn(word, text, f"{word} leaked into {path}")

    def test_engine_does_not_import_adapters_or_network_clients(self) -> None:
        forbidden_roots = {"adapters", "requests", "urllib", "http", "socket", "paramiko"}
        for path in sorted((ROOT / "engine").glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    roots = {alias.name.split(".")[0] for alias in node.names}
                    self.assertTrue(roots.isdisjoint(forbidden_roots), (path, roots))
                elif isinstance(node, ast.ImportFrom) and node.module:
                    self.assertNotIn(node.module.split(".")[0], forbidden_roots, (path, node.module))

    def test_flake_reads_only_semantic_packets(self) -> None:
        text = (ROOT / "nix/materialize.nix").read_text(encoding="utf-8").lower()
        self.assertNotIn("transport-receipt", text)
        self.assertIn("builtins.readfile", text)

    def test_transport_receipt_mutation_does_not_change_semantic_output(self) -> None:
        with tempfile.TemporaryDirectory(prefix="transport-mutation-") as tmp:
            mutated = Path(tmp) / "transport.json"
            value = read_json(ROOT / "out/transports/live/transport-receipt.json")
            value["locator"] = {"repository": "totally/different", "issue": 987654}
            mutated.write_text(canonical_json(value) + "\n")
            output = Path(tmp) / "evaluation"
            pipeline_run(ROOT / "out/transports/live/ledger.jsonl", ROOT / "schema.json", ROOT / "out/sources/local/snapshot", output)
            self.assertEqual((output / "semantic-packet.json").read_bytes(), self.packet.read_bytes())

    def test_semantic_ledger_mutation_changes_semantic_packet(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ledger-mutation-") as tmp:
            tmp_path = Path(tmp)
            rows = copy.deepcopy(self.rows)
            purpose = next(row for row in rows if row["id"] == "event:purpose.p0.2")
            purpose["payload"]["title"] += " changed"
            ledger = tmp_path / "ledger.jsonl"
            ledger.write_text("".join(canonical_json(row) + "\n" for row in sorted(rows, key=lambda r: r["id"])))
            output = tmp_path / "evaluation"
            pipeline_run(ledger, ROOT / "schema.json", ROOT / "out/sources/local/snapshot", output)
            self.assertNotEqual((output / "semantic-packet.json").read_bytes(), self.packet.read_bytes())

    def test_pipeline_is_repeatable(self) -> None:
        with tempfile.TemporaryDirectory(prefix="repeatability-") as tmp:
            first = Path(tmp) / "first"
            second = Path(tmp) / "second"
            args = (ROOT / "out/transports/live/ledger.jsonl", ROOT / "schema.json", ROOT / "out/sources/local/snapshot")
            pipeline_run(*args, first)
            pipeline_run(*args, second)
            self.assertEqual((first / "semantic-packet.json").read_bytes(), (second / "semantic-packet.json").read_bytes())

    def test_direct_and_ci_wrapper_outputs_match(self) -> None:
        self.assertEqual((ROOT / "out/evaluations/live-local/semantic-packet.json").read_bytes(), (ROOT / "out/evaluations/file-git-file/semantic-packet.json").read_bytes())

    def test_fixture_expectations_all_hold(self) -> None:
        result = read_json(ROOT / "out/evaluations/live-local/scanned/case-results.json")
        cases = result["cases"]
        self.assertEqual(len(cases), 11)
        self.assertTrue(all(case["expectation_met"] for case in cases))
        self.assertEqual(sum(case["actual"] == "pass" for case in cases), 1)
        self.assertEqual(sum(case["actual"] == "fail" for case in cases), 10)

    def test_positive_module_compiles_without_network(self) -> None:
        completed = subprocess.run(["go", "test", "./..."], cwd=ROOT / "fixtures/code/pass-clean", text=True, capture_output=True, check=False, env={**os.environ, "GOWORK": "off", "GOPROXY": "off", "GOSUMDB": "off"})
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    @unittest.skipUnless(NIX_BIN, "NIX_BIN is not configured")
    def test_nix_materialization_is_provider_invariant(self) -> None:
        env = {**os.environ, "NIX_CONFIG": "experimental-features = nix-command\n"}
        packets = [ROOT / "out/evaluations/live-local/semantic-packet.json", ROOT / "out/evaluations/synthetic-b-git-path/semantic-packet.json", ROOT / "out/evaluations/file-git-file/semantic-packet.json"]
        paths = []
        materializer = ROOT / "nix/materialize.nix"
        for packet in packets:
            expression = f"import {materializer} {{ packet = {packet}; }}"
            completed = subprocess.run([NIX_BIN, "eval", "--offline", "--impure", "--raw", "--expr", expression], cwd=ROOT, env=env, text=True, capture_output=True, check=True)
            paths.append(completed.stdout.strip())
        self.assertEqual(len(set(paths)), 1)
        self.assertEqual(Path(paths[0]).read_bytes(), self.packet.read_bytes())


if __name__ == "__main__":
    unittest.main(verbosity=2)
