#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

CHECK = "gov-final-scope-purpose-join / gate"
LEGACY = {"repo-governance / proof"}
SHA = re.compile(r"^[0-9a-f]{40}$")


class ControlPlaneError(ValueError):
    pass


def need(ok: bool, code: str) -> None:
    if not ok:
        raise ControlPlaneError(code)


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class Api:
    def __init__(self, token: str | None = None, base_url: str = "https://api.github.com") -> None:
        self.token = token or None
        self.base_url = base_url.rstrip("/")

    def get(self, path: str) -> Any:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "roccho-dev-governance-control-plane/1",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(self.base_url + path, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")
            raise ControlPlaneError(f"github-http:{exc.code}:{path}:{body[:300]}") from exc
        except urllib.error.URLError as exc:
            raise ControlPlaneError(f"github-network:{path}:{exc.reason}") from exc


class FakeApi(Api):
    def __init__(self, routes: dict[str, Any]) -> None:
        self.routes = routes
        super().__init__(None, "https://fake.invalid")

    def get(self, path: str) -> Any:
        if path not in self.routes:
            raise ControlPlaneError(f"fake-missing:{path}")
        return self.routes[path]


def decode_content(value: dict[str, Any], code: str) -> str:
    need(value.get("encoding") == "base64", f"{code}:encoding")
    content = value.get("content")
    need(isinstance(content, str), f"{code}:content")
    return base64.b64decode(content).decode("utf-8")


def ref_matches(conditions: dict[str, Any], branch: str, default_branch: str) -> bool:
    ref = conditions.get("ref_name") or {}
    include = ref.get("include") or []
    exclude = ref.get("exclude") or []
    aliases = {branch, f"refs/heads/{branch}", "~ALL"}
    if branch == default_branch:
        aliases.add("~DEFAULT_BRANCH")
    included = not include or any(item in aliases for item in include)
    excluded = any(item in aliases for item in exclude)
    return included and not excluded


def check(api: Api, repo: str = "roccho-dev/governance", branch: str = "proposals") -> dict[str, Any]:
    metadata = api.get(f"/repos/{repo}")
    need(metadata.get("full_name") == repo, "repo-metadata")
    need(metadata.get("default_branch") == branch, "default-branch")
    ref = api.get(f"/repos/{repo}/git/ref/heads/{branch}")
    head = ((ref.get("object") or {}).get("sha"))
    need(isinstance(head, str) and SHA.fullmatch(head) is not None, "branch-head")

    intent_value = api.get(f"/repos/{repo}/contents/ci.intent.v1.jsonl?ref={head}")
    intent_text = decode_content(intent_value, "ci-intent")
    intents = [json.loads(line) for line in intent_text.splitlines() if line.strip()]
    need(len(intents) == 2, "ci-intent-cardinality")
    need(
        {row.get("path") for row in intents}
        == {".github/workflows/gov-final-scope-purpose-join.yml", ".github/workflows/gov-canary.yml"},
        "ci-intent-universe",
    )
    gate_rows = [row for row in intents if row.get("authority_class") == "merge-admission"]
    need(len(gate_rows) == 1 and gate_rows[0].get("required_check_name") == CHECK, "ci-intent-gate")

    summaries = api.get(f"/repos/{repo}/rulesets?includes_parents=true&per_page=100")
    need(isinstance(summaries, list), "rulesets-response")
    matched = []
    contexts: list[str] = []
    pull_request_required = False
    bypass_actors: list[Any] = []
    for summary in summaries:
        if summary.get("target") != "branch" or summary.get("enforcement") != "active":
            continue
        ruleset_id = summary.get("id")
        need(isinstance(ruleset_id, int), "ruleset-id")
        detail = api.get(f"/repos/{repo}/rulesets/{ruleset_id}")
        if not ref_matches(detail.get("conditions") or {}, branch, metadata["default_branch"]):
            continue
        matched.append({"id": ruleset_id, "name": detail.get("name"), "enforcement": detail.get("enforcement")})
        bypass_actors.extend(detail.get("bypass_actors") or [])
        for rule in detail.get("rules") or []:
            if rule.get("type") == "pull_request":
                pull_request_required = True
            if rule.get("type") == "required_status_checks":
                for item in (rule.get("parameters") or {}).get("required_status_checks") or []:
                    context = item.get("context")
                    if isinstance(context, str):
                        contexts.append(context)

    need(bool(matched), "ruleset-not-observable-or-missing")
    need(pull_request_required, "pull-request-rule-missing")
    need(not bypass_actors, "ruleset-bypass-present")
    need(not (set(contexts) & LEGACY), "legacy-required-check")
    need(contexts.count(CHECK) == 1, "stable-check-cardinality")
    need(set(contexts) == {CHECK}, "required-check-not-exclusive")

    return {
        "kind": "governance.liveFinalCiControlPlaneObservation.v1",
        "status": "pass",
        "repository": repo,
        "branch": branch,
        "observedHead": head,
        "workflowCount": 2,
        "matchingActiveRulesets": matched,
        "requiredStatusChecks": contexts,
        "pullRequestRequired": True,
        "bypassActorCount": 0,
        "stableCheckExclusive": True,
        "permanentMergePathProven": True,
        "authority": False,
        "allRepositoriesEnforced": False,
    }


def fake_routes(context: str = CHECK, bypass: bool = False, enforcement: str = "active") -> dict[str, Any]:
    head = "a" * 40
    intents = [
        {
            "path": ".github/workflows/gov-final-scope-purpose-join.yml",
            "authority_class": "merge-admission",
            "required_check_name": CHECK,
        },
        {"path": ".github/workflows/gov-canary.yml", "authority_class": "evidence-only"},
    ]
    return {
        "/repos/roccho-dev/governance": {"full_name": "roccho-dev/governance", "default_branch": "proposals"},
        "/repos/roccho-dev/governance/git/ref/heads/proposals": {"object": {"sha": head}},
        f"/repos/roccho-dev/governance/contents/ci.intent.v1.jsonl?ref={head}": {
            "encoding": "base64",
            "content": base64.b64encode(("\n".join(canonical(row) for row in intents) + "\n").encode()).decode(),
        },
        "/repos/roccho-dev/governance/rulesets?includes_parents=true&per_page=100": [
            {"id": 7, "target": "branch", "enforcement": enforcement}
        ],
        "/repos/roccho-dev/governance/rulesets/7": {
            "id": 7,
            "name": "proposals final gate",
            "target": "branch",
            "enforcement": enforcement,
            "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
            "bypass_actors": [{"actor_id": 1}] if bypass else [],
            "rules": [
                {"type": "pull_request", "parameters": {}},
                {
                    "type": "required_status_checks",
                    "parameters": {"required_status_checks": [{"context": context}]},
                },
            ],
        },
    }


def selftest() -> dict[str, Any]:
    check(FakeApi(fake_routes()))
    duplicate = fake_routes()
    duplicate["/repos/roccho-dev/governance/rulesets/7"]["rules"][1]["parameters"]["required_status_checks"].append(
        {"context": CHECK}
    )
    cases = [
        ("legacy", fake_routes(context="repo-governance / proof"), "legacy-required-check"),
        ("bypass", fake_routes(bypass=True), "ruleset-bypass-present"),
        ("evaluate", fake_routes(enforcement="evaluate"), "ruleset-not-observable-or-missing"),
        ("duplicate", duplicate, "stable-check-cardinality"),
    ]
    rejected = []
    for name, routes, expected in cases:
        try:
            check(FakeApi(routes))
        except ControlPlaneError as exc:
            need(expected in str(exc), f"wrong-finding:{name}:{exc}")
            rejected.append({"case": name, "status": "rejected", "finding": str(exc)})
        else:
            raise ControlPlaneError(f"false-green:{name}")
    return {
        "kind": "governance.liveFinalCiControlPlaneObservation.selftest.v1",
        "status": "pass",
        "positiveCases": 1,
        "destructiveCases": len(rejected),
        "cases": rejected,
        "authority": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["check", "selftest"])
    parser.add_argument("--out", type=Path)
    parser.add_argument("--repo", default="roccho-dev/governance")
    parser.add_argument("--branch", default="proposals")
    parser.add_argument("--api-url", default=os.environ.get("GITHUB_API_URL", "https://api.github.com"))
    parser.add_argument("--token-env", default="GITHUB_TOKEN")
    args = parser.parse_args()
    report = (
        selftest()
        if args.command == "selftest"
        else check(Api(os.environ.get(args.token_env), args.api_url), args.repo, args.branch)
    )
    text = canonical(report) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ControlPlaneError as exc:
        print(
            canonical(
                {
                    "kind": "governance.liveFinalCiControlPlaneObservation.v1",
                    "status": "fail",
                    "finding": str(exc),
                }
            ),
            file=sys.stderr,
        )
        raise SystemExit(1)
