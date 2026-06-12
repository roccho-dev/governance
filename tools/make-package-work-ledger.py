#!/usr/bin/env python3
"""make-package-work-ledger.py — governance records -> package-work-ledger.a2ui.jsonl
(+ organization-topology.a2ui.jsonl).

Deterministic projection for the board pipeline (board-view compose input).
Sibling of make-spec-catalog.py: same input ledgers, different surface.

Canonicalisation of the /tmp board-wire prototype with the gaps closed:
  - fail-loud: a missing input ledger is an error, never an empty projection
    (dc-pkgviz-b1).
  - duplicate packageId rows in a state-table ledger are an error
    (dc-pkgviz-b2).
  - provenance: every workUnit carries a governance rev sourceRef
    (dc-pkgviz-a4/i1; rev = git HEAD of the records root, no wallclock so
    output stays byte-deterministic).
"""
import argparse
import json
import pathlib
import subprocess
import sys


def fail(msg: str) -> None:
    print(f"make-package-work-ledger: ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def read_jsonl(path: pathlib.Path):
    if not path.is_file():
        fail(f"required ledger missing: {path}")
    rows = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as e:
            fail(f"{path}:{i}: invalid JSONL: {e}")
    return rows


def by_package_unique(rows, key, label):
    out = {}
    for row in rows:
        pid = row.get(key)
        if not pid:
            continue
        if pid in out:
            fail(f"duplicate packageId in {label}: {pid}")
        out[pid] = row
    return out


def git_head(root: pathlib.Path) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True
        ).stdout.strip()
    except subprocess.CalledProcessError as e:
        fail(f"cannot resolve governance rev: {e.stderr.strip()}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="governance records root (git checkout)")
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()
    root = pathlib.Path(args.root)
    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rev = git_head(root)
    contracts = read_jsonl(root / "records/specs/package-contract.v1.jsonl")
    members = read_jsonl(root / "records/specs/catalog-membership.v1.jsonl")
    placement = read_jsonl(root / "records/specs/repo-placement.v1.jsonl")
    disposition = read_jsonl(root / "records/migration/package-disposition.v1.jsonl")
    evidence = read_jsonl(root / "records/feat/build-evidence.v1.jsonl")

    contract_by = by_package_unique(contracts, "packageId", "package-contract")
    member_by = by_package_unique(members, "packageId", "catalog-membership")
    place_by = by_package_unique(
        [{**r, "packageId": r.get("packageId") or r.get("package")} for r in placement],
        "packageId", "repo-placement")
    proven = {e.get("packageId") for e in evidence
              if e.get("promotableBuildEvidence") is True and e.get("status") == "pass"}
    disp_by = {}
    for d in disposition:  # event ledger: last event wins per successor id
        for s in d.get("successorPackageIds") or []:
            disp_by[s] = d.get("disposition")
        legacy = d.get("legacyPackageId")
        if legacy and d.get("disposition", "").startswith("superseded"):
            disp_by[legacy] = d.get("disposition")

    ledger = [{"version": "v0.9", "createSurface": {
        "surfaceId": "package-work-ledger",
        "catalogId": "urn:package-work-ledger:v1",
        "sendDataModel": True}}]

    for pid in sorted(set(contract_by) | set(member_by)):
        c = contract_by.get(pid, {})
        status = c.get("status", "unknown")
        if status == "accepted":
            state = "accepted-proven" if pid in proven else "accepted-unproven"
        else:
            state = status
        place = place_by.get(pid, {})
        ledger.append({"version": "v0.9", "updateDataModel": {
            "surfaceId": "package-work-ledger",
            "path": f"/work/{pid}",
            "value": {
                "kind": "package.workUnit.v1",
                "packageId": pid,
                "repoId": place.get("repoId") or place.get("repo"),
                "state": state,
                "candidateBranch": None,
                "actorIds": [],
                "sourceRefs": [
                    {"path": "records/specs/package-contract.v1.jsonl",
                     "meaning": f"contract status={status}"},
                    {"path": "records/migration/package-disposition.v1.jsonl",
                     "meaning": f"disposition={disp_by.get(pid, 'none')}"},
                    {"path": "records/feat/build-evidence.v1.jsonl",
                     "meaning": "nix-final evidence pass" if pid in proven
                                else "no promotable evidence"},
                    {"path": f"governance@{rev}",
                     "meaning": "projection source rev"},
                ]}}})

    topo = [
        {"version": "v0.9", "createSurface": {
            "surfaceId": "organization-topology",
            "catalogId": "urn:organization-topology:v1",
            "sendDataModel": True}},
        {"version": "v0.9", "updateDataModel": {
            "surfaceId": "organization-topology", "path": "/graph",
            "value": {"kind": "organization.graph.v1",
                      "id": "governance-package-state",
                      "title": "Package state (governance ledgers projection)",
                      "sourceRefs": [{"path": f"governance@{rev}",
                                      "meaning": "governance unified repo"}]}}},
    ]

    def write(name, rows):
        (out_dir / name).write_text(
            "\n".join(json.dumps(r, ensure_ascii=False, separators=(",", ":"),
                                 sort_keys=True) for r in rows) + "\n",
            encoding="utf-8")

    write("package-work-ledger.a2ui.jsonl", ledger)
    write("organization-topology.a2ui.jsonl", topo)
    states = {}
    for r in ledger[1:]:
        s = r["updateDataModel"]["value"]["state"]
        states[s] = states.get(s, 0) + 1
    print(f"make-package-work-ledger: rev={rev[:12]} workUnits={len(ledger)-1} "
          f"states={json.dumps(states, sort_keys=True)}")


if __name__ == "__main__":
    main()
