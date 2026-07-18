#!/usr/bin/env python3
from __future__ import annotations

import generate_legacy as legacy

CURRENT_DECISION_DIGEST = "cc7ac3d6618b31eb0a0979b8aa0e2bfaf6abd95646e45c740d154c8204cd00d1"


def main() -> None:
    legacy.DECISION_DIGEST = CURRENT_DECISION_DIGEST
    rows, legacy_rows = legacy.build()
    legacy.write_jsonl(legacy.ROOT / "claims.jsonl", rows)
    legacy.write_jsonl(legacy.ROOT / "legacy-responsibilities.jsonl", legacy_rows)
    print(
        legacy.json.dumps(
            {
                "claims": len(rows),
                "legacy": len(legacy_rows),
                "legacyDigest": legacy.LEGACY_DIGEST,
                "purposePathDigest": legacy.PURPOSE_PATH_DIGEST,
                "decisionDigest": CURRENT_DECISION_DIGEST,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
