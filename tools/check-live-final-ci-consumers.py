#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import re

SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
API_VERSION = "2022-11-28"
USER_AGENT = "roccho-dev-governance-final-ci/2"


class LiveError(ValueError):
    pass


def need(ok: bool, code: str) -> None:
    if not ok:
        raise LiveError(code)


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass
class HttpResponse:
    status: int
    url: str
    headers: dict[str, str]
    body: bytes


class GitHubApi:
    def __init__(self, token: str | None = None, base_url: str = "https://api.github.com") -> None:
        self.token = token or None
        self.base_url = base_url.rstrip("/")

    def _request_once(self, path: str, token: str | None, accept: str) -> HttpResponse:
        url = path if path.startswith(("http://", "https://")) else self.base_url + path
        headers = {
            "Accept": accept,
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": API_VERSION,
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return HttpResponse(
                    status=response.status,
                    url=response.geturl(),
                    headers={key.lower(): value for key, value in response.headers.items()},
                    body=response.read(),
                )
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")
            raise LiveError(f"github-http:{exc.code}:{url}:{body[:300]}") from exc
        except urllib.error.URLError as exc:
            raise LiveError(f"github-network:{url}:{exc.reason}") from exc

    def request(self, path: str, accept: str = "application/vnd.github+json") -> HttpResponse:
        try:
            return self._request_once(path, self.token, accept)
        except LiveError as exc:
            text = str(exc)
            if self.token and (":403:" in text or ":404:" in text):
                return self._request_once(path, None, accept)
            raise

    def get_json(self, path: str) -> Any:
        response = self.request(path)
        try:
            return json.loads(response.body)
        except json.JSONDecodeError as exc:
            raise LiveError(f"github-json:{path}") from exc

    def get_bytes(self, path: str) -> bytes:
        return self.request(path, "application/octet-stream").body


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    need(isinstance(value, dict), f"not-object:{path}")
    return value


def decode_content(value: dict[str, Any], code: str) -> bytes:
    need(value.get("encoding") == "base64", f"{code}:encoding")
    content = value.get("content")
    need(isinstance(content, str), f"{code}:content")
    try:
        return base64.b64decode(content, validate=False)
    except Exception as exc:
        raise LiveError(f"{code}:base64") from exc


def validate_claim(claim: dict[str, Any], expected: dict[str, Any]) -> None:
    repo = expected["repository"]
    need(claim.get("kind") == "governance.selectedConsumerClaim.v1", f"claim-kind:{repo}")
    need(claim.get("repository") == repo, f"claim-repository:{repo}")
    need(claim.get("role") == expected["role"], f"claim-role:{repo}")
    need(claim.get("allRepositoriesEnforced") is False, f"claim-overclaim:{repo}")
    decision = claim.get("decision")
    need(isinstance(decision, dict), f"claim-decision:{repo}")
    need(decision.get("acceptedMerge") == expected["decisionMerge"], f"claim-decision-merge:{repo}")
    need("sha256:" + str(decision.get("contractDigest")) == expected["acceptedBundleDigest"], f"claim-bundle:{repo}")
    assertion = claim.get("assertion")
    need(isinstance(assertion, dict), f"claim-assertion:{repo}")
    need(assertion.get("assertionId") == expected["assertionId"], f"claim-assertion-id:{repo}")
    need(assertion.get("lifecycle") == expected["lifecycle"], f"claim-lifecycle:{repo}")
    need(assertion.get("generatedMeaningFreeAdapter") is True, f"claim-adapter:{repo}")
    need(assertion.get("acceptedBundleDigest") == expected["acceptedBundleDigest"], f"claim-assertion-bundle:{repo}")
    need(assertion.get("sourceClosureDigest") == expected["sourceClosureDigest"], f"claim-assertion-closure:{repo}")
    receipt_contract = claim.get("receiptContract")
    need(isinstance(receipt_contract, dict), f"claim-receipt-contract:{repo}")
    need(receipt_contract.get("candidateShaSource") == "github.event.pull_request.head.sha || github.sha", f"claim-sha-source:{repo}")
    need(receipt_contract.get("requiredResult") == "pass", f"claim-result:{repo}")
    need(receipt_contract.get("authority") is False, f"claim-receipt-authority:{repo}")


def validate_receipt(receipt: dict[str, Any], expected: dict[str, Any], current_head: str) -> None:
    repo = expected["repository"]
    need(receipt.get("kind") == "governance.selectedConsumerReceipt.v1", f"receipt-kind:{repo}")
    need(receipt.get("status") == "pass", f"receipt-status:{repo}")
    need(receipt.get("repository") == repo, f"receipt-repository:{repo}")
    need(receipt.get("role") == expected["role"], f"receipt-role:{repo}")
    need(receipt.get("candidateSha") == current_head, f"receipt-candidate-sha:{repo}")
    need(receipt.get("assertionId") == expected["assertionId"], f"receipt-assertion:{repo}")
    need(receipt.get("acceptedBundleDigest") == expected["acceptedBundleDigest"], f"receipt-bundle:{repo}")
    need(receipt.get("sourceClosureDigest") == expected["sourceClosureDigest"], f"receipt-closure:{repo}")
    need(receipt.get("authority") is False, f"receipt-authority:{repo}")
    need(receipt.get("allRepositoriesEnforced") is False, f"receipt-overclaim:{repo}")
    if expected.get("knownMismatchRejected") is True:
        need(receipt.get("knownMismatchRejected") is True, f"receipt-known-mismatch:{repo}")


def artifact_receipt(zip_bytes: bytes, expected_path: str, repo: str) -> tuple[dict[str, Any], str]:
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
            names = [name for name in archive.namelist() if not name.endswith("/")]
            need(names == [expected_path], f"artifact-files:{repo}")
            raw = archive.read(expected_path)
    except zipfile.BadZipFile as exc:
        raise LiveError(f"artifact-zip:{repo}") from exc
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LiveError(f"artifact-json:{repo}") from exc
    need(isinstance(value, dict), f"artifact-object:{repo}")
    return value, "sha256:" + hashlib.sha256(raw).hexdigest()


def query(**params: Any) -> str:
    return urllib.parse.urlencode({key: value for key, value in params.items() if value is not None})


def capture_repository(api: GitHubApi, expected: dict[str, Any]) -> dict[str, Any]:
    repo = expected["repository"]
    branch = expected["branch"]
    metadata = api.get_json(f"/repos/{repo}")
    need(metadata.get("full_name") == repo, f"repo-metadata:{repo}")
    need(metadata.get("default_branch") == branch, f"default-branch:{repo}")
    need(metadata.get("private") is False, f"repo-not-public:{repo}")

    ref = api.get_json(f"/repos/{repo}/git/ref/heads/{urllib.parse.quote(branch, safe='')}")
    current_head = ((ref.get("object") or {}).get("sha"))
    need(isinstance(current_head, str) and SHA.fullmatch(current_head) is not None, f"current-head:{repo}")

    claim_path = expected["claimPath"]
    claim_blob = api.get_json(f"/repos/{repo}/contents/{claim_path}?{query(ref=current_head)}")
    claim_raw = decode_content(claim_blob, f"claim-content:{repo}")
    try:
        claim = json.loads(claim_raw)
    except json.JSONDecodeError as exc:
        raise LiveError(f"claim-json:{repo}") from exc
    need(isinstance(claim, dict), f"claim-object:{repo}")
    validate_claim(claim, expected)
    claim_digest = "sha256:" + hashlib.sha256(claim_raw).hexdigest()

    runs = api.get_json(f"/repos/{repo}/actions/runs?{query(branch=branch, event='push', status='success', per_page=100)}")
    candidates = [
        run
        for run in runs.get("workflow_runs", [])
        if run.get("head_sha") == current_head
        and run.get("conclusion") == "success"
        and run.get("event") == "push"
        and (run.get("name") == expected["workflowName"] or run.get("path") == expected["workflowPath"])
    ]
    need(bool(candidates), f"live-run-missing:{repo}")
    candidates.sort(key=lambda run: int(run.get("id", 0)), reverse=True)
    run = candidates[0]
    run_id = run.get("id")
    need(isinstance(run_id, int) and run_id > 0, f"live-run-id:{repo}")

    artifacts_value = api.get_json(f"/repos/{repo}/actions/runs/{run_id}/artifacts?{query(per_page=100)}")
    artifacts = [
        item
        for item in artifacts_value.get("artifacts", [])
        if item.get("name") == expected["artifactName"] and item.get("expired") is False
    ]
    need(len(artifacts) == 1, f"live-artifact-cardinality:{repo}")
    artifact = artifacts[0]
    artifact_id = artifact.get("id")
    artifact_digest = artifact.get("digest")
    need(isinstance(artifact_id, int) and artifact_id > 0, f"live-artifact-id:{repo}")
    need(isinstance(artifact_digest, str) and DIGEST.fullmatch(artifact_digest) is not None, f"live-artifact-digest:{repo}")

    zip_bytes = api.get_bytes(f"/repos/{repo}/actions/artifacts/{artifact_id}/zip")
    observed_artifact_digest = "sha256:" + hashlib.sha256(zip_bytes).hexdigest()
    need(observed_artifact_digest == artifact_digest, f"live-artifact-digest-mismatch:{repo}")
    receipt, receipt_digest = artifact_receipt(zip_bytes, expected["receiptPath"], repo)
    validate_receipt(receipt, expected, current_head)

    return {
        "repository": repo,
        "branch": branch,
        "currentHead": current_head,
        "claimPath": claim_path,
        "claimBlobSha": claim_blob.get("sha"),
        "claimDigest": claim_digest,
        "runId": run_id,
        "runHeadSha": run.get("head_sha"),
        "runEvent": run.get("event"),
        "runConclusion": run.get("conclusion"),
        "workflowName": run.get("name"),
        "workflowPath": run.get("path"),
        "artifactId": artifact_id,
        "artifactName": artifact.get("name"),
        "artifactDigest": artifact_digest,
        "artifactCreatedAt": artifact.get("created_at"),
        "receiptPath": expected["receiptPath"],
        "receiptDigest": receipt_digest,
        "receipt": receipt,
    }


def validate_rollout(rollout: dict[str, Any]) -> list[dict[str, Any]]:
    need(rollout.get("kind") == "governance.selectedFinalCiRollout.v2", "rollout-kind")
    need(rollout.get("allRepositoriesEnforced") is False, "rollout-overclaim")
    repositories = rollout.get("repositories")
    need(isinstance(repositories, list) and len(repositories) == 2, "rollout-cardinality")
    need({row.get("repository") for row in repositories if isinstance(row, dict)} == {"roccho-dev/ui", "roccho-dev/ops"}, "rollout-repositories")
    for row in repositories:
        need(isinstance(row, dict), "rollout-row")
        for field in (
            "repository",
            "branch",
            "role",
            "assertionId",
            "claimPath",
            "workflowName",
            "workflowPath",
            "artifactName",
            "receiptPath",
            "decisionMerge",
            "acceptedBundleDigest",
            "sourceClosureDigest",
            "lifecycle",
        ):
            need(isinstance(row.get(field), str) and bool(row[field]), f"rollout-field:{row.get('repository')}:{field}")
        need(row.get("authority") is False, f"rollout-authority:{row.get('repository')}")
    return repositories


def capture(rollout: dict[str, Any], api: GitHubApi) -> dict[str, Any]:
    repositories = validate_rollout(rollout)
    live = [capture_repository(api, row) for row in repositories]
    return {
        "kind": "governance.liveSelectedConsumerPacket.v1",
        "status": "pass",
        "repositoryCount": len(live),
        "allRepositoriesEnforced": False,
        "repositories": live,
    }


class FakeApi(GitHubApi):
    def __init__(self, json_routes: dict[str, Any], bytes_routes: dict[str, bytes]) -> None:
        self.json_routes = json_routes
        self.bytes_routes = bytes_routes
        super().__init__(None, "https://fake.invalid")

    def get_json(self, path: str) -> Any:
        if path not in self.json_routes:
            raise LiveError(f"fake-json-missing:{path}")
        return self.json_routes[path]

    def get_bytes(self, path: str) -> bytes:
        if path not in self.bytes_routes:
            raise LiveError(f"fake-bytes-missing:{path}")
        return self.bytes_routes[path]


def make_zip(receipt: dict[str, Any], path: str) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(path, canonical(receipt) + "\n")
    return out.getvalue()


def fake_for(rollout: dict[str, Any]) -> FakeApi:
    json_routes: dict[str, Any] = {}
    bytes_routes: dict[str, bytes] = {}
    for index, expected in enumerate(rollout["repositories"], 1):
        repo = expected["repository"]
        head = str(index) * 40
        claim = {
            "kind": "governance.selectedConsumerClaim.v1",
            "repository": repo,
            "role": expected["role"],
            "allRepositoriesEnforced": False,
            "decision": {
                "acceptedMerge": expected["decisionMerge"],
                "contractDigest": expected["acceptedBundleDigest"].removeprefix("sha256:"),
            },
            "assertion": {
                "assertionId": expected["assertionId"],
                "lifecycle": expected["lifecycle"],
                "generatedMeaningFreeAdapter": True,
                "acceptedBundleDigest": expected["acceptedBundleDigest"],
                "sourceClosureDigest": expected["sourceClosureDigest"],
            },
            "receiptContract": {
                "candidateShaSource": "github.event.pull_request.head.sha || github.sha",
                "requiredResult": "pass",
                "authority": False,
            },
        }
        receipt = {
            "kind": "governance.selectedConsumerReceipt.v1",
            "status": "pass",
            "repository": repo,
            "role": expected["role"],
            "candidateSha": head,
            "assertionId": expected["assertionId"],
            "acceptedBundleDigest": expected["acceptedBundleDigest"],
            "sourceClosureDigest": expected["sourceClosureDigest"],
            "authority": False,
            "allRepositoriesEnforced": False,
        }
        if expected.get("knownMismatchRejected"):
            receipt["knownMismatchRejected"] = True
        zip_bytes = make_zip(receipt, expected["receiptPath"])
        artifact_id = 1000 + index
        run_id = 2000 + index
        json_routes[f"/repos/{repo}"] = {"full_name": repo, "default_branch": expected["branch"], "private": False}
        json_routes[f"/repos/{repo}/git/ref/heads/{expected['branch']}"] = {"object": {"sha": head}}
        json_routes[f"/repos/{repo}/contents/{expected['claimPath']}?ref={head}"] = {
            "encoding": "base64",
            "content": base64.b64encode(canonical(claim).encode()).decode(),
            "sha": "blob",
        }
        runs_path = f"/repos/{repo}/actions/runs?branch={expected['branch']}&event=push&status=success&per_page=100"
        json_routes[runs_path] = {
            "workflow_runs": [
                {
                    "id": run_id,
                    "head_sha": head,
                    "conclusion": "success",
                    "event": "push",
                    "name": expected["workflowName"],
                    "path": expected["workflowPath"],
                }
            ]
        }
        json_routes[f"/repos/{repo}/actions/runs/{run_id}/artifacts?per_page=100"] = {
            "artifacts": [
                {
                    "id": artifact_id,
                    "name": expected["artifactName"],
                    "expired": False,
                    "digest": "sha256:" + hashlib.sha256(zip_bytes).hexdigest(),
                    "created_at": "2026-07-18T00:00:00Z",
                }
            ]
        }
        bytes_routes[f"/repos/{repo}/actions/artifacts/{artifact_id}/zip"] = zip_bytes
    return FakeApi(json_routes, bytes_routes)


def expected_head(api: FakeApi, expected: dict[str, Any]) -> str:
    return api.json_routes[f"/repos/{expected['repository']}/git/ref/heads/{expected['branch']}"]["object"]["sha"]


def run_path(expected: dict[str, Any]) -> str:
    return f"/repos/{expected['repository']}/actions/runs?branch={expected['branch']}&event=push&status=success&per_page=100"


def artifact_row(api: FakeApi, expected: dict[str, Any]) -> dict[str, Any]:
    run = api.json_routes[run_path(expected)]["workflow_runs"][0]
    path = f"/repos/{expected['repository']}/actions/runs/{run['id']}/artifacts?per_page=100"
    return api.json_routes[path]["artifacts"][0]


def mutate_receipt(api: FakeApi, expected: dict[str, Any], **fields: Any) -> None:
    artifact = artifact_row(api, expected)
    zip_path = f"/repos/{expected['repository']}/actions/artifacts/{artifact['id']}/zip"
    with zipfile.ZipFile(io.BytesIO(api.bytes_routes[zip_path])) as archive:
        receipt = json.loads(archive.read(expected["receiptPath"]))
    receipt.update(fields)
    zip_bytes = make_zip(receipt, expected["receiptPath"])
    api.bytes_routes[zip_path] = zip_bytes
    artifact["digest"] = "sha256:" + hashlib.sha256(zip_bytes).hexdigest()


def selftest(rollout: dict[str, Any]) -> dict[str, Any]:
    packet = capture(rollout, fake_for(rollout))
    need(packet["repositoryCount"] == 2, "selftest-positive")
    rejected = []
    import copy

    cases: list[tuple[str, Callable[[dict[str, Any], FakeApi], None], str]] = []
    cases.append(("receipt-sha", lambda value, api: mutate_receipt(api, value["repositories"][0], candidateSha="f" * 40), "receipt-candidate-sha"))
    cases.append(("run-head", lambda value, api: api.json_routes[run_path(value["repositories"][0])]["workflow_runs"][0].update(head_sha="e" * 40), "live-run-missing"))
    cases.append(("artifact-digest", lambda value, api: artifact_row(api, value["repositories"][0]).update(digest="sha256:" + "0" * 64), "live-artifact-digest-mismatch"))
    cases.append(("expired-artifact", lambda value, api: artifact_row(api, value["repositories"][0]).update(expired=True), "live-artifact-cardinality"))
    cases.append(("missing-run", lambda value, api: api.json_routes[run_path(value["repositories"][0])].update(workflow_runs=[]), "live-run-missing"))

    for name, mutate, expected_code in cases:
        candidate_rollout = copy.deepcopy(rollout)
        api = fake_for(candidate_rollout)
        mutate(candidate_rollout, api)
        try:
            capture(candidate_rollout, api)
        except LiveError as exc:
            need(expected_code in str(exc), f"selftest-finding:{name}:{exc}")
            rejected.append({"case": name, "status": "rejected", "finding": str(exc)})
        else:
            raise LiveError(f"selftest-false-green:{name}")
    return {
        "kind": "governance.liveSelectedConsumerPacket.selftest.v1",
        "status": "pass",
        "positiveCases": 1,
        "destructiveCases": len(rejected),
        "cases": rejected,
        "authority": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture and verify live selected consumer claims and exact-SHA receipt artifacts.")
    parser.add_argument("command", choices=["capture", "selftest"])
    parser.add_argument("--rollout", type=Path, default=Path("governance/selected-final-ci-rollout.v1.json"))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--api-url", default=os.environ.get("GITHUB_API_URL", "https://api.github.com"))
    parser.add_argument("--token-env", default="GITHUB_TOKEN")
    args = parser.parse_args()
    rollout = read_json(args.rollout)
    report = selftest(rollout) if args.command == "selftest" else capture(rollout, GitHubApi(os.environ.get(args.token_env), args.api_url))
    text = canonical(report) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LiveError as exc:
        print(canonical({"kind": "governance.liveSelectedConsumerPacket.v1", "status": "fail", "finding": str(exc)}), file=sys.stderr)
        raise SystemExit(1)
