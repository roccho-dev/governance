#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import re
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
ARTIFACT_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
EXPECTED_REPOS = {
    "roccho-dev/ui": "positive-feature-consumer",
    "roccho-dev/ops": "migration-consumer-known-mismatch",
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
    need(value.get("contractCanonicalDigest") == "8106d85404e636a9797dfb8e0a1f6343db8a7867ff904577f682e5d82ad9b314", "decision-digest")
    need(value.get("authorityClasses") == ["accepted-meaning", "merge-admission", "effect", "evidence-only"], "authority-classes")
    need(value.get("targetWorkflows") == ["gov-gate", "gov-canary"], "target-workflows")
    need(value.get("stableRequiredCheck") == CHECK_NAME, "check-name")
    need(value.get("allRepositoriesEnforced") is False, "decision-overclaim")


def validate_rollout(value: dict[str, Any]) -> None:
    need(value.get("kind") == "governance.selectedFinalCiRollout.v1", "rollout-kind")
    need(value.get("decisionMerge") == "a8fc9e8e04d53f1d783317059e4421c8dc724d01", "rollout-decision")
    need(value.get("allRepositoriesEnforced") is False, "rollout-overclaim")
    rows = value.get("repositories")
    need(isinstance(rows, list) and len(rows) == 2, "rollout-cardinality")
    by_repo = {row.get("repository"): row for row in rows if isinstance(row, dict)}
    need(set(by_repo) == set(EXPECTED_REPOS), "rollout-repositories")
    for repo, role in EXPECTED_REPOS.items():
        row = by_repo[repo]
        need(row.get("role") == role, f"rollout-role:{repo}")
        need(SHA.fullmatch(str(row.get("candidateHead", ""))) is not None, f"candidate-head:{repo}")
        need(SHA.fullmatch(str(row.get("mergeCommit", ""))) is not None, f"merge-commit:{repo}")
        need(row.get("receiptStatus") == "pass", f"receipt-status:{repo}")
        need(isinstance(row.get("receiptRunId"), int) and row["receiptRunId"] > 0, f"receipt-run:{repo}")
        need(ARTIFACT_DIGEST.fullmatch(str(row.get("receiptArtifactDigest", ""))) is not None, f"artifact-digest:{repo}")
        need(row.get("acceptedBundleDigest") == "sha256:8106d85404e636a9797dfb8e0a1f6343db8a7867ff904577f682e5d82ad9b314", f"bundle:{repo}")
        need(row.get("sourceClosureDigest") == "sha256:a8fc9e8e04d53f1d783317059e4421c8dc724d01", f"closure:{repo}")
        need(row.get("lifecycle") == "active", f"lifecycle:{repo}")
        need(row.get("authority") is False, f"receipt-authority:{repo}")


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
    gate_intent = by_path[GATE]
    canary_intent = by_path[CANARY]
    need(gate_intent.get("required_check_name") == CHECK_NAME, "intent-check-name")
    need(gate_intent.get("authority_class") == "merge-admission", "intent-gate-authority")
    need(gate_intent.get("candidate_sha_source") == "github.event.pull_request.head.sha || github.sha", "intent-sha-source")
    need(canary_intent.get("authority_class") == "evidence-only", "intent-canary-authority")
    need(canary_intent.get("authority") is False, "canary-authority")

    gate_text = (ROOT / GATE).read_text(encoding="utf-8")
    canary_text = (ROOT / CANARY).read_text(encoding="utf-8")
    need("name: gov-final-scope-purpose-join" in gate_text, "gate-workflow-name")
    need("name: gate" in gate_text, "gate-job-name")
    need("github.event.pull_request.head.sha || github.sha" in gate_text, "gate-exact-sha")
    need("persist-credentials: false" in gate_text, "gate-credentials")
    need("a8fc9e8e04d53f1d783317059e4421c8dc724d01" in gate_text, "gate-accepted-decision")
    need("pull_request_target" not in gate_text, "pull-request-target")
    need("name: gov-canary" in canary_text, "canary-workflow-name")
    need("schedule:" in canary_text and "workflow_dispatch:" in canary_text, "canary-triggers")
    need("pull_request:" not in canary_text and "push:" not in canary_text, "canary-effect-trigger")
    need("contents: read" in canary_text, "canary-read-permission")


def compile_selected_admissions(rollout: dict[str, Any], candidate_sha: str) -> list[dict[str, Any]]:
    compiler = load_compiler()
    bundle = "sha256:8106d85404e636a9797dfb8e0a1f6343db8a7867ff904577f682e5d82ad9b314"
    closure = "sha256:a8fc9e8e04d53f1d783317059e4421c8dc724d01"
    grants = []
    assertions = []
    receipts = []
    for subject in ["repo:roccho-dev/governance", "repo:roccho-dev/ui", "repo:roccho-dev/ops"]:
        grants.append({"subjectId": subject, "grantId": f"grant:{subject}", "acceptedBundleDigest": bundle, "sourceClosureDigest": closure, "lifecycle": "active"})
    assertions.append({"subjectId": "repo:roccho-dev/governance", "assertionId": "governance.final-ci-self.v1", "acceptedBundleDigest": bundle, "sourceClosureDigest": closure, "lifecycle": "active"})
    receipts.append({"subjectId": "repo:roccho-dev/governance", "receiptId": f"governance:{candidate_sha}", "acceptedBundleDigest": bundle, "sourceClosureDigest": closure})
    for row in rollout["repositories"]:
        subject = f"repo:{row['repository']}"
        assertions.append({"subjectId": subject, "assertionId": row["assertionId"], "acceptedBundleDigest": row["acceptedBundleDigest"], "sourceClosureDigest": row["sourceClosureDigest"], "lifecycle": row["lifecycle"]})
        receipts.append({"subjectId": subject, "receiptId": f"run:{row['receiptRunId']}", "acceptedBundleDigest": row["acceptedBundleDigest"], "sourceClosureDigest": row["sourceClosureDigest"]})
    rows = compiler.compile_admissions(grants, assertions, receipts)
    need(len(rows) == 3 and all(row.get("admissionResult") == "organization-active" for row in rows), "organization-admission")
    return rows


def check(candidate_sha: str, decision_path: Path = DECISION, rollout_path: Path = ROLLOUT) -> dict[str, Any]:
    need(SHA.fullmatch(candidate_sha) is not None, "candidate-sha")
    decision = read_json(decision_path)
    rollout = read_json(rollout_path)
    validate_decision(decision)
    validate_rollout(rollout)
    validate_provider_files()
    admissions = compile_selected_admissions(rollout, candidate_sha)
    return {
        "kind": "governance.finalCiProductionGate.v1",
        "status": "pass",
        "decision": "allow",
        "candidateSha": candidate_sha,
        "acceptedDecisionMerge": decision["acceptedMerge"],
        "acceptedContractDigest": decision["contractCanonicalDigest"],
        "finalCheckName": CHECK_NAME,
        "workflowCount": 2,
        "selectedRepositoryCount": 3,
        "admissions": admissions,
        "productionAdmission": True,
        "mergeAdmissionAuthority": True,
        "meaningAuthority": False,
        "effectAuthority": False,
        "allRepositoriesEnforced": False,
    }


def selftest() -> dict[str, Any]:
    decision = read_json(DECISION)
    rollout = read_json(ROLLOUT)
    check("a" * 40)
    cases: list[tuple[str, Callable[[dict[str, Any], dict[str, Any]], None], str]] = [
        ("decision", lambda d, r: d.update(acceptedMerge="0" * 40), "decision-merge"),
        ("overclaim", lambda d, r: r.update(allRepositoriesEnforced=True), "rollout-overclaim"),
        ("missing-repo", lambda d, r: r["repositories"].pop(), "rollout-cardinality"),
        ("bad-head", lambda d, r: r["repositories"][0].update(candidateHead="bad"), "candidate-head"),
        ("bad-merge", lambda d, r: r["repositories"][0].update(mergeCommit="bad"), "merge-commit"),
        ("failed-receipt", lambda d, r: r["repositories"][0].update(receiptStatus="fail"), "receipt-status"),
        ("missing-run", lambda d, r: r["repositories"][0].update(receiptRunId=0), "receipt-run"),
        ("bad-artifact", lambda d, r: r["repositories"][0].update(receiptArtifactDigest="bad"), "artifact-digest"),
        ("stale-bundle", lambda d, r: r["repositories"][0].update(acceptedBundleDigest="sha256:old"), "bundle"),
        ("stale-closure", lambda d, r: r["repositories"][0].update(sourceClosureDigest="sha256:old"), "closure"),
        ("revoked", lambda d, r: r["repositories"][0].update(lifecycle="revoked"), "lifecycle"),
        ("receipt-authority", lambda d, r: r["repositories"][0].update(authority=True), "receipt-authority"),
    ]
    results = []
    import tempfile
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        for name, mutate, expected in cases:
            d = copy.deepcopy(decision)
            r = copy.deepcopy(rollout)
            mutate(d, r)
            dp = root / f"{name}-decision.json"
            rp = root / f"{name}-rollout.json"
            dp.write_text(canonical(d), encoding="utf-8")
            rp.write_text(canonical(r), encoding="utf-8")
            try:
                check("a" * 40, dp, rp)
            except GateError as exc:
                need(expected in str(exc), f"wrong-finding:{name}:{exc}")
                results.append({"case": name, "status": "rejected", "finding": str(exc)})
            else:
                raise GateError(f"destructive case passed:{name}")
    return {"kind": "governance.finalCiProductionGate.selftest.v1", "status": "pass", "positiveCases": 1, "destructiveCases": len(results), "cases": results, "authority": False}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["check", "selftest"])
    parser.add_argument("--candidate-sha", default="a" * 40)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = check(args.candidate_sha) if args.command == "check" else selftest()
    print(canonical(report) if args.json else f"final-ci-production:{report['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
