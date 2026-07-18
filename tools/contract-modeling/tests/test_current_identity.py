from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRENT_HEAD = "c9d4d0afd0679adc2a49e40d5e9e90ca6fd8f068"
CURRENT_DIGEST = "cc7ac3d6618b31eb0a0979b8aa0e2bfaf6abd95646e45c740d154c8204cd00d1"
STALE_DIGEST = "b72502f7845ead05f61d0640ef8b3f50789c7db0afafd3764b4c19d39a9fd4e0"


class CurrentIdentityTests(unittest.TestCase):
    def test_policy_pins_current_adrs_candidate(self) -> None:
        policy = json.loads((ROOT / "fixtures/accepted-policy.json").read_text(encoding="utf-8"))
        decision = policy["decision"]
        self.assertEqual("roccho-dev/adrs#237", decision["pr"])
        self.assertEqual(CURRENT_HEAD, decision["candidate_head"])
        self.assertEqual(CURRENT_DIGEST, decision["decision_digest"])
        self.assertEqual("accepted-candidate", decision["status"])
        self.assertEqual("shadow", policy["mode"])
        self.assertFalse(policy["legacy"]["final_frozen_inventory"])
        self.assertFalse(policy["cutover"]["external_consumer_zero_proven"])
        self.assertNotIn(STALE_DIGEST, json.dumps(policy, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
