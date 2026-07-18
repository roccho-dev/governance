from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCEPTED_MERGE = "458ab4267882083de0593754d1bf9766bf8d54da"
CURRENT_DIGEST = "cc7ac3d6618b31eb0a0979b8aa0e2bfaf6abd95646e45c740d154c8204cd00d1"
STALE_DIGEST = "b72502f7845ead05f61d0640ef8b3f50789c7db0afafd3764b4c19d39a9fd4e0"


class CurrentIdentityTests(unittest.TestCase):
    def test_policy_pins_accepted_adrs_release_and_production_cutover(self) -> None:
        policy = json.loads((ROOT / "fixtures/accepted-policy.json").read_text(encoding="utf-8"))
        decision = policy["decision"]
        self.assertEqual("roccho-dev/adrs#241", decision["pr"])
        self.assertEqual(ACCEPTED_MERGE, decision["accepted_merge"])
        self.assertEqual(CURRENT_DIGEST, decision["decision_digest"])
        self.assertEqual("recursive-contract-modeling-v1.0.1", decision["release"])
        self.assertEqual("accepted", decision["status"])
        self.assertEqual("production", policy["mode"])
        self.assertTrue(policy["legacy"]["final_frozen_inventory"])
        self.assertEqual(36, policy["legacy"]["responsibility_count"])
        self.assertTrue(policy["cutover"]["external_consumer_zero_proven"])
        self.assertEqual("production", policy["cutover"]["state"])
        self.assertTrue(policy["cutover"]["migration_complete_candidate"])
        self.assertNotIn(STALE_DIGEST, json.dumps(policy, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
