#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import re
import tempfile
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
DECISION = ROOT / "governance/accepted-final-ci-decision.v1.json"
ROLLOUT = ROOT / "governance/selected-final-ci-rollout.v1.json"
CI_INTENT = ROOT / "ci.intent.v1.jsonl"
WORKFLOWS = ROOT / ".github/workflows"
GATE = ".github/workflows/gov-final-scope-purpose-join.yml"
CANARY = ".github/workflows/gov-canary.yml"
CHECK_NAME = "gov-final-scope-purpose-join / gate"
SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
EXPECTED_REPOS = {
    "roccho-dev/ui": "positive-feature-consumer",
    "roccho-dev/ops": "migration-consumer-known-mismatch",
}
STALE_EVIDENCE_FIELDS = {
    "candidateHead",
    "mergeCommit",
    "receiptRunId",
    "receiptArtifactDigest",
    "receiptStatus",
}


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
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        need(isinstance(value, dict), f"not-object:{path}:{line_no}")
        rows.append(value)
    return rows


def load_compiler() -> Any:
    path = ROOT / "tools/compile-claim-port-joins.py"
    spec = importlib.util.spec_from_file_location("claim_port_join", path)
    need(spec is not None and spec.loader is not None, "compiler-load")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_decision(value: dict[str, Any]) -> None:
    need(value.get("kind") == "governance.acceptedFinalCiDecisionProjection.v1", "decision-kind")
    need(value.get("issue") == "roccho-dev/adrs#233", "decision-source")
    need(value.get("decisionId") == "01K0D7C3A00000000000000233", "decision-id")
    need(value.get("releaseId") == "final-organization-ci-topology-v1.0.0", "decision-release")
    need(value.get("acceptedMerge") == "a8fc9e8e04d53f1d783317059e4421c8dc724d01", "decision-merge")
    need(
        value.get("contractCanonicalDigest")
        == "8106d85404e636a9797dfb8e0a1f6343db8a7867ff904577f682e5d82ad9b314",
        "decision-digest",
    )
    need(
        value.get("authorityClasses")
        == ["accepted-meaning", "merge-admission", "effect", "evidence-only"],
        "authority-classes",
    )
    need(value.get("targetWorkflows") == ["gov-gate", "gov-canary"], "target-workflows")
    need(value.get("stableRequiredCheck") == CHECK_NAME, "check-name")
    need(value.get("allRepositoriesEnforced") is False, "decision-overclaim")


def validate_rollout(value: dict[str, Any]) -> dict[str, dict[str, Any]]:
    need(value.get("kind") == "governance.selectedFinalCiRollout.v2", "rollout-kind")
    need(value.get("decisionMerge") == "a8fc9e8e04d53f1d783317059e4421c8dc724d01", "rollout-decision")
    need(value.get("allRepositoriesEnforced") is False, "rollout-overclaim")
    rows = value.get("repositories")
    need(isinstance(rows, list) and len(rows) == 2, "rollout-cardinality")
    by_repo = {row.get("repository"): row for row in rows if isinstance(row, dict)}
    need(set(by_repo) == set(EXPECTED_REPOS), "rollout-repositories")
    for repo, role in EXPECTED_REPOS.items():
        row = by_repo[repo]
        need(not (STALE_EVIDENCE_FIELDS & set(row)), f"checked-in-live-evidence:{repo}")
        need(row.get("role") == role, f"rollout-role:{repo}")
        need(row.get("branch") == "proposals", f"rollout-branch:{repo}")
        need(row.get("claimPath") == "governance/final-ci-claim.v1.json", f"rollout-claim-path:{repo}")
        need(row.get("workflowName") == "final CI consumer", f"rollout-workflow-name:{repo}")
        need(row.get("workflowPath") == ".github/workflows/final-ci-consumer.yml", f"rollout-workflow-path:{repo}")
        need(row.get("artifactName") == "final-ci-consumer-receipt", f"rollout-artifact-name:{repo}")
        need(row.get("receiptPath") == "final-ci-consumer-receipt.json", f"rollout-receipt-path:{repo}")
        need(
            row.get("acceptedBundleDigest")
            == "sha256:8106d85404e636a9797dfb8e0a1f6343db8a7867ff904577f682e5d82ad9b314",
            f"bundle:{repo}",
        )
        need(
            row.get("sourceClosureDigest")
            == "sha256:a8fc9e8e04d53f1d783317059e4421c8dc724d01",
            f"closure:{repo}",
        )
        need(row.get("lifecycle") == "active", f"lifecycle:{repo}")
        need(row.get("authority") is False, f"rollout-authority:{repo}")
    return by_repo


def validate_live_packet(
    packet: dict[str, Any], expected: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    need(packet.get("kind") == "governance.liveSelectedConsumerPacket.v1", "live-kind")
    need(packet.get("status") == "pass", "live-status")
    need(packet.get("allRepositoriesEnforced") is False, "live-overclaim")
    rows = packet.get("repositories")
    need(isinstance(rows, list) and len(rows) == 2, "live-cardinality")
    by_repo = {row.get("repository"): row for row in rows if isinstance(row, dict)}
    need(set(by_repo) == set(expected), "live-repositories")
    for repo, contract in expected.items():
        row = by_repo[repo]
        head = row.get("currentHead")
        need(isinstance(head, str) and SHA.fullmatch(head) is not None, f"live-head:{repo}")
        need(row.get("branch") == contract["branch"], f"live-branch:{repo}")
        need(row.get("claimPath") == contract["claimPath"], f"live-claim-path:{repo}")
        need(DIGEST.fullmatch(str(row.get("claimDigest", ""))) is not None, f"live-claim-digest:{repo}")
        need(row.get("runHeadSha") == head, f"live-run-head:{repo}")
        need(row.get("runEvent") == "push", f"live-run-event:{repo}")
        need(row.get("runConclusion") == "success", f"live-run-conclusion:{repo}")
        need(
            row.get("workflowName") == contract["workflowName"]
            or row.get("workflowPath") == contract["workflowPath"],
            f"live-workflow:{repo}",
        )
        need(isinstance(row.get("runId"), int) and row["runId"] > 0, f"live-run-id:{repo}")
        need(isinstance(row.get("artifactId"), int) and row["artifactId"] > 0, f"live-artifact-id:{repo}")
        need(row.get("artifactName") == contract["artifactName"], f"live-artifact-name:{repo}")
        need(
            DIGEST.fullmatch(str(row.get("artifactDigest", ""))) is not None,
            f"live-artifact-digest:{repo}",
        )
        need(row.get("receiptPath") == contract["receiptPath"], f"live-receipt-path:{repo}")
        need(
            DIGEST.fullmatch(str(row.get("receiptDigest", ""))) is not None,
            f"live-receipt-digest:{repo}",
        )
        receipt = row.get("receipt")
        need(isinstance(receipt, dict), f"live-receipt:{repo}")
        need(receipt.get("kind") == "governance.selectedConsumerReceipt.v1", f"receipt-kind:{repo}")
        need(receipt.get("status") == "pass", f"receipt-status:{repo}")
        need(receipt.get("repository") == repo, f"receipt-repository:{repo}")
        need(receipt.get("role") == contract["role"], f"receipt-role:{repo}")
        need(receipt.get("candidateSha") == head, f"receipt-candidate-sha:{repo}")
        need(receipt.get("assertionId") == contract["assertionId"], f"receipt-assertion:{repo}")
        need(
            receipt.get("acceptedBundleDigest") == contract["acceptedBundleDigest"],
            f"receipt-bundle:{repo}",
        )
        need(
            receipt.get("sourceClosureDigest") == contract["sourceClosureDigest"],
            f"receipt-closure:{repo}",
        )
        need(receipt.get("authority") is False, f"receipt-authority:{repo}")
        need(receipt.get("allRepositoriesEnforced") is False, f"receipt-overclaim:{repo}")
        if contract.get("knownMismatchRejected") is True:
            need(receipt.get("knownMismatchRejected") is True, f"receipt-known-mismatch:{repo}")
    return by_repo


def validate_provider_files() -> None:
    actual = {
        path.relative_to(ROOT).as_posix()
        for path in WORKFLOWS.iterdir()
        if path.is_file() and path.suffix in {".yml", ".yaml"}
    }
    need(actual == {GATE, CANARY}, "workflow-universe")
    rows = read_jsonl(CI_INTENT)
    need(len(rows) == 2, "ci-intent-cardinality")
    by_path = {row.get("path"): row for row in rows}
    need(set(by_path) == {GATE, CANARY}, "ci-intent-universe")
    need(by_path[GATE].get("required_check_name") == CHECK_NAME, "intent-check-name")
    need(by_path[GATE].get("authority_class") == "merge-admission", "intent-gate-authority")
    need(by_path[CANARY].get("authority_class") == "evidence-only", "intent-canary-authority")
    gate_text = (ROOT / GATE).read_text(encoding="utf-8")
    canary_text = (ROOT / CANARY).read_text(encoding="utf-8")
    need("check-live-final-ci-consumers.py capture" in gate_text, "gate-live-capture")
    need("--live-consumers" in gate_text, "gate-live-packet")
    need("check-live-final-ci-consumers.py capture" in canary_text, "canary-live-consumers")
    need("check-live-final-ci-control-plane.py check" in canary_text, "canary-control-plane")
    need("pull_request_target" not in gate_text, "pull-request-target")
    need("persist-credentials: false" in gate_text, "gate-credentials")


def compile_selected_admissions(
    live: dict[str, dict[str, Any]], candidate_sha: str
) -> list[dict[str, Any]]:
    compiler = load_compiler()
    bundle = "sha256:8106d85404e636a9797dfb8e0a1f6343db8a7867ff904577f682e5d82ad9b314"
    closure = "sha256:a8fc9e8e04d53f1d783317059e4421c8dc724d01"
    grants = []
    assertions = []
    receipts = []
    subjects = ["repo:roccho-dev/governance", "repo:roccho-dev/ui", "repo:roccho-dev/ops"]
    for subject in subjects:
        grants.append(
            {
                "subjectId": subject,
                "grantId": f"grant:{subject}",
                "acceptedBundleDigest": bundle,
                "sourceClosureDigest": closure,
                "lifecycle": "active",
            }
        )
    assertions.append(
        {
            "subjectId": subjects[0],
            "assertionId": "governance.final-ci-self.v1",
            "acceptedBundleDigest": bundle,
            "sourceClosureDigest": closure,
            "candidateSha": candidate_sha,
            "lifecycle": "active",
        }
    )
    receipts.append(
        {
            "subjectId": subjects[0],
            "receiptId": f"governance:{candidate_sha}",
            "acceptedBundleDigest": bundle,
            "sourceClosureDigest": closure,
            "candidateSha": candidate_sha,
        }
    )
    for repo in ("roccho-dev/ui", "roccho-dev/ops"):
        live_row = live[repo]
        receipt = live_row["receipt"]
        subject = f"repo:{repo}"
        assertions.append(
            {
                "subjectId": subject,
                "assertionId": receipt["assertionId"],
                "acceptedBundleDigest": receipt["acceptedBundleDigest"],
                "sourceClosureDigest": receipt["sourceClosureDigest"],
                "candidateSha": live_row["currentHead"],
                "lifecycle": "active",
            }
        )
        receipts.append(
            {
                "subjectId": subject,
                "receiptId": f"run:{live_row['runId']}:artifact:{live_row['artifactId']}",
                "acceptedBundleDigest": receipt["acceptedBundleDigest"],
                "sourceClosureDigest": receipt["sourceClosureDigest"],
                "candidateSha": receipt["candidateSha"],
            }
        )
    rows = compiler.compile_admissions(grants, assertions, receipts)
    need(len(rows) == 3, "organization-admission-cardinality")
    need(
        all(row.get("admissionResult") == "organization-active" for row in rows),
        "organization-admission",
    )
    need(all(row.get("candidateShaMatches") is True for row in rows), "organization-candidate-sha")
    return rows


def check(
    candidate_sha: str,
    live_path: Path,
    decision_path: Path = DECISION,
    rollout_path: Path = ROLLOUT,
) -> dict[str, Any]:
    need(SHA.fullmatch(candidate_sha) is not None, "candidate-sha")
    need(live_path.is_file(), "live-packet-missing")
    decision = read_json(decision_path)
    rollout = read_json(rollout_path)
    packet = read_json(live_path)
    validate_decision(decision)
    expected = validate_rollout(rollout)
    live = validate_live_packet(packet, expected)
    validate_provider_files()
    admissions = compile_selected_admissions(live, candidate_sha)
    return {
        "kind": "governance.finalCiProductionGate.v2",
        "status": "pass",
        "decision": "allow",
        "candidateSha": candidate_sha,
        "acceptedDecisionMerge": decision["acceptedMerge"],
        "acceptedContractDigest": decision["contractCanonicalDigest"],
        "finalCheckName": CHECK_NAME,
        "workflowCount": 2,
        "selectedRepositoryCount": 3,
        "liveConsumerReadback": True,
        "artifactBodiesVerified": True,
        "receiptCandidateShaBound": True,
        "admissions": admissions,
        "productionAdmission": True,
        "mergeAdmissionAuthority": True,
        "meaningAuthority": False,
        "effectAuthority": False,
        "allRepositoriesEnforced": False,
    }


def fake_packet(rollout: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for index, contract in enumerate(rollout["repositories"], 1):
        head = str(index) * 40
        receipt = {
            "kind": "governance.selectedConsumerReceipt.v1",
            "status": "pass",
            "repository": contract["repository"],
            "role": contract["role"],
            "candidateSha": head,
            "assertionId": contract["assertionId"],
            "acceptedBundleDigest": contract["acceptedBundleDigest"],
            "sourceClosureDigest": contract["sourceClosureDigest"],
            "authority": False,
            "allRepositoriesEnforced": False,
        }
        if contract.get("knownMismatchRejected"):
            receipt["knownMismatchRejected"] = True
        rows.append(
            {
                "repository": contract["repository"],
                "branch": contract["branch"],
                "currentHead": head,
                "claimPath": contract["claimPath"],
                "claimDigest": "sha256:" + str(index) * 64,
                "runId": index,
                "runHeadSha": head,
                "runEvent": "push",
                "runConclusion": "success",
                "workflowName": contract["workflowName"],
                "workflowPath": contract["workflowPath"],
                "artifactId": 100 + index,
                "artifactName": contract["artifactName"],
                "artifactDigest": "sha256:" + str(index + 2) * 64,
                "receiptPath": contract["receiptPath"],
                "receiptDigest": "sha256:" + str(index + 4) * 64,
                "receipt": receipt,
            }
        )
    return {
        "kind": "governance.liveSelectedConsumerPacket.v1",
        "status": "pass",
        "repositoryCount": 2,
        "allRepositoriesEnforced": False,
        "repositories": rows,
    }


def selftest() -> dict[str, Any]:
    rollout = read_json(ROLLOUT)
    packet = fake_packet(rollout)
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        live_path = root / "live.json"
        live_path.write_text(canonical(packet), encoding="utf-8")
        check("a" * 40, live_path)
        cases: list[tuple[str, Callable[[dict[str, Any], dict[str, Any]], None], str]] = [
            (
                "receipt-sha",
                lambda rollout_value, packet_value: packet_value["repositories"][0]["receipt"].update(
                    candidateSha="f" * 40
                ),
                "receipt-candidate-sha",
            ),
            (
                "run-head",
                lambda rollout_value, packet_value: packet_value["repositories"][0].update(
                    runHeadSha="e" * 40
                ),
                "live-run-head",
            ),
            (
                "claim-digest",
                lambda rollout_value, packet_value: packet_value["repositories"][0].update(
                    claimDigest="bad"
                ),
                "live-claim-digest",
            ),
            (
                "failed-run",
                lambda rollout_value, packet_value: packet_value["repositories"][0].update(
                    runConclusion="failure"
                ),
                "live-run-conclusion",
            ),
            (
                "missing-live-repo",
                lambda rollout_value, packet_value: packet_value["repositories"].pop(),
                "live-cardinality",
            ),
            (
                "checked-in-evidence",
                lambda rollout_value, packet_value: rollout_value["repositories"][0].update(
                    candidateHead="b" * 40
                ),
                "checked-in-live-evidence",
            ),
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
            except GateError as exc:
                need(expected_code in str(exc), f"wrong-finding:{name}:{exc}")
                rejected.append({"case": name, "status": "rejected", "finding": str(exc)})
            else:
                raise GateError(f"destructive case passed:{name}")
    return {
        "kind": "governance.finalCiProductionGate.selftest.v2",
        "status": "pass",
        "positiveCases": 1,
        "destructiveCases": len(rejected),
        "cases": rejected,
        "authority": False,
    }


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
