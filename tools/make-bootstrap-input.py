#!/usr/bin/env python3
"""Pure projection: accepted bootstrap-minimal-acceptance decision record ->
`governance.bootstrapInput.v1` machine input consumed by the bootstrap pinned
flake-input consumer.

Authority chain (fixed premises):
  adrs raw = why; governance accepted records = accepted definition;
  this projection = machine input; bootstrap = pinned flake input consumer.

Source authority (the ONLY input; no ADR is parsed):
  records/decisions/bootstrap-minimal-acceptance.v1.jsonl
  (kind governance.bootstrapMinimalAcceptance.v1, status accepted)

The projection carries the accepted facts bootstrap may consume directly
(requiredSsot, specsOptional, outOfScope, actionableNoticesRequired) and a
typed `ssotLocations` contract whose per-SSOT URL slots are `null` because no
SSOT-location URL is an accepted governance definition yet. `null` means NOT
ACCEPTED — the consumer MUST NOT fabricate or assume a URL from it.
"""
from __future__ import annotations
import argparse, json, pathlib, hashlib

REC = "records/decisions/bootstrap-minimal-acceptance.v1.jsonl"


def read_jsonl(path):
    for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            yield json.loads(line)


def canon(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".", help="governance repo root")
    ap.add_argument("--out", default="-", help="output path or - for stdout")
    args = ap.parse_args()
    root = pathlib.Path(args.root)

    recs = [r for r in read_jsonl(root / REC) if r.get("kind") == "governance.bootstrapMinimalAcceptance.v1"]
    if len(recs) != 1:
        raise SystemExit(f"expected exactly 1 accepted bootstrap-minimal-acceptance record, found {len(recs)}")
    r = recs[0]
    if r.get("status") != "accepted":
        raise SystemExit(f"source record status is {r.get('status')!r}, expected 'accepted'")

    ac = r.get("acceptanceCriteria", {})
    mc = r.get("minimumContract", {})
    required = list(ac.get("requiredSsot", []))

    payload = {
        "recordId": r["recordId"],
        "status": r["status"],
        "requiredSsot": required,
        "specsOptional": ac.get("specsOptional"),
        "outOfScope": mc.get("outOfScope", []),
        "actionableNoticesRequired": mc.get("actionableNoticesRequired"),
        "policyRefs": r.get("policyRefs", []),
        # Typed hole: per accepted SSOT name -> URL once an accepted
        # SSOT-location record exists. null = NOT ACCEPTED in governance.
        "ssotLocations": {name: None for name in required},
    }
    digest = hashlib.sha256(canon(payload)).hexdigest()

    out = {
        "kind": "governance.bootstrapInput.v1",
        "sourceAuthority": REC,
        "rawAdrDirectAuthority": False,
        "projectionDigest": digest,
        "ssotLocationContract": (
            "ssotLocations maps each requiredSsot name to its SSOT URL once an "
            "accepted governance SSOT-location record exists. null = the URL is "
            "NOT an accepted governance definition; the consumer MUST NOT "
            "fabricate or assume a value from a null slot."
        ),
        **payload,
    }
    text = json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out == "-":
        print(text, end="")
    else:
        p = pathlib.Path(args.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
