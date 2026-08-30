from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.gov_release.canon_tdd import CanonTddError, OUTPUT_KIND, validate_final_evidence, write_final


def d(seed: str) -> str:
    return "sha256:" + hashlib.sha256(seed.encode()).hexdigest()


def complete() -> dict:
    gov_commit = "1" * 40
    gov_tree = "2" * 40
    return {
        "kind": "governance.canonTddFinalEvidence.v1",
        "scope": "p1-rule-evolution-foundation",
        "accepted_rule": {
            "decision_id": "01M18BMZDPXHY9MCV9QNJWNQ6W",
            "repository": "roccho-dev/adrs",
            "commit": "3" * 40,
            "tree": "4" * 40,
            "path": "adr/src/01M18BMZDPXHY9MCV9QNJWNQ6W-evidence-gated-rule-evolution-canon-tdd.cue",
            "digest": d("decision"),
        },
        "governance": {
            "repository": "roccho-dev/governance",
            "commit": gov_commit,
            "tree": gov_tree,
            "obligation_root": d("obligations"),
            "obligation_count": 123,
            "missing": 0,
            "extra": 0,
            "duplicate": 0,
            "unknown": 0,
            "stale": 0,
            "build_root_a": d("build"),
            "build_root_b": d("build"),
            "final_join_root": d("join"),
        },
        "ops": {
            "repository": "roccho-dev/ops",
            "commit": "5" * 40,
            "tree": "6" * 40,
            "package_claim_root": d("claims"),
            "observation_root": d("observations"),
            "finding_root": d("findings"),
            "receipt_root": d("receipts"),
            "required_observation_count": 7,
            "required_unobserved_count": 0,
        },
        "gate_self_proof": {
            "gate_digest": d("gate"),
            "rules": 7,
            "rule_ids": [f"SL-{i:03d}" for i in range(7)],
            "fixture_classes": ["good", "bad", "false-positive", "false-negative"],
            "missing_fixture_classes": 0,
            "mutation_hits": 7,
            "mutation_misses": 0,
            "good_cases": 7,
            "bad_cases": 7,
            "false_positive_cases": 7,
            "false_negative_cases": 7,
            "bad_rejected": 7,
            "false_negative_rejected": 7,
            "good_accepted": 7,
            "false_positive_accepted": 7,
            "repair_replays": 7,
            "replay_root_a": d("self-proof"),
            "replay_root_b": d("self-proof"),
        },
        "toolchain": {
            "nix_version": "2.34.4",
            "nar_hash": "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
            "required_tools": [
                {"id": "ast-grep@0.42.1", "digest": d("ast-grep")},
                {"id": "policyctl", "digest": d("policyctl")},
            ],
        },
        "final_effect": {
            "repository": "roccho-dev/governance",
            "merge_commit": gov_commit,
            "merge_tree": gov_tree,
            "remote_commit": gov_commit,
            "remote_tree": gov_tree,
            "preserved_members": True,
            "undeclared_changes": 0,
            "readback_root": d("readback"),
        },
        "publication": {
            "repository": "roccho-dev/governance",
            "tag": "p1-final/fixture",
            "asset_name": "p1-final-green.json",
            "asset_sha256": d("asset"),
            "remote_asset_sha256": d("asset"),
            "bytes": 1024,
            "manifest_digest": d("manifest"),
            "remote_manifest_digest": d("manifest"),
        },
        "replay": {
            "artifact_sha256": d("replay-artifact"),
            "fresh_evaluator": True,
            "source_clone_used": False,
            "repair_used": False,
            "output_root": d("join"),
            "expected_output_root": d("join"),
        },
        "residuals": [],
        "claim_ceiling": {
            "p2_monitoring_complete": False,
            "production_cutover": False,
            "business_outcome_achieved": False,
            "corporate_sale_outcome_achieved": False,
        },
    }


class CanonTddTest(unittest.TestCase):
    def test_complete_target_is_the_only_positive_artifact(self) -> None:
        artifact = validate_final_evidence(complete())
        self.assertEqual(artifact["kind"], OUTPUT_KIND)
        self.assertEqual(artifact["verdict"], "GREEN")
        self.assertNotIn("status", artifact)
        self.assertNotIn("phase", json.dumps(artifact).lower())

    def test_same_input_is_byte_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "evidence.json"
            evidence.write_text(json.dumps(complete(), sort_keys=True), encoding="utf-8")
            left, right = root / "left.json", root / "right.json"
            write_final(evidence, left)
            write_final(evidence, right)
            self.assertEqual(left.read_bytes(), right.read_bytes())

    def test_failures_emit_no_canonical_artifact(self) -> None:
        cases = {
            "intermediate-status": lambda x: x.__setitem__("status", "pass"),
            "missing-decision": lambda x: x["accepted_rule"].__setitem__("digest", None),
            "unobserved": lambda x: x["ops"].__setitem__("required_unobserved_count", 1),
            "missing-obligation": lambda x: x["governance"].__setitem__("missing", 1),
            "nondeterministic-obligations": lambda x: x["governance"].__setitem__("build_root_b", d("other")),
            "missing-fixture": lambda x: x["gate_self_proof"].__setitem__("missing_fixture_classes", 1),
            "mutation-miss": lambda x: x["gate_self_proof"].__setitem__("mutation_misses", 1),
            "bad-not-rejected": lambda x: x["gate_self_proof"].__setitem__("bad_rejected", 6),
            "false-negative-not-rejected": lambda x: x["gate_self_proof"].__setitem__("false_negative_rejected", 6),
            "false-positive-rejected": lambda x: x["gate_self_proof"].__setitem__("false_positive_accepted", 6),
            "repair-not-replayed": lambda x: x["gate_self_proof"].__setitem__("repair_replays", 6),
            "self-proof-nondeterministic": lambda x: x["gate_self_proof"].__setitem__("replay_root_b", d("other")),
            "tool-missing": lambda x: x["toolchain"].__setitem__("required_tools", []),
            "nar-missing": lambda x: x["toolchain"].__setitem__("nar_hash", ""),
            "merge-not-read-back": lambda x: x["final_effect"].__setitem__("remote_commit", "7" * 40),
            "undeclared-change": lambda x: x["final_effect"].__setitem__("undeclared_changes", 1),
            "asset-not-read-back": lambda x: x["publication"].__setitem__("remote_asset_sha256", d("other")),
            "manifest-not-read-back": lambda x: x["publication"].__setitem__("remote_manifest_digest", d("other")),
            "fresh-replay-missing": lambda x: x["replay"].__setitem__("fresh_evaluator", False),
            "repair-used": lambda x: x["replay"].__setitem__("repair_used", True),
            "residual": lambda x: x.__setitem__("residuals", ["open"]),
            "overclaim": lambda x: x["claim_ceiling"].__setitem__("production_cutover", True),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                value = copy.deepcopy(complete())
                mutate(value)
                root = Path(tmp)
                evidence, output = root / "evidence.json", root / "final.json"
                evidence.write_text(json.dumps(value), encoding="utf-8")
                output.write_text("stale", encoding="utf-8")
                with self.assertRaises(CanonTddError):
                    write_final(evidence, output)
                self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
