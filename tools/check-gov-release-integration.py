#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.gov_release.core import ReleaseError, digest, make_eligibility  # noqa: E402

BASELINE = ROOT / "governance/gov-release-baseline.v1.json"
CONTRACT_DIGEST = "sha256:5016d40e3bc7628436ac1b5736f180c36e114047772544bd6b64e53d6eeefb7b"
DECISION_DIGEST = "sha256:51a0fb65a990981c392ff1f7d5c9f9fdb61f09c3caa81eef656ebbd3d7e22c9f"
ADRS_HEAD = "5a8a6d9968178144b2e547f28bb9977a7b65c755"


def need(ok: bool, code: str) -> None:
    if not ok:
        raise ReleaseError(code)


def read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    need(isinstance(value, dict), f"not-object:{path}")
    return value


def validate_baseline(value: dict[str, Any]) -> None:
    need(value.get("kind") == "governance.govReleaseBaseline.v1", "baseline-kind")
    need(value.get("closureModel") == "gov-release-publication", "baseline-closure-model")
    need(value.get("supersedesClosureModels") == ["github-merge-protection", "signed-promotion"], "baseline-supersedes")
    need(value.get("historicalClosureReceipts") == {"adrs223": "superseded", "adrs233": "superseded", "governance150": "superseded"}, "baseline-old-closure")
    candidate = value["adrsCandidate"]
    need(candidate["head"] == ADRS_HEAD, "baseline-adrs-head")
    need(candidate["contractDigest"] == CONTRACT_DIGEST, "baseline-contract-digest")
    need(candidate["acceptedDecisionDigest"] == DECISION_DIGEST, "baseline-decision-digest")
    need(value["governance"]["workflowCount"] == 3, "baseline-workflow-count")
    need(value["currentOperationalAdoption"]["releasePublished"] is False, "baseline-release-published")
    need(value["currentOperationalAdoption"]["releaseReadback"] is False, "baseline-release-readback")
    invariants = value["invariants"]
    for key in ["githubMergeHasAuthority", "githubRulesetRequired", "unreleasedCommitHasEffect", "signatureRequired", "allRepositoriesEnforced", "businessOutcomeAchieved"]:
        need(invariants.get(key) is False, "baseline:" + key)


def live_digests(value: dict[str, Any]) -> tuple[str, str]:
    need(value.get("kind") == "governance.liveSelectedConsumerPacket.v1", "live-kind")
    need(value.get("status") == "pass", "live-status")
    need(value.get("artifactBodiesVerified") is True, "live-artifact-bodies")
    need(value.get("receiptCandidateShaBound") is True, "live-receipt-sha")
    rows = value.get("repositories")
    need(isinstance(rows, list) and len(rows) == 2, "live-repository-count")
    need(len({row.get("repository") for row in rows if isinstance(row, dict)}) == 2, "live-duplicate-repository")
    claims = []
    receipts = []
    for row in sorted(rows, key=lambda item: item["repository"]):
        receipt = row.get("receipt", {})
        need(row.get("runConclusion") == "success" and row.get("runEvent") == "push", "live-run")
        need(row.get("currentHead") == row.get("runHeadSha") == receipt.get("candidateSha"), "live-candidate-binding")
        need(receipt.get("status") == "pass" and receipt.get("authority") is False, "live-receipt")
        claims.append({"repository": row["repository"], "currentHead": row["currentHead"], "claimDigest": row["claimDigest"]})
        receipts.append({"repository": row["repository"], "candidateSha": receipt["candidateSha"], "receiptDigest": row["receiptDigest"], "artifactDigest": row["artifactDigest"]})
    return digest(claims), digest(receipts)


def eligibility(gate: dict[str, Any], live: dict[str, Any], candidate_sha: str) -> dict[str, Any]:
    baseline = read(BASELINE)
    validate_baseline(baseline)
    claim_set_digest, receipt_set_digest = live_digests(live)
    value = make_eligibility(
        candidate_sha=candidate_sha,
        accepted_decision_digest=DECISION_DIGEST,
        gate_report=gate,
        claim_set_digest=claim_set_digest,
        receipt_set_digest=receipt_set_digest,
    )
    value.update(
        {
            "adrsPullRequest": 242,
            "adrsHead": baseline["adrsCandidate"]["head"],
            "decisionStatus": baseline["adrsCandidate"]["status"],
            "govReleaseContractDigest": CONTRACT_DIGEST,
            "releaseWorkflow": "gov-release",
            "signatureRequired": False,
            "githubRulesetRequired": False,
            "unreleasedCommitHasEffect": False,
            "allRepositoriesEnforced": False,
            "businessOutcomeAchieved": False,
        }
    )
    value["eligibilityDigest"] = digest({key: item for key, item in value.items() if key != "eligibilityDigest"})
    return value


def rejected(name: str, fn: Callable[[], Any]) -> dict[str, str]:
    try:
        fn()
    except (ReleaseError, KeyError, TypeError, ValueError):
        return {"case": name, "status": "rejected"}
    raise ReleaseError("destructive-case-passed:" + name)


def fixture() -> tuple[dict[str, Any], dict[str, Any]]:
    candidate_sha = "a" * 40
    gate = {"kind": "governance.finalScopePurposeJoin.gate.v6", "status": "pass", "decision": "allow", "candidateSha": candidate_sha}
    rows = []
    for repository, digit in [("roccho-dev/ops", "1"), ("roccho-dev/ui", "2")]:
        rows.append(
            {
                "repository": repository,
                "currentHead": digit * 40,
                "runHeadSha": digit * 40,
                "runConclusion": "success",
                "runEvent": "push",
                "claimDigest": "sha256:" + digit * 64,
                "receiptDigest": "sha256:" + ("3" if digit == "1" else "4") * 64,
                "artifactDigest": "sha256:" + ("5" if digit == "1" else "6") * 64,
                "receipt": {"candidateSha": digit * 40, "status": "pass", "authority": False},
            }
        )
    live = {"kind": "governance.liveSelectedConsumerPacket.v1", "status": "pass", "artifactBodiesVerified": True, "receiptCandidateShaBound": True, "repositories": rows}
    return gate, live


def selftest() -> dict[str, Any]:
    gate, live = fixture()
    value = eligibility(gate, live, "a" * 40)
    cases = []
    bad = copy.deepcopy(gate); bad["candidateSha"] = "b" * 40
    cases.append(rejected("gate-other-candidate", lambda: eligibility(bad, live, "a" * 40)))
    bad = copy.deepcopy(live); bad["artifactBodiesVerified"] = False
    cases.append(rejected("artifact-body-unverified", lambda: eligibility(gate, bad, "a" * 40)))
    bad = copy.deepcopy(live); bad["repositories"][0]["receipt"]["candidateSha"] = "9" * 40
    cases.append(rejected("receipt-other-candidate", lambda: eligibility(gate, bad, "a" * 40)))
    bad = read(BASELINE); bad["historicalClosureReceipts"]["governance150"] = "completed"
    cases.append(rejected("old-closure-active", lambda: validate_baseline(bad)))
    workflows = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / ".github/workflows").glob("*.yml"))
    need("promotion-keygen" not in workflows, "keygen-workflow")
    need("--private-key-file" not in workflows, "private-key-workflow")
    need("cryptography" not in workflows, "signature-dependency")
    need("gov-release-manifest.json" in workflows, "release-manifest-workflow")
    need("gh release create" in workflows, "release-publish-workflow")
    need("accepted-decision.json" in workflows, "accepted-decision-workflow")
    return {
        "kind": "governance.govReleaseIntegration.selftest.v2",
        "status": "pass",
        "positiveCases": 1,
        "destructiveCases": len(cases),
        "cases": cases,
        "eligibility": value,
        "releasePublished": False,
        "operationalAdoptionEffect": False,
        "signatureRequired": False,
        "githubRulesetRequired": False,
        "allRepositoriesEnforced": False,
        "businessOutcomeAchieved": False,
        "authority": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["eligibility", "selftest", "canary"])
    parser.add_argument("--gate", type=Path)
    parser.add_argument("--live-consumers", type=Path)
    parser.add_argument("--candidate-sha")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.command == "eligibility":
        if args.gate is None or args.live_consumers is None or not args.candidate_sha:
            parser.error("eligibility requires --gate --live-consumers --candidate-sha")
        report = eligibility(read(args.gate), read(args.live_consumers), args.candidate_sha)
    elif args.command == "selftest":
        report = selftest()
    else:
        baseline = read(BASELINE)
        validate_baseline(baseline)
        report = {
            "kind": "governance.govReleaseCanary.v2",
            "status": "candidate-pass",
            "contractDigest": CONTRACT_DIGEST,
            "acceptedDecisionDigest": DECISION_DIGEST,
            "releasePublished": baseline["currentOperationalAdoption"]["releasePublished"],
            "releaseReadback": baseline["currentOperationalAdoption"]["releaseReadback"],
            "rulesetSeverity": "information",
            "rulesetAffectsReleaseClosure": False,
            "signatureRequired": False,
            "operationalAdoptionEffect": False,
            "allRepositoriesEnforced": False,
            "businessOutcomeAchieved": False,
            "authority": False,
        }
    text = json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
