from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
IDENTITY_PATH = ROOT / "governance/gov-release-identity.v1.json"
SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


class IdentityError(ValueError):
    pass


def need(ok: bool, code: str) -> None:
    if not ok:
        raise IdentityError(code)


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    need(isinstance(value, dict), f"not-object:{path}")
    return value


def validate_identity(value: dict[str, Any]) -> dict[str, Any]:
    need(value.get("kind") == "governance.govReleaseIdentityProjection.v1", "identity-kind")
    source = value.get("source")
    decision = value.get("acceptedDecision")
    contract = value.get("contract")
    topology = value.get("currentTopology")
    need(isinstance(source, dict), "identity-source")
    need(isinstance(decision, dict), "identity-decision")
    need(isinstance(contract, dict), "identity-contract")
    need(isinstance(topology, dict), "identity-topology")
    need(source.get("repository") == "roccho-dev/adrs", "identity-repository")
    need(source.get("pullRequest") == 242, "identity-pull-request")
    need(isinstance(source.get("head"), str) and SHA.fullmatch(source["head"]) is not None, "identity-head")
    need(source.get("decisionPath") == "release/v1/accepted-decision.json", "identity-decision-path")
    need(source.get("contractPath") == "release/v1/contract.json", "identity-contract-path")
    need(source.get("status") in {"accepted-in-candidate", "accepted"}, "identity-status")
    need(isinstance(decision.get("canonicalDigest"), str) and DIGEST.fullmatch(decision["canonicalDigest"]) is not None, "identity-decision-digest")
    need(isinstance(contract.get("canonicalDigest"), str) and DIGEST.fullmatch(contract["canonicalDigest"]) is not None, "identity-contract-digest")
    need(isinstance(topology.get("acceptedMerge"), str) and SHA.fullmatch(topology["acceptedMerge"]) is not None, "identity-accepted-merge")
    need(topology.get("stableCheckName") == "gov-final-scope-purpose-join / gate", "identity-stable-check")
    need(value.get("selectedScope") == ["roccho-dev/governance", "roccho-dev/ui", "roccho-dev/ops"], "identity-selected-scope")
    need(value.get("allRepositoriesEnforced") is False, "identity-all-repositories")
    need(value.get("businessOutcomeAchieved") is False, "identity-business-outcome")
    need(value.get("authority") is False, "identity-authority")
    return value


def load_identity(path: Path = IDENTITY_PATH) -> dict[str, Any]:
    return validate_identity(read_json(path))


def workflow_outputs(value: dict[str, Any]) -> dict[str, str]:
    return {
        "adrs_repository": value["source"]["repository"],
        "adrs_pull_request": str(value["source"]["pullRequest"]),
        "adrs_head": value["source"]["head"],
        "decision_path": value["source"]["decisionPath"],
        "contract_path": value["source"]["contractPath"],
        "decision_status": value["source"]["status"],
        "accepted_decision_digest": value["acceptedDecision"]["canonicalDigest"],
        "contract_digest": value["contract"]["canonicalDigest"],
        "accepted_merge": value["currentTopology"]["acceptedMerge"],
        "stable_check_name": value["currentTopology"]["stableCheckName"],
    }


def duplicate_identity_literals(root: Path = ROOT) -> list[dict[str, str]]:
    identity = load_identity()
    values = {
        "adrs-head": identity["source"]["head"],
        "accepted-decision-digest": identity["acceptedDecision"]["canonicalDigest"],
        "contract-digest": identity["contract"]["canonicalDigest"],
    }
    findings: list[dict[str, str]] = []
    allowed = {IDENTITY_PATH.resolve()}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.resolve() in allowed or ".git" in path.parts:
            continue
        if path.suffix not in {".py", ".json", ".jsonl", ".yml", ".yaml", ".md", ".sh"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for code, literal in values.items():
            if literal in text:
                findings.append({"code": code, "path": path.relative_to(root).as_posix()})
    return findings


def selftest() -> dict[str, Any]:
    value = load_identity()
    bad = json.loads(json.dumps(value))
    bad["source"]["head"] = "bad"
    try:
        validate_identity(bad)
    except IdentityError as exc:
        need(str(exc) == "identity-head", "identity-selftest-finding")
    else:
        raise IdentityError("identity-selftest-false-green")
    findings = duplicate_identity_literals()
    need(not findings, "duplicate-identity-literals:" + json.dumps(findings, sort_keys=True, separators=(",", ":")))
    return {
        "kind": "governance.govReleaseIdentityProjection.selftest.v1",
        "status": "pass",
        "identityPath": IDENTITY_PATH.relative_to(ROOT).as_posix(),
        "duplicateLiteralCount": 0,
        "authority": False,
        "allRepositoriesEnforced": False,
        "businessOutcomeAchieved": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["json", "github-output", "selftest"])
    args = parser.parse_args()
    value = load_identity()
    if args.command == "json":
        print(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    elif args.command == "github-output":
        for key, item in workflow_outputs(value).items():
            print(f"{key}={item}")
    else:
        print(json.dumps(selftest(), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
