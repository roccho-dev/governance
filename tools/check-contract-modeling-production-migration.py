#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "tools/contract-modeling/fixtures/accepted-policy.json"
INVENTORY = ROOT / "tools/contract-modeling/production/legacy-inventory.json"
CLOSURE = ROOT / "tools/contract-modeling/production/closure.json"
LEGACY_PATH = "specs/packages/jsonl-datamodeling-duckdb-ci"
DECISION_MERGE = "458ab4267882083de0593754d1bf9766bf8d54da"
DECISION_DIGEST = "cc7ac3d6618b31eb0a0979b8aa0e2bfaf6abd95646e45c740d154c8204cd00d1"
LEGACY_DIGEST = "cfb47ace6877dfabe7322c18448962628611d26d328b81b5689b6c184e04e76d"
ARCHIVE_DIGEST = "459d7cfd2f7ebe1bc1e6ee2a665347c030da098b2018be9ac5b590b648d87c19"
PRESERVATION_COMMIT = "c02f243375fe42635f71f7ffa6ba9be37718dfca"
SHADOW_MERGE = "495fb26a6794155586f2b7af52e7da09285fa780"
FINAL_GATE = "gov-final-scope-purpose-join / gate"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
LEGACY_IDS = [
    "schema-contracts", "field-contracts", "semantic-terms", "compatibility-edges",
    "migration-edges", "projection-contracts", "query-contracts", "destructive-cases",
    "model-decision-ledger", "promotion-ledger", "current-state",
    *[f"G{i:03d}" for i in range(1, 25)], "package-contract-abi",
]
ALLOWED_LEGACY_REFERENCES = {
    "docs/contract-modeling-153.md",
    "tools/check-contract-modeling-production-migration.py",
    "tools/contract-modeling/fixtures/accepted-policy.json",
    "tools/contract-modeling/production/closure.json",
    "tools/contract-modeling/production/legacy-inventory.json",
}


class MigrationError(ValueError):
    pass


def need(condition: bool, code: str) -> None:
    if not condition:
        raise MigrationError(code)


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    need(isinstance(value, dict), f"not-object:{path}")
    return value


def legacy_reference_paths() -> list[str]:
    proc = subprocess.run(
        ["git", "-C", str(ROOT), "grep", "-l", "-F", LEGACY_PATH, "--", "."],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode not in (0, 1):
        raise MigrationError(f"git-grep-failed:{proc.stderr.strip()}")
    return sorted(line.removeprefix("./") for line in proc.stdout.splitlines() if line.strip())


def validate(policy: dict[str, Any], inventory: dict[str, Any], closure: dict[str, Any], candidate_sha: str) -> dict[str, Any]:
    need(bool(HEX40.fullmatch(candidate_sha)), "candidate-sha")
    decision = policy.get("decision", {})
    legacy = policy.get("legacy", {})
    cutover = policy.get("cutover", {})
    need(policy.get("kind") == "contractModelingPolicyInput.v1", "policy-kind")
    need(policy.get("mode") == "production", "policy-mode")
    need(decision.get("accepted_merge") == DECISION_MERGE, "decision-merge")
    need(decision.get("decision_digest") == DECISION_DIGEST, "decision-digest")
    need(decision.get("decision_id") == "01K0E1CM000000000000000234", "decision-id")
    need(decision.get("correction_decision_id") == "01K0E1CM000000000000000235", "correction-id")
    need(decision.get("release") == "recursive-contract-modeling-v1.0.1", "release")
    need(decision.get("status") == "accepted", "decision-status")
    need(policy.get("compiler", {}).get("shadow_merge") == SHADOW_MERGE, "shadow-merge")
    need(legacy.get("source") == LEGACY_PATH, "legacy-source")
    need(legacy.get("source_digest") == LEGACY_DIGEST, "legacy-digest")
    need(legacy.get("preservation_commit") == PRESERVATION_COMMIT, "preservation-commit")
    need(legacy.get("source_archive_sha256") == ARCHIVE_DIGEST, "archive-digest")
    need(legacy.get("responsibility_count") == 36, "responsibility-count")
    need(legacy.get("final_frozen_inventory") is True, "inventory-not-frozen")
    need(cutover.get("state") == "production", "cutover-state")
    need(cutover.get("production_gate") == FINAL_GATE, "production-gate")
    need(cutover.get("legacy_active_consumer_count") == 0, "legacy-consumers")
    need(cutover.get("external_consumer_zero_proven") is True, "consumer-zero-unproven")
    need(cutover.get("anti_reintroduction_required") is True, "anti-reintroduction-disabled")
    need(cutover.get("effect_readback_required") is True, "effect-readback-disabled")
    need(cutover.get("migration_complete_candidate") is True, "migration-candidate")

    need(inventory.get("kind") == "contractModelingLegacyInventory.v1", "inventory-kind")
    need(inventory.get("status") == "frozen", "inventory-status")
    need(inventory.get("source", {}).get("responsibilityUniverseDigest") == LEGACY_DIGEST, "inventory-digest")
    need(inventory.get("source", {}).get("preservationCommit") == PRESERVATION_COMMIT, "inventory-preservation")
    need(inventory.get("source", {}).get("archiveSha256") == ARCHIVE_DIGEST, "inventory-archive")
    rows = inventory.get("responsibilities")
    need(isinstance(rows, list), "inventory-rows")
    ids = [row.get("id") for row in rows if isinstance(row, dict)]
    need(len(ids) == 36 and len(set(ids)) == 36, "inventory-cardinality")
    need(sorted(ids) == sorted(LEGACY_IDS), "inventory-universe")
    need(digest(sorted(ids)) == LEGACY_DIGEST, "inventory-universe-digest")
    need(all(row.get("disposition") == "mapped" and row.get("target") for row in rows), "inventory-disposition")
    totals = inventory.get("totals", {})
    need(totals == {"total": 36, "mapped": 36, "retired": 0, "quarantined": 0, "unexplained": 0}, "inventory-totals")
    need(inventory.get("authority") is False, "inventory-authority")

    need(closure.get("kind") == "contractModelingProductionClosure.v1", "closure-kind")
    need(closure.get("acceptedDecision", {}).get("merge") == DECISION_MERGE, "closure-decision-merge")
    need(closure.get("acceptedDecision", {}).get("digest") == DECISION_DIGEST, "closure-decision-digest")
    need(closure.get("compiler", {}).get("shadowMerge") == SHADOW_MERGE, "closure-shadow-merge")
    need(closure.get("compiler", {}).get("meaningAuthority") is False, "meaning-authority")
    need(closure.get("compiler", {}).get("effectAuthority") is False, "effect-authority")
    need(closure.get("legacy", {}).get("responsibilityCount") == 36, "closure-inventory-count")
    need(closure.get("legacy", {}).get("unexplained") == 0, "closure-unexplained")
    need(closure.get("legacy", {}).get("activeConsumerCount") == 0, "closure-consumers")
    need(closure.get("legacy", {}).get("externalConsumerZeroProven") is True, "closure-consumer-proof")
    proof = closure.get("proof", {})
    need(proof.get("requiredPackageCount") == 2, "real-packages")
    need(proof.get("modelOnlyPackageCount") == 1, "model-only-package")
    need(proof.get("eightWayAdmission") is True, "eight-way")
    need(proof.get("promotionOnlyCurrent") is True, "promotion-current")
    need(proof.get("replayEqual") is True, "replay")
    need(proof.get("compatibleVersionsShareABI") is True, "abi")
    need(proof.get("approvedRawDirectQueryCount") == 0, "raw-direct")
    need(proof.get("effectReceiptsJoined") is True, "effect-receipts")
    need(proof.get("antiReintroduction") is True, "anti-reintroduction")
    need(proof.get("productionGate") == FINAL_GATE, "closure-gate")
    need(closure.get("cutover", {}).get("state") == "production-candidate", "closure-cutover")
    need(closure.get("cutover", {}).get("effectReadbackRequired") is True, "closure-readback")
    need(closure.get("cutover", {}).get("migrationCompleteBeforeEffectReadback") is False, "pre-effect-overclaim")
    need(closure.get("cutover", {}).get("migrationCompleteAfterEffectReadback") is True, "post-effect-closure")
    ceiling = closure.get("claimCeiling", {})
    need(ceiling == {"allRepositoriesEnforced": False, "businessOutcomeAchieved": False, "corporateSaleOutcomeAchieved": False}, "claim-ceiling")

    references = legacy_reference_paths()
    unexpected = sorted(set(references) - ALLOWED_LEGACY_REFERENCES)
    need(not unexpected, f"active-legacy-reference:{unexpected}")
    return {
        "kind": "contractModelingProductionMigrationCandidate.v1",
        "status": "pass",
        "candidateSha": candidate_sha,
        "acceptedDecisionMerge": DECISION_MERGE,
        "acceptedDecisionDigest": DECISION_DIGEST,
        "compilerShadowMerge": SHADOW_MERGE,
        "legacyResponsibilityDigest": LEGACY_DIGEST,
        "legacyResponsibilityCount": 36,
        "legacyMapped": 36,
        "legacyUnexplained": 0,
        "legacyActiveConsumerCount": 0,
        "legacyReferences": references,
        "antiReintroduction": True,
        "productionGate": FINAL_GATE,
        "productionCutoverEligible": True,
        "effectReadbackRequired": True,
        "migrationComplete": False,
        "migrationCompleteAfterEffectReadback": True,
        "authority": False,
        "effect": False,
        "allRepositoriesEnforced": False,
        "businessOutcomeAchieved": False,
        "corporateSaleOutcomeAchieved": False,
    }


def selftest() -> dict[str, Any]:
    policy = read_json(POLICY)
    inventory = read_json(INVENTORY)
    closure = read_json(CLOSURE)
    validate(policy, inventory, closure, "a" * 40)
    cases: list[str] = []

    def reject(name: str, mutate: Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], None]) -> None:
        p, i, c = copy.deepcopy(policy), copy.deepcopy(inventory), copy.deepcopy(closure)
        mutate(p, i, c)
        try:
            validate(p, i, c, "a" * 40)
        except MigrationError:
            cases.append(name)
        else:
            raise MigrationError(f"selftest-false-green:{name}")

    reject("stale-decision", lambda p, i, c: p["decision"].__setitem__("decision_digest", "0" * 64))
    reject("shadow-mode", lambda p, i, c: p.__setitem__("mode", "shadow"))
    reject("unfrozen-inventory", lambda p, i, c: p["legacy"].__setitem__("final_frozen_inventory", False))
    reject("unmapped-responsibility", lambda p, i, c: i["responsibilities"][0].__setitem__("disposition", "quarantined"))
    reject("missing-responsibility", lambda p, i, c: i["responsibilities"].pop())
    reject("consumer-remains", lambda p, i, c: p["cutover"].__setitem__("legacy_active_consumer_count", 1))
    reject("consumer-zero-unproven", lambda p, i, c: p["cutover"].__setitem__("external_consumer_zero_proven", False))
    reject("raw-direct-approved", lambda p, i, c: c["proof"].__setitem__("approvedRawDirectQueryCount", 1))
    reject("effect-readback-optional", lambda p, i, c: c["cutover"].__setitem__("effectReadbackRequired", False))
    reject("business-overclaim", lambda p, i, c: c["claimCeiling"].__setitem__("businessOutcomeAchieved", True))
    return {"kind": "contractModelingProductionMigrationSelftest.v1", "status": "pass", "destructiveCases": cases, "destructiveCaseCount": len(cases)}


def write_candidate(candidate_sha: str, out: Path) -> dict[str, Any]:
    report = validate(read_json(POLICY), read_json(INVENTORY), read_json(CLOSURE), candidate_sha)
    out.mkdir(parents=True, exist_ok=True)
    (out / "production-migration-candidate.json").write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    receipt = {
        "kind": "contractModelingProductionCutoverReceipt.v1",
        "status": "candidate-pass",
        "candidateSha": candidate_sha,
        "acceptedDecisionMerge": DECISION_MERGE,
        "acceptedDecisionDigest": DECISION_DIGEST,
        "legacyResponsibilityDigest": LEGACY_DIGEST,
        "legacyActiveConsumerCount": 0,
        "productionGate": FINAL_GATE,
        "effectReadbackRequired": True,
        "migrationComplete": False,
        "authority": False,
        "effect": False,
        "businessOutcomeAchieved": False,
    }
    (out / "production-cutover-receipt.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (out / "production-cutover-pass").write_text("PASS\n", encoding="utf-8")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("--candidate-sha", required=True)
    check.add_argument("--out", type=Path, required=True)
    sub.add_parser("selftest")
    args = parser.parse_args()
    try:
        result = write_candidate(args.candidate_sha, args.out) if args.command == "check" else selftest()
    except (MigrationError, OSError, KeyError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(canonical(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
