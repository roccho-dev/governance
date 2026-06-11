#!/usr/bin/env python3
"""Production bridge: build specs-equivalent `package-catalog.json` +
`placement-table.json` from governance-records SSOT.

Inputs (all under `<governance-records-root>/records/specs/`):
  - package-contract.v1.jsonl   (per-package contract; `source.rawDefinition`
                                 preserves the full original specs definition)
  - repo-placement.v1.jsonl     (authoritative placement attrs per package)
  - catalog-membership.v1.jsonl (the `spec.packages` membership set — which
                                 packageIds belong in the emitted catalog)

Outputs (same schema the specs flake produced under share/spec/):
  - <out-dir>/package-catalog.json
  - <out-dir>/placement-table.json

Field mapping is taken from specs flake.nix `packageCatalog`/`placementTable`
let-bindings (each entry projects `spec.packages.<name>.<field>`). The rich
catalog fields are sourced from `record.source.rawDefinition` (the curated
`record.definition` layer only carries the feat subset consumed by
make-feat-input.py).
"""
from __future__ import annotations
import argparse, json, pathlib, sys

# packageCatalog entry fields, in specs flake.nix definition order.
CATALOG_FIELDS = [
    "package", "packageRole", "responsibility", "mission", "provides",
    "requires", "dependencyUse", "publicInterface", "usesExtensions",
    "envNeeds", "releaseNeeds", "artifactContract", "runtimeRequirements",
    "preflightRequiredTools", "officialOutput", "packageContents",
    "forbiddenOutputs", "allowedCompatCommands", "requiredCommands",
    "blockedWhen", "outputReviewGate", "requiredCheckPackages",
    "checkPackageContract", "implementationContract", "migrationContract",
    "acceptanceContract", "namingContract", "riskMitigationContract",
]
# fields the specs flake projects with `or null` / `or [ ]` defaults.
DEFAULT_NULL = {"implementationContract", "migrationContract",
                "acceptanceContract", "namingContract", "riskMitigationContract"}
DEFAULT_LIST = {"usesExtensions"}


def read_jsonl(path):
    for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            yield json.loads(line)


def build_catalog_entry(rec, package_id):
    rd = rec.get("source", {}).get("rawDefinition")
    if not isinstance(rd, dict):
        return None, "no-rawDefinition"
    entry = {}
    for f in CATALOG_FIELDS:
        if f == "package":
            entry[f] = package_id  # rd omits its own name; record key is authority
            continue
        if f in rd:
            entry[f] = rd[f]
        elif f in DEFAULT_LIST:
            entry[f] = []
        elif f in DEFAULT_NULL:
            entry[f] = None
        else:
            # specs would have errored if the attr were truly missing; record the gap.
            entry[f] = None
    return entry, None


def build_placement_entry(rec, place, package_id):
    # specs placementTable is DERIVED from spec.packages via helper fns
    # (flake.nix repoIdFor/repoCategoryFor/repoSourceUriFor). We replicate that
    # logic over the governance-records fields rather than reading stored values
    # verbatim, because the stored repoId/repoSourceUri are the raw attrs and the
    # catalog applies fallback rules.
    rd = rec.get("source", {}).get("rawDefinition")
    p = rd if isinstance(rd, dict) else rec.get("definition", {})
    if place:  # repo-placement.v1 carries the authoritative placement attrs
        p = {**p, **{k: place[k] for k in
                     ("repoId", "repoPlacement", "repoCategory", "repoSourceUri")
                     if k in place}}
    repo_placement = p.get("repoPlacement")
    # repoIdFor
    if repo_placement == "ownRepo":
        repo_id = package_id
    else:
        repo_id = p.get("repoId") or package_id
    # repoCategoryFor
    repo_category = p.get("repoCategory")
    if repo_category is None:
        repo_category = "spec" if repo_placement == "fixed" else "feat"
    # repoSourceUriFor
    repo_source_uri = p.get("repoSourceUri")
    if repo_source_uri is None:
        repo_source_uri = ("path:." if repo_placement == "fixed"
                           else f"devenv-pkg://repo/{repo_id}/target.bundle")
    return {
        "package": package_id,
        "workerName": package_id,
        "artifactName": f"{package_id}.zip",
        "repoId": repo_id,
        "repoPlacement": repo_placement,
        "repoCategory": repo_category,
        "repoSourceUri": repo_source_uri,
    }


def read_membership(path):
    """Return the set of packageIds marked as spec.packages members."""
    members = set()
    for rec in read_jsonl(path):
        if rec.get("kind") != "specs.catalogMembership.v1":
            raise SystemExit(f"unexpected record kind in {path}: {rec.get('kind')!r}")
        if rec.get("inSpecPackages") is True:
            members.add(rec["packageId"])
    if not members:
        raise SystemExit(f"membership file {path} yielded an empty package set")
    return members


def main():
    ap = argparse.ArgumentParser(
        description="emit specs-equivalent package-catalog.json + "
                    "placement-table.json from a governance-records checkout")
    ap.add_argument("governance_records_root",
                    help="path to the governance-records repo root")
    ap.add_argument("--out-dir", required=True,
                    help="directory to write package-catalog.json + "
                         "placement-table.json into")
    args = ap.parse_args()
    root = pathlib.Path(args.governance_records_root) / "records" / "specs"
    contracts = {r["packageId"]: r for r in read_jsonl(root / "package-contract.v1.jsonl")}
    placements = {p["packageId"]: p for p in read_jsonl(root / "repo-placement.v1.jsonl")}
    members = read_membership(root / "catalog-membership.v1.jsonl")

    missing = sorted(members - set(contracts))
    if missing:
        raise SystemExit(f"membership packages without package-contract record: {missing}")

    catalog, placement_table, skipped = [], [], []
    for pid in sorted(contracts):
        if pid not in members:
            continue
        rec = contracts[pid]
        entry, err = build_catalog_entry(rec, pid)
        if err:
            skipped.append((pid, err))
            continue
        catalog.append(entry)
        placement_table.append(build_placement_entry(rec, placements.get(pid), pid))

    if skipped:
        print("skipped (no dict rawDefinition):", skipped, file=sys.stderr)
        raise SystemExit("refusing to emit a partial catalog: membership packages "
                         "above lack a dict source.rawDefinition")

    outdir = pathlib.Path(args.out_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "package-catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (outdir / "placement-table.json").write_text(
        json.dumps(placement_table, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"emitted {len(catalog)} catalog entries, "
          f"{len(placement_table)} placement entries", file=sys.stderr)


if __name__ == "__main__":
    main()
