from __future__ import annotations

import copy
import unittest

from tools.gov_release.core import (
    ReleaseError,
    digest,
    make_eligibility,
    make_engine_descriptor,
    make_manifest,
    make_nix_output_descriptor,
    reduce_manifests,
    validate_manifest,
    validate_readback,
)


class GovReleaseTest(unittest.TestCase):
    def setUp(self) -> None:
        self.decision = "sha256:" + "1" * 64
        self.engine_descriptor = make_engine_descriptor(
            repository="roccho-dev/governance",
            commit_sha="a" * 40,
        )
        self.nix_descriptor = make_nix_output_descriptor(
            package="gov-package-output",
            nar_hash="sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
        )
        self.engine = digest(self.engine_descriptor)
        self.nix = digest(self.nix_descriptor)
        self.genesis = make_manifest(
            release_id="gov-release-0000",
            sequence=0,
            previous_release_digest=None,
            supersedes_release_digest=None,
            accepted_decision_digest=self.decision,
            gov_engine_digest=self.engine,
            nix_output_digest=self.nix,
        )
        self.genesis_digest = digest(self.genesis)
        self.next_release = make_manifest(
            release_id="gov-release-0001",
            sequence=1,
            previous_release_digest=self.genesis_digest,
            supersedes_release_digest=self.genesis_digest,
            accepted_decision_digest=self.decision,
            gov_engine_digest=self.engine,
            nix_output_digest=self.nix,
        )

    def rejected(self, fn) -> None:
        with self.assertRaises((ReleaseError, KeyError, TypeError, ValueError)):
            fn()

    def test_positive_reduce_and_readback(self) -> None:
        selected = reduce_manifests([self.next_release, self.genesis])
        self.assertEqual(selected["selectedReleaseId"], "gov-release-0001")
        release_digest = digest(self.next_release)
        receipt = {
            "kind": "govReleaseReadbackReceipt.v1",
            "status": "pass",
            "releaseId": "gov-release-0001",
            "releaseDigest": release_digest,
            "observedManifestDigest": release_digest,
            "adopted": True,
            "authority": False,
            "transport": {"provider": "fixture", "releaseId": 1},
        }
        report = validate_readback(receipt, self.next_release)
        self.assertTrue(report["adopted"])

    def test_green_or_merge_alone_has_no_effect(self) -> None:
        gate = {
            "kind": "governance.finalScopePurposeJoin.gate.v6",
            "status": "pass",
            "decision": "allow",
            "candidateSha": "a" * 40,
        }
        eligibility = make_eligibility(
            candidate_sha="a" * 40,
            accepted_decision_digest=self.decision,
            gate_report=gate,
            claim_set_digest="sha256:" + "2" * 64,
            receipt_set_digest="sha256:" + "3" * 64,
        )
        self.assertTrue(eligibility["releaseEligible"])
        self.assertFalse(eligibility["releasePublished"])
        self.assertFalse(eligibility["operationalAdoptionEffect"])

    def test_manifest_mutations_rejected(self) -> None:
        cases = []
        for field, value in (
            ("acceptedDecisionDigest", "sha256:" + "8" * 64),
            ("govEngineDigest", "sha256:" + "7" * 64),
            ("nixOutputDigest", "sha256:" + "6" * 64),
            ("status", "draft"),
        ):
            bad = copy.deepcopy(self.genesis)
            bad[field] = value
            cases.append(bad)
        bad = copy.deepcopy(self.genesis)
        bad["githubRunId"] = 1
        cases.append(bad)
        bad = copy.deepcopy(self.genesis)
        del bad["nixOutputDigest"]
        cases.append(bad)
        for value in cases:
            self.rejected(lambda value=value: validate_manifest(value))

    def test_chain_mutations_rejected(self) -> None:
        self.rejected(lambda: reduce_manifests([self.next_release]))
        bad = copy.deepcopy(self.next_release)
        bad["previousReleaseDigest"] = "sha256:" + "5" * 64
        self.rejected(lambda: reduce_manifests([self.genesis, bad]))
        bad = copy.deepcopy(self.next_release)
        bad["supersedesReleaseDigest"] = "sha256:" + "4" * 64
        self.rejected(lambda: reduce_manifests([self.genesis, bad]))
        duplicate = copy.deepcopy(self.next_release)
        duplicate["releaseId"] = "other-release"
        self.rejected(lambda: reduce_manifests([self.genesis, self.next_release, duplicate]))
        replacement = copy.deepcopy(self.genesis)
        replacement["releaseId"] = self.next_release["releaseId"]
        replacement["sequence"] = 2
        replacement["previousReleaseDigest"] = digest(self.next_release)
        self.rejected(lambda: reduce_manifests([self.genesis, self.next_release, replacement]))

    def test_readback_mutations_rejected(self) -> None:
        release_digest = digest(self.next_release)
        base = {
            "kind": "govReleaseReadbackReceipt.v1",
            "status": "pass",
            "releaseId": self.next_release["releaseId"],
            "releaseDigest": release_digest,
            "observedManifestDigest": release_digest,
            "adopted": True,
            "authority": False,
        }
        for field, value in (
            ("status", "fail"),
            ("releaseId", "other"),
            ("releaseDigest", "sha256:" + "4" * 64),
            ("observedManifestDigest", "sha256:" + "5" * 64),
            ("adopted", False),
            ("authority", True),
        ):
            bad = copy.deepcopy(base)
            bad[field] = value
            self.rejected(lambda bad=bad: validate_readback(bad, self.next_release))


if __name__ == "__main__":
    unittest.main()
