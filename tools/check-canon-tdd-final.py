#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.gov_release.canon_tdd import CanonTddError, diagnostic_document, write_final


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        artifact = write_final(args.evidence, args.out)
    except CanonTddError as exc:
        print(json.dumps(diagnostic_document(exc.diagnostics), sort_keys=True, separators=(",", ":")), file=sys.stderr)
        return 1
    print(json.dumps({"kind": "governance.canonTddFinalWriteReceipt.v1", "artifact": str(args.out.resolve()), "artifactDigest": artifact["closureDigest"], "authority": False}, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
