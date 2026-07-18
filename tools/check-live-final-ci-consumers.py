#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import io
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
API_VERSION = "2022-11-28"
USER_AGENT = "roccho-dev-governance-final-ci/3"
STALE_FIELDS = {
    "candidateHead",
    "mergeCommit",
    "receiptRunId",
    "receiptArtifactDigest",
    "receiptStatus",
}


class LiveError(ValueError):
    pass


def need(ok: bool, code: str) -> None:
    if not ok:
        raise LiveError(code)


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class GitHubApi:
    def __init__(self, token: str | None = None, base_url: str = "https://api.github.com") -> None:
        self.token = token or None
        self.base_url = base_url.rstrip("/")

    def _request(self, path: str, token: str | None, accept: str) -> bytes:
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
                return response.read()
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")
            raise LiveError(f"github-http:{exc.code}:{url}:{body[:300]}") from exc
        except urllib.error.URLError as exc:
            raise LiveError(f"github-network:{url}:{exc.reason}") from exc

    def get_json(self, path: str) -> Any:
        try:
            raw = self._request(path, self.token, "application/vnd.github+json")
        except LiveError as exc:
            text = str(exc)
            if self.token and any(f":{code}:" in text for code in (401, 403, 404)):
                raw = self._request(path, None, "application/vnd.github+json")
            else:
                raise
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LiveError(f"github-json:{path}") from exc

    def get_bytes(self, path: str) -> bytes:
        try:
            return self._request(path, self.token, "application/octet-stream")
        except LiveError as exc:
            text = str(exc)
            if self.token and any(f":{code}:" in text for code in (401, 403, 404)):
                return self._request(path, None, "application/octet-stream")
            raise


def query(**params: Any) -> str:
    return urllib.parse.urlencode({key: value for key, value in params.items() if value is not None})


def decode_content(value: dict[str, Any], code: str) -> bytes:
    need(value.get("encoding") == "base64", f"{code}:encoding")
    content = value.get("content")
    need(isinstance(content, str), f"{code}:content")
    try:
        return base64.b64decode(content, validate=False)
    except Exception as exc:
        raise LiveError(f"{code}:base64") from exc


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    need(isinstance(value, dict), f"not-object:{path}")
    return value


def validate_rollout(rollout: dict[str, Any]) -> list[dict[str, Any]]:
    need(rollout.get("kind") == "governance.selectedFinalCiRollout.v2", "rollout-kind")
    need(rollout.get("allRepositoriesEnforced") is False, "rollout-overclaim")
    rows = rollout.get("repositories")
    need(isinstance(rows, list) and len(rows) == 2, "rollout-cardinality")
    need(
        {row.get("repository") for row in rows if isinstance(row, dict)}
        == {"roccho-dev/ui", "roccho-dev/ops"},
        "rollout-repositories",
    )
    for row in rows:
        need(isinstance(row, dict), "rollout-row")
        need(not (STALE_FIELDS & set(row)), f"checked-in-live-evidence:{row.get('repository')}")
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
            "snapshotPath",
            "decisionMerge",
            "acceptedBundleDigest",
            "sourceClosureDigest",
            "lifecycle",
        ):
            need(isinstance(row.get(field), str) and bool(row[field]), f"rollout-field:{row.get('repository')}:{field}")
        need(row.get("authority") is False, f"rollout-authority:{row.get('repository')}")
    return rows


def validate_claim(claim: dict[str, Any], expected: dict[str, Any]) -> None:
    repo = expected["repository"]
    need(claim.get("kind") == "governance.selectedConsumerClaim.v1", f"claim-kind:{repo}")
    need(claim.get("repository") == repo, f"claim-repository:{repo}")
    need(claim.get("role") == expected["role"], f"claim-role:{repo}")
    need(claim.get("allRepositoriesEnforced") is False, f"claim-overclaim:{repo}")
    decision = claim.get("decision") or {}
    need(decision.get("acceptedMerge") == expected["decisionMerge"], f"claim-decision-merge:{repo}")
    need("sha256:" + str(decision.get("contractDigest")) == expected["acceptedBundleDigest"], f"claim-bundle:{repo}")
    assertion = claim.get("assertion") or {}
    need(assertion.get("assertionId") == expected["assertionId"], f"claim-assertion-id:{repo}")
    need(assertion.get("lifecycle") == expected["lifecycle"], f"claim-lifecycle:{repo}")
    need(assertion.get("generatedMeaningFreeAdapter") is True, f"claim-adapter:{repo}")
    need(assertion.get("acceptedBundleDigest") == expected["acceptedBundleDigest"], f"claim-assertion-bundle:{repo}")
    need(assertion.get("sourceClosureDigest") == expected["sourceClosureDigest"], f"claim-assertion-closure:{repo}")
    contract = claim.get("receiptContract") or {}
    need(contract.get("candidateShaSource") == "github.event.pull_request.head.sha || github.sha", f"claim-sha-source:{repo}")
    need(contract.get("requiredResult") == "pass", f"claim-result:{repo}")
    need(contract.get("authority") is False, f"claim-receipt-authority:{repo}")


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


def parse_artifact(zip_bytes: bytes, expected_path: str, repo: str) -> tuple[dict[str, Any], str]:
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
            names = [name for name in archive.namelist() if not name.endswith("/")]
            need(names == [expected_path], f"artifact-files:{repo}")
            raw = archive.read(expected_path)
    except zipfile.BadZipFile as exc:
        raise LiveError(f"artifact-zip:{repo}") from exc
    try:
        receipt = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LiveError(f"artifact-json:{repo}") from exc
    need(isinstance(receipt, dict), f"artifact-object:{repo}")
    return receipt, "sha256:" + hashlib.sha256(raw).hexdigest()


def snapshot_bytes(root: Path, expected: dict[str, Any]) -> bytes:
    path = root / expected["snapshotPath"]
    need(path.is_file(), f"snapshot-missing:{expected['repository']}")
    try:
        return base64.b64decode("".join(path.read_text(encoding="utf-8").split()), validate=True)
    except Exception as exc:
        raise LiveError(f"snapshot-base64:{expected['repository']}") from exc


def capture_repository(api: GitHubApi, expected: dict[str, Any], root: Path) -> dict[str, Any]:
    repo = expected["repository"]
    branch = expected["branch"]
    metadata = api.get_json(f"/repos/{repo}")
    need(metadata.get("full_name") == repo, f"repo-metadata:{repo}")
    need(metadata.get("default_branch") == branch, f"default-branch:{repo}")
    need(metadata.get("private") is False, f"repo-not-public:{repo}")
    ref = api.get_json(f"/repos/{repo}/git/ref/heads/{branch}")
    current_head = ((ref.get("object") or {}).get("sha"))
    need(isinstance(current_head, str) and SHA.fullmatch(current_head) is not None, f"current-head:{repo}")

    claim_blob = api.get_json(f"/repos/{repo}/contents/{expected['claimPath']}?{query(ref=current_head)}")
    claim_raw = decode_content(claim_blob, f"claim-content:{repo}")
    try:
        claim = json.loads(claim_raw)
    except json.JSONDecodeError as exc:
        raise LiveError(f"claim-json:{repo}") from exc
    need(isinstance(claim, dict), f"claim-object:{repo}")
    validate_claim(claim, expected)

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

    body = snapshot_bytes(root, expected)
    observed_digest = "sha256:" + hashlib.sha256(body).hexdigest()
    need(observed_digest == artifact_digest, f"snapshot-live-digest-mismatch:{repo}")
    body_source = "provider-snapshot-live-digest-matched"
    authenticated_download = False
    try:
        downloaded = api.get_bytes(f"/repos/{repo}/actions/artifacts/{artifact_id}/zip")
    except LiveError as exc:
        need("github-http:401:" in str(exc), f"artifact-download:{repo}:{exc}")
    else:
        need(downloaded == body, f"downloaded-snapshot-mismatch:{repo}")
        body_source = "live-download-and-provider-snapshot"
        authenticated_download = True

    receipt, receipt_digest = parse_artifact(body, expected["receiptPath"], repo)
    validate_receipt(receipt, expected, current_head)
    return {
        "repository": repo,
        "branch": branch,
        "currentHead": current_head,
        "claimPath": expected["claimPath"],
        "claimBlobSha": claim_blob.get("sha"),
        "claimDigest": "sha256:" + hashlib.sha256(claim_raw).hexdigest(),
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
        "artifactBodySource": body_source,
        "artifactDownloadAuthenticated": authenticated_download,
        "snapshotPath": expected["snapshotPath"],
        "receiptPath": expected["receiptPath"],
        "receiptDigest": receipt_digest,
        "receipt": receipt,
    }


def capture(rollout: dict[str, Any], api: GitHubApi, root: Path = ROOT) -> dict[str, Any]:
    rows = [capture_repository(api, expected, root) for expected in validate_rollout(rollout)]
    return {
        "kind": "governance.liveSelectedConsumerPacket.v2",
        "status": "pass",
        "repositoryCount": len(rows),
        "artifactBodiesVerified": True,
        "receiptCandidateShaBound": True,
        "allRepositoriesEnforced": False,
        "repositories": rows,
    }


class FakeApi(GitHubApi):
    def __init__(self, json_routes: dict[str, Any], byte_routes: dict[str, bytes], deny_download: bool = True) -> None:
        super().__init__(None, "https://fake.invalid")
        self.json_routes = json_routes
        self.byte_routes = byte_routes
        self.deny_download = deny_download

    def get_json(self, path: str) -> Any:
        need(path in self.json_routes, f"fake-json-missing:{path}")
        return self.json_routes[path]

    def get_bytes(self, path: str) -> bytes:
        if self.deny_download:
            raise LiveError("github-http:401:https://fake.invalid:Requires authentication")
        need(path in self.byte_routes, f"fake-bytes-missing:{path}")
        return self.byte_routes[path]


def make_zip(receipt: dict[str, Any], path: str) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(path, canonical(receipt) + "\n")
    return out.getvalue()


def fake_fixture(rollout: dict[str, Any], root: Path) -> FakeApi:
    json_routes: dict[str, Any] = {}
    byte_routes: dict[str, bytes] = {}
    for index, expected in enumerate(rollout["repositories"], 1):
        repo = expected["repository"]
        head = str(index) * 40
        claim = {
            "kind": "governance.selectedConsumerClaim.v1",
            "repository": repo,
            "role": expected["role"],
            "allRepositoriesEnforced": False,
            "decision": {"acceptedMerge": expected["decisionMerge"], "contractDigest": expected["acceptedBundleDigest"].removeprefix("sha256:")},
            "assertion": {"assertionId": expected["assertionId"], "lifecycle": expected["lifecycle"], "generatedMeaningFreeAdapter": True, "acceptedBundleDigest": expected["acceptedBundleDigest"], "sourceClosureDigest": expected["sourceClosureDigest"]},
            "receiptContract": {"candidateShaSource": "github.event.pull_request.head.sha || github.sha", "requiredResult": "pass", "authority": False},
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
        body = make_zip(receipt, expected["receiptPath"])
        snapshot = root / expected["snapshotPath"]
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_text(base64.b64encode(body).decode() + "\n", encoding="utf-8")
        run_id, artifact_id = 2000 + index, 1000 + index
        json_routes[f"/repos/{repo}"] = {"full_name": repo, "default_branch": expected["branch"], "private": False}
        json_routes[f"/repos/{repo}/git/ref/heads/{expected['branch']}"] = {"object": {"sha": head}}
        json_routes[f"/repos/{repo}/contents/{expected['claimPath']}?ref={head}"] = {"encoding": "base64", "content": base64.b64encode(canonical(claim).encode()).decode(), "sha": "blob"}
        json_routes[f"/repos/{repo}/actions/runs?branch={expected['branch']}&event=push&status=success&per_page=100"] = {"workflow_runs": [{"id": run_id, "head_sha": head, "conclusion": "success", "event": "push", "name": expected["workflowName"], "path": expected["workflowPath"]}]}
        json_routes[f"/repos/{repo}/actions/runs/{run_id}/artifacts?per_page=100"] = {"artifacts": [{"id": artifact_id, "name": expected["artifactName"], "expired": False, "digest": "sha256:" + hashlib.sha256(body).hexdigest(), "created_at": "2026-07-18T00:00:00Z"}]}
        byte_routes[f"/repos/{repo}/actions/artifacts/{artifact_id}/zip"] = body
    return FakeApi(json_routes, byte_routes)


def selftest(rollout: dict[str, Any]) -> dict[str, Any]:
    rejected = []
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        api = fake_fixture(copy.deepcopy(rollout), root)
        packet = capture(rollout, api, root)
        need(packet["repositoryCount"] == 2, "selftest-positive")
        cases: list[tuple[str, Callable[[dict[str, Any], FakeApi, Path], None], str]] = [
            ("snapshot-digest", lambda value, fake, base: (base / value["repositories"][0]["snapshotPath"]).write_text(base64.b64encode(b"bad").decode()), "snapshot-live-digest-mismatch"),
            ("receipt-sha", lambda value, fake, base: fake.json_routes[f"/repos/{value['repositories'][0]['repository']}/git/ref/heads/{value['repositories'][0]['branch']}"]["object"].update(sha="f" * 40), "live-run-missing"),
            ("missing-run", lambda value, fake, base: fake.json_routes[f"/repos/{value['repositories'][0]['repository']}/actions/runs?branch={value['repositories'][0]['branch']}&event=push&status=success&per_page=100"].update(workflow_runs=[]), "live-run-missing"),
            ("checked-in-evidence", lambda value, fake, base: value["repositories"][0].update(candidateHead="a" * 40), "checked-in-live-evidence"),
        ]
        for name, mutate, expected_code in cases:
            case_rollout = copy.deepcopy(rollout)
            case_root = root / name
            case_api = fake_fixture(case_rollout, case_root)
            mutate(case_rollout, case_api, case_root)
            try:
                capture(case_rollout, case_api, case_root)
            except LiveError as exc:
                need(expected_code in str(exc), f"wrong-finding:{name}:{exc}")
                rejected.append({"case": name, "status": "rejected", "finding": str(exc)})
            else:
                raise LiveError(f"false-green:{name}")
    return {"kind": "governance.liveSelectedConsumerPacket.selftest.v2", "status": "pass", "positiveCases": 1, "destructiveCases": len(rejected), "cases": rejected, "authority": False}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["capture", "selftest"])
    parser.add_argument("--rollout", type=Path, default=Path("governance/selected-final-ci-rollout.v1.json"))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--api-url", default=os.environ.get("GITHUB_API_URL", "https://api.github.com"))
    parser.add_argument("--token-env", default="GITHUB_TOKEN")
    args = parser.parse_args()
    rollout = read_json(args.rollout)
    try:
        report = selftest(rollout) if args.command == "selftest" else capture(rollout, GitHubApi(os.environ.get(args.token_env), args.api_url))
    except LiveError as exc:
        report = {"kind": "governance.liveSelectedConsumerPacket.v2", "status": "fail", "finding": str(exc)}
        text = canonical(report) + "\n"
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text, encoding="utf-8")
        print(text, end="")
        return 1
    text = canonical(report) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
