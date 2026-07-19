#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.gov_release.identity import IDENTITY_PATH, load_identity  # noqa: E402

DECISION = ROOT / "governance/accepted-final-ci-decision.v1.json"
ROLLOUT = ROOT / "governance/selected-final-ci-rollout.v1.json"
RELEASE_BASELINE = ROOT / "governance/gov-release-baseline.v1.json"
CI_INTENT = ROOT / "ci.intent.v1.jsonl"
WORKFLOWS = ROOT / ".github/workflows"
GATE = ".github/workflows/gov-final-scope-purpose-join.yml"
CANARY = ".github/workflows/gov-canary.yml"
RELEASE = ".github/workflows/gov-release.yml"
SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
SOURCE_CLOSURE = re.compile(r"^sha256:[0-9a-f]{40}$")
EXPECTED_REPOS = {
    "roccho-dev/ui": "positive-feature-consumer",
    "roccho-dev/ops": "migration-consumer-known-mismatch",
}
STALE_EVIDENCE_FIELDS = {"candidateHead", "mergeCommit", "receiptRunId", "receiptArtifactDigest", "receiptStatus"}


class GateError(ValueError):
    pass


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def need(ok: bool, code: str) -> None:
    if not ok:
        raise GateError(code)


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    need(isinstance(value, dict), f"not-object:{path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        need(isinstance(value, dict), f"not-object:{path}:{line_number}")
        rows.append(value)
    return rows


def load_compiler() -> Any:
    path = ROOT / "tools/compile-claim-port-joins.py"
    spec = importlib.util.spec_from_file_location("claim_port_join", path)
    need(spec is not None and spec.loader is not None, "compiler-load")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_current_decision(value: dict[str, Any], identity: dict[str, Any]) -> None:
    need(value.get("kind") == "governance.acceptedFinalCiDecisionProjection.v1", "decision-kind")
    need(value.get("issue") == "roccho-dev/adrs#233", "decision-source")
    need(value.get("acceptedMerge") == identity["currentTopology"]["acceptedMerge"], "decision-merge")
    need(value.get("stableRequiredCheck") == identity["currentTopology"]["stableCheckName"], "check-name")
    need(value.get("allRepositoriesEnforced") is False, "decision-overclaim")


def validate_release_candidate(value: dict[str, Any], identity: dict[str, Any]) -> None:
    need(value.get("kind") == "governance.govReleaseBaseline.v1", "release-baseline-kind")
    need(value.get("status") == "candidate", "release-baseline-status")
    need(value.get("closureModel") == "gov-release-publication", "release-closure-model")
    need(value.get("supersedesClosureModels") == ["github-merge-protection", "signed-promotion"], "release-supersedes")
    need(value.get("identityProjection") == IDENTITY_PATH.relative_to(ROOT).as_posix(), "release-identity-projection")
    need(identity["source"]["status"] in {"accepted-in-candidate", "accepted"}, "release-decision-status")
    need(value["governance"]["workflowCount"] == 3, "release-workflow-count")
    need(value["currentOperationalAdoption"]["releasePublished"] is False, "release-not-published")
    need(value["currentOperationalAdoption"]["releaseReadback"] is False, "release-not-read-back")
    invariants = value["invariants"]
    for key in ["githubMergeHasAuthority", "githubRulesetRequired", "unreleasedCommitHasEffect", "signatureRequired", "allRepositoriesEnforced", "businessOutcomeAchieved"]:
        need(invariants.get(key) is False, "release-invariant:" + key)


def validate_rollout(value: dict[str, Any], identity: dict[str, Any]) -> dict[str, dict[str, Any]]:
    need(value.get("kind") == "governance.selectedFinalCiRollout.v2", "rollout-kind")
    need(value.get("decisionMerge") == identity["currentTopology"]["acceptedMerge"], "rollout-decision")
    need(value.get("allRepositoriesEnforced") is False, "rollout-overclaim")
    rows = value.get("repositories")
    need(isinstance(rows, list) and len(rows) == 2, "rollout-cardinality")
    by_repository = {row.get("repository"): row for row in rows if isinstance(row, dict)}
    need(set(by_repository) == set(EXPECTED_REPOS), "rollout-repositories")
    bundle_values = set()
    closure_values = set()
    for repository, role in EXPECTED_REPOS.items():
        row = by_repository[repository]
        need(not (STALE_EVIDENCE_FIELDS & set(row)), f"checked-in-live-evidence:{repository}")
        need(row.get("role") == role, f"rollout-role:{repository}")
        need(row.get("branch") == "proposals", f"rollout-branch:{repository}")
        need(row.get("claimPath") == "governance/final-ci-claim.v1.json", f"rollout-claim-path:{repository}")
        need(row.get("workflowName") == "final CI consumer", f"rollout-workflow-name:{repository}")
        need(row.get("workflowPath") == ".github/workflows/final-ci-consumer.yml", f"rollout-workflow-path:{repository}")
        need(row.get("artifactName") == "final-ci-consumer-receipt", f"rollout-artifact-name:{repository}")
        need(row.get("receiptPath") == "final-ci-consumer-receipt.json", f"rollout-receipt-path:{repository}")
        need(DIGEST.fullmatch(str(row.get("acceptedBundleDigest", ""))) is not None, f"bundle:{repository}")
        need(SOURCE_CLOSURE.fullmatch(str(row.get("sourceClosureDigest", ""))) is not None, f"closure:{repository}")
        need(row.get("lifecycle") == "active", f"lifecycle:{repository}")
        need(row.get("authority") is False, f"rollout-authority:{repository}")
        bundle_values.add(row["acceptedBundleDigest"])
        closure_values.add(row["sourceClosureDigest"])
    need(len(bundle_values) == 1, "rollout-bundle-drift")
    need(len(closure_values) == 1, "rollout-closure-drift")
    return by_repository


def validate_live_packet(packet: dict[str, Any], expected: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    need(packet.get("kind") == "governance.liveSelectedConsumerPacket.v1", "live-kind")
    need(packet.get("status") == "pass", "live-status")
    need(packet.get("allRepositoriesEnforced") is False, "live-overclaim")
    need(packet.get("artifactBodiesVerified") is True, "live-artifact-bodies")
    need(packet.get("receiptCandidateShaBound") is True, "live-receipt-bound")
    rows = packet.get("repositories")
    need(isinstance(rows, list) and len(rows) == 2, "live-cardinality")
    by_repository = {row.get("repository"): row for row in rows if isinstance(row, dict)}
    need(set(by_repository) == set(expected), "live-repositories")
    for repository, contract in expected.items():
        row = by_repository[repository]
        head = row.get("currentHead")
        need(isinstance(head, str) and SHA.fullmatch(head) is not None, f"live-head:{repository}")
        need(row.get("branch") == contract["branch"], f"live-branch:{repository}")
        need(row.get("claimPath") == contract["claimPath"], f"live-claim-path:{repository}")
        need(DIGEST.fullmatch(str(row.get("claimDigest", ""))) is not None, f"live-claim-digest:{repository}")
        need(row.get("runHeadSha") == head, f"live-run-head:{repository}")
        need(row.get("runEvent") == "push", f"live-run-event:{repository}")
        need(row.get("runConclusion") == "success", f"live-run-conclusion:{repository}")
        need(row.get("workflowName") == contract["workflowName"] or row.get("workflowPath") == contract["workflowPath"], f"live-workflow:{repository}")
        need(isinstance(row.get("runId"), int) and row["runId"] > 0, f"live-run-id:{repository}")
        need(isinstance(row.get("artifactId"), int) and row["artifactId"] > 0, f"live-artifact-id:{repository}")
        need(row.get("artifactName") == contract["artifactName"], f"live-artifact-name:{repository}")
        need(DIGEST.fullmatch(str(row.get("artifactDigest", ""))) is not None, f"live-artifact-digest:{repository}")
        need(row.get("receiptPath") == contract["receiptPath"], f"live-receipt-path:{repository}")
        need(DIGEST.fullmatch(str(row.get("receiptDigest", ""))) is not None, f"live-receipt-digest:{repository}")
        receipt = row.get("receipt")
        need(isinstance(receipt, dict), f"live-receipt:{repository}")
        need(receipt.get("kind") == "governance.selectedConsumerReceipt.v1", f"receipt-kind:{repository}")
        need(receipt.get("status") == "pass", f"receipt-status:{repository}")
        need(receipt.get("repository") == repository, f"receipt-repository:{repository}")
        need(receipt.get("role") == contract["role"], f"receipt-role:{repository}")
        need(receipt.get("candidateSha") == head, f"receipt-candidate-sha:{repository}")
        need(receipt.get("assertionId") == contract["assertionId"], f"receipt-assertion:{repository}")
        need(receipt.get("acceptedBundleDigest") == contract["acceptedBundleDigest"], f"receipt-bundle:{repository}")
        need(receipt.get("sourceClosureDigest") == contract["sourceClosureDigest"], f"receipt-closure:{repository}")
        need(receipt.get("authority") is False, f"receipt-authority:{repository}")
        need(receipt.get("allRepositoriesEnforced") is False, f"receipt-overclaim:{repository}")
        if contract.get("knownMismatchRejected") is True:
            need(receipt.get("knownMismatchRejected") is True, f"receipt-known-mismatch:{repository}")
    return by_repository


def validate_provider_files(identity: dict[str, Any]) -> None:
    expected = {GATE, CANARY, RELEASE}
    actual = {path.relative_to(ROOT).as_posix() for path in WORKFLOWS.iterdir() if path.is_file() and path.suffix in {".yml", ".yaml"}}
    need(actual == expected, "workflow-universe")
    rows = read_jsonl(CI_INTENT)
    need(len(rows) == 3, "ci-intent-cardinality")
    by_path = {row.get("path"): row for row in rows}
    need(set(by_path) == expected, "ci-intent-universe")
    need(by_path[GATE].get("required_check_name") == identity["currentTopology"]["stableCheckName"], "intent-check-name")
    need(by_path[GATE].get("authority_class") == "release-eligibility-evidence", "intent-gate-authority")
    need(by_path[GATE].get("identity_projection") == IDENTITY_PATH.relative_to(ROOT).as_posix(), "intent-identity-projection")
    need(by_path[CANARY].get("authority_class") == "evidence-only", "intent-canary-authority")
    need(by_path[RELEASE].get("authority_class") == "release-adoption", "intent-release-authority")
    gate_text = (ROOT / GATE).read_text(encoding="utf-8")
    canary_text = (ROOT / CANARY).read_text(encoding="utf-8")
    release_text = (ROOT / RELEASE).read_text(encoding="utf-8")
    need("check-live-final-ci-consumers.py capture" in gate_text, "gate-live-capture")
    need("--live-consumers" in gate_text, "gate-live-packet")
    need("check-live-final-ci-consumers.py capture" in canary_text, "canary-live-consumers")
    need("check-live-final-ci-control-plane.py check" in canary_text, "canary-control-plane")
    need("workflow_dispatch" in release_text, "release-dispatch")
    need("gh release create" in release_text, "release-publish")
    need("gov-release-manifest.json" in release_text, "release-manifest")
    need("gov-release-identity.v1.json" in gate_text + canary_text + release_text, "identity-projection-workflow")
    need("contents: write" in release_text, "release-write-boundary")
    need("pull_request_target" not in gate_text + canary_text + release_text, "pull-request-target")
    need("persist-credentials: false" in gate_text, "gate-credentials")


def compile_selected_admissions(live: dict[str, dict[str, Any]], candidate_sha: str, expected: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    compiler = load_compiler()
    reference = next(iter(expected.values()))
    bundle = reference["acceptedBundleDigest"]
    closure = reference["sourceClosureDigest"]
    subjects = ["repo:roccho-dev/governance", "repo:roccho-dev/ui", "repo:roccho-dev/ops"]
    grants = [{"subjectId": subject, "grantId": f"grant:{subject}", "acceptedBundleDigest": bundle, "sourceClosureDigest": closure, "lifecycle": "active"} for subject in subjects]
    assertions = [{"subjectId": subjects[0], "assertionId": "governance.final-ci-self.v1", "acceptedBundleDigest": bundle, "sourceClosureDigest": closure, "candidateSha": candidate_sha, "lifecycle": "active"}]
    receipts = [{"subjectId": subjects[0], "receiptId": f"governance:{candidate_sha}", "acceptedBundleDigest": bundle, "sourceClosureDigest": closure, "candidateSha": candidate_sha}]
    for repository in ("roccho-dev/ui", "roccho-dev/ops"):
        live_row = live[repository]
        receipt = live_row["receipt"]
        subject = f"repo:{repository}"
        assertions.append({"subjectId": subject, "assertionId": receipt["assertionId"], "acceptedBundleDigest": receipt["acceptedBundleDigest"], "sourceClosureDigest": receipt["sourceClosureDigest"], "candidateSha": live_row["currentHead"], "lifecycle": "active"})
        receipts.append({"subjectId": subject, "receiptId": f"run:{live_row['runId']}:artifact:{live_row['artifactId']}", "acceptedBundleDigest": receipt["acceptedBundleDigest"], "sourceClosureDigest": receipt["sourceClosureDigest"], "candidateSha": receipt["candidateSha"]})
    rows = compiler.compile_admissions(grants, assertions, receipts)
    need(len(rows) == 3, "organization-admission-cardinality")
    need(all(row.get("admissionResult") == "organization-active" for row in rows), "organization-admission")
    need(all(row.get("candidateShaMatches") is True for row in rows), "organization-candidate-sha")
    return rows


def check(candidate_sha: str, live_path: Path, decision_path: Path = DECISION, rollout_path: Path = ROLLOUT, release_baseline_path: Path = RELEASE_BASELINE) -> dict[str, Any]:
    need(SHA.fullmatch(candidate_sha) is not None, "candidate-sha")
    need(live_path.is_file(), "live-packet-missing")
    identity = load_identity()
    decision = read_json(decision_path)
    rollout = read_json(rollout_path)
    release_baseline = read_json(release_baseline_path)
    packet = read_json(live_path)
    validate_current_decision(decision, identity)
    validate_release_candidate(release_baseline, identity)
    expected = validate_rollout(rollout, identity)
    live = validate_live_packet(packet, expected)
    validate_provider_files(identity)
    admissions = compile_selected_admissions(live, candidate_sha, expected)
    return {
        "kind": "governance.finalCiProductionEvidence.v5",
        "status": "pass",
        "decision": "allow",
        "candidateSha": candidate_sha,
        "identityProjection": IDENTITY_PATH.relative_to(ROOT).as_posix(),
        "currentlyAcceptedDecisionMerge": identity["currentTopology"]["acceptedMerge"],
        "govReleaseDecisionCandidateHead": identity["source"]["head"],
        "govReleaseContractDigest": identity["contract"]["canonicalDigest"],
        "govReleaseAcceptedDecisionDigest": identity["acceptedDecision"]["canonicalDigest"],
        "finalCheckName": identity["currentTopology"]["stableCheckName"],
        "workflowCount": 3,
        "selectedRepositoryCount": 3,
        "liveConsumerReadback": True,
        "artifactBodiesVerified": True,
        "receiptCandidateShaBound": True,
        "admissions": admissions,
        "candidateEvidencePass": True,
        "releaseEligible": True,
        "releasePublished": False,
        "operationalAdoptionEffect": False,
        "mergeAdmissionAuthority": False,
        "meaningAuthority": False,
        "effectAuthority": False,
        "signatureRequired": False,
        "githubRulesetRequired": False,
        "unreleasedCommitHasEffect": False,
        "allRepositoriesEnforced": False,
        "authority": False,
    }


def fake_packet(rollout: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for index, contract in enumerate(rollout["repositories"], 1):
        head = str(index) * 40
        receipt = {"kind": "governance.selectedConsumerReceipt.v1", "status": "pass", "repository": contract["repository"], "role": contract["role"], "candidateSha": head, "assertionId": contract["assertionId"], "acceptedBundleDigest": contract["acceptedBundleDigest"], "sourceClosureDigest": contract["sourceClosureDigest"], "authority": False, "allRepositoriesEnforced": False}
        if contract.get("knownMismatchRejected"):
            receipt["knownMismatchRejected"] = True
        rows.append({"repository": contract["repository"], "branch": contract["branch"], "currentHead": head, "claimPath": contract["claimPath"], "claimDigest": "sha256:" + str(index) * 64, "runId": index, "runHeadSha": head, "runEvent": "push", "runConclusion": "success", "workflowName": contract["workflowName"], "workflowPath": contract["workflowPath"], "artifactId": 100 + index, "artifactName": contract["artifactName"], "artifactDigest": "sha256:" + str(index + 2) * 64, "receiptPath": contract["receiptPath"], "receiptDigest": "sha256:" + str(index + 4) * 64, "receipt": receipt})
    return {"kind": "governance.liveSelectedConsumerPacket.v1", "status": "pass", "repositoryCount": 2, "artifactBodiesVerified": True, "receiptCandidateShaBound": True, "allRepositoriesEnforced": False, "repositories": rows}


def selftest() -> dict[str, Any]:
    rollout = read_json(ROLLOUT)
    packet = fake_packet(rollout)
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        live_path = root / "live.json"
        live_path.write_text(canonical(packet), encoding="utf-8")
        check("a" * 40, live_path)
        cases: list[tuple[str, Callable[[dict[str, Any], dict[str, Any]], None], str]] = [
            ("receipt-sha", lambda rollout_value, packet_value: packet_value["repositories"][0]["receipt"].update(candidateSha="f" * 40), "receipt-candidate-sha"),
            ("run-head", lambda rollout_value, packet_value: packet_value["repositories"][0].update(runHeadSha="e" * 40), "live-run-head"),
            ("claim-digest", lambda rollout_value, packet_value: packet_value["repositories"][0].update(claimDigest="bad"), "live-claim-digest"),
            ("failed-run", lambda rollout_value, packet_value: packet_value["repositories"][0].update(runConclusion="failure"), "live-run-conclusion"),
            ("missing-live-repo", lambda rollout_value, packet_value: packet_value["repositories"].pop(), "live-cardinality"),
            ("checked-in-evidence", lambda rollout_value, packet_value: rollout_value["repositories"][0].update(candidateHead="b" * 40), "checked-in-live-evidence"),
        ]
        rejected = []
        for name, mutate, expected_code in cases:
            rollout_value = copy.deepcopy(rollout)
            packet_value = copy.deepcopy(packet)
            mutate(rollout_value, packet_value)
            rollout_path = root / f"{name}-rollout.json"
            packet_path = root / f"{name}-live.json"
            rollout_path.write_text(canonical(rollout_value), encoding="utf-8")
            packet_path.write_text(canonical(packet_value), encoding="utf-8")
            try:
                check("a" * 40, packet_path, rollout_path=rollout_path)
            except GateError as error:
                need(expected_code in str(error), f"wrong-finding:{name}:{error}")
                rejected.append({"case": name, "status": "rejected", "finding": str(error)})
            else:
                raise GateError(f"destructive case passed:{name}")
    return {"kind": "governance.finalCiProductionEvidence.selftest.v5", "status": "pass", "positiveCases": 1, "destructiveCases": len(rejected), "cases": rejected, "identityProjection": IDENTITY_PATH.relative_to(ROOT).as_posix(), "signatureRequired": False, "operationalAdoptionEffect": False, "allRepositoriesEnforced": False, "authority": False}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["check", "selftest"])
    parser.add_argument("--candidate-sha", default="a" * 40)
    parser.add_argument("--live-consumers", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.command == "check":
        if args.live_consumers is None:
            parser.error("check requires --live-consumers")
        report = check(args.candidate_sha, args.live_consumers)
    else:
        report = selftest()
    print(canonical(report) if args.json else f"final-ci-production:{report['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
