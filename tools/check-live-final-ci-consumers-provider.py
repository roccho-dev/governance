#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import importlib.util
import io
import json
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORE_PATH = ROOT / "tools/check-live-final-ci-consumers-core.py"
OPS_LOGICAL = "roccho-dev/ops"
OPS_PROVIDER = "roccho-org/ops"
UI_LOGICAL = "roccho-dev/ui"
PROVIDERS = {OPS_LOGICAL: OPS_PROVIDER, UI_LOGICAL: UI_LOGICAL}
CURRENT_BODY_PATHS = {
    OPS_LOGICAL: "governance/evidence/current-provider/ops/final-ci-consumer-receipt.zip.b64",
    UI_LOGICAL: "governance/evidence/current-provider/ui/final-ci-consumer-receipt.zip.b64",
}


def load_core() -> Any:
    spec = importlib.util.spec_from_file_location("live_final_ci_consumers_core", CORE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("live-consumer-core-load")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CORE = load_core()


class DiagnosticError(CORE.LiveError):
    def __init__(self, finding: str, diagnostic: dict[str, Any]) -> None:
        super().__init__(finding)
        self.diagnostic = diagnostic


def provider_aliases() -> list[dict[str, Any]]:
    return [{
        "logicalRepository": OPS_LOGICAL,
        "providerRepository": OPS_PROVIDER,
        "relation": "current-provider-for-logical-contract",
        "authority": False,
    }]


def finding_text(error: Exception) -> str:
    value = str(error)
    return value[:500]


class CurrentProviderApi(CORE.GitHubApi):
    """Read current provider state while preserving accepted logical IDs."""

    def provider_get_json(self, logical: str, suffix: str) -> Any:
        CORE.need(logical in PROVIDERS, "provider-logical:" + logical)
        return super().get_json(f"/repos/{PROVIDERS[logical]}{suffix}")

    def provider_download(self, logical: str, suffix: str) -> tuple[bytes, bool, list[dict[str, Any]]]:
        CORE.need(logical in PROVIDERS, "provider-logical:" + logical)
        path = f"/repos/{PROVIDERS[logical]}{suffix}"
        attempts: list[dict[str, Any]] = []
        if self.token:
            try:
                body = self._request(path, self.token, "application/vnd.github+json")
            except CORE.LiveError as error:
                attempts.append({"mode": "authenticated", "status": "fail", "finding": finding_text(error)})
            else:
                attempts.append({"mode": "authenticated", "status": "pass"})
                return body, True, attempts
        try:
            body = self._request(path, None, "application/vnd.github+json")
        except CORE.LiveError as error:
            attempts.append({"mode": "anonymous", "status": "fail", "finding": finding_text(error)})
            raise DiagnosticError("artifact-download:" + logical, {"downloadAttempts": attempts}) from error
        attempts.append({"mode": "anonymous", "status": "pass"})
        return body, False, attempts

    def get_json(self, path: str) -> Any:
        logical = next((repo for repo in PROVIDERS if path == f"/repos/{repo}" or path.startswith(f"/repos/{repo}/")), None)
        CORE.need(logical is not None, "provider-route:" + path)
        value = self.provider_get_json(logical, path[len(f"/repos/{logical}"):])
        if path == f"/repos/{logical}":
            CORE.need(isinstance(value, dict), "provider-metadata-object:" + logical)
            CORE.need(value.get("full_name") == PROVIDERS[logical], "provider-alias-unexpected:" + logical)
            value = copy.deepcopy(value)
            value["provider_full_name"] = value["full_name"]
            value["full_name"] = logical
        return value

    def get_bytes(self, path: str) -> bytes:
        logical = next((repo for repo in PROVIDERS if path.startswith(f"/repos/{repo}/")), None)
        CORE.need(logical is not None, "provider-byte-route:" + path)
        body, _, _ = self.provider_download(logical, path[len(f"/repos/{logical}"):])
        return body


class FakeCurrentProviderApi(CurrentProviderApi):
    def __init__(self, json_routes: dict[str, Any], byte_routes: dict[str, bytes]) -> None:
        super().__init__("fake-token", "https://fake.invalid")
        self.json_routes = json_routes
        self.byte_routes = byte_routes

    def provider_get_json(self, logical: str, suffix: str) -> Any:
        path = f"/repos/{PROVIDERS[logical]}{suffix}"
        CORE.need(path in self.json_routes, "fake-json-missing:" + path)
        return copy.deepcopy(self.json_routes[path])

    def provider_download(self, logical: str, suffix: str) -> tuple[bytes, bool, list[dict[str, Any]]]:
        path = f"/repos/{PROVIDERS[logical]}{suffix}"
        CORE.need(path in self.byte_routes, "fake-bytes-missing:" + path)
        return self.byte_routes[path], True, [{"mode": "authenticated", "status": "pass"}]


def read_snapshot(path: Path, code: str) -> bytes:
    CORE.need(path.is_file() and not path.is_symlink(), code + ":missing")
    try:
        return base64.b64decode("".join(path.read_text(encoding="utf-8").split()), validate=True)
    except Exception as error:
        raise CORE.LiveError(code + ":base64") from error


def receipt_raw(body: bytes, expected: dict[str, Any]) -> bytes:
    try:
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            names = [name for name in archive.namelist() if not name.endswith("/")]
            CORE.need(names == [expected["receiptPath"]], "artifact-files:" + expected["repository"])
            return archive.read(expected["receiptPath"])
    except zipfile.BadZipFile as error:
        raise CORE.LiveError("artifact-zip:" + expected["repository"]) from error


def historical_snapshot_replay(rollout: dict[str, Any], root: Path = ROOT) -> dict[str, Any]:
    rows = []
    for expected in CORE.validate_rollout(rollout):
        body = CORE.snapshot_bytes(root, expected)
        receipt, receipt_digest = CORE.parse_artifact(body, expected)
        head = receipt.get("candidateSha")
        CORE.need(isinstance(head, str) and CORE.SHA.fullmatch(head) is not None, "historical-head:" + expected["repository"])
        CORE.validate_receipt(receipt, expected, head)
        rows.append({
            "repository": expected["repository"],
            "snapshotPath": expected["snapshotPath"],
            "snapshotDigest": "sha256:" + hashlib.sha256(body).hexdigest(),
            "receiptDigest": receipt_digest,
            "historicalHead": head,
            "usedForCurrent": False,
        })
    return {
        "kind": "governance.historicalSelectedConsumerReplay.v1",
        "status": "pass",
        "current": False,
        "live": False,
        "releaseEligible": False,
        "usedForCurrent": False,
        "authority": False,
        "repositories": rows,
    }


def observe_current(api: CurrentProviderApi, expected: dict[str, Any], current_body_root: Path = ROOT) -> dict[str, Any]:
    repository, branch = expected["repository"], expected["branch"]
    diagnostic: dict[str, Any] = {
        "repository": repository,
        "providerRepository": PROVIDERS[repository],
        "branch": branch,
        "receiptParsed": False,
        "receiptCandidateShaBound": False,
    }
    try:
        metadata = api.provider_get_json(repository, "")
        CORE.need(isinstance(metadata, dict) and metadata.get("full_name") == PROVIDERS[repository], "provider-metadata:" + repository)
        CORE.need(metadata.get("default_branch") == branch and metadata.get("private") is False, "provider-branch:" + repository)
        ref = api.provider_get_json(repository, f"/git/ref/heads/{branch}")
        head = ((ref.get("object") or {}).get("sha"))
        CORE.need(isinstance(head, str) and CORE.SHA.fullmatch(head) is not None, "provider-current-head:" + repository)
        diagnostic["currentHead"] = head
        runs = api.provider_get_json(repository, f"/actions/runs?{CORE.query(branch=branch, event='push', status='success', per_page=100)}")
        candidates = [run for run in runs.get("workflow_runs", []) if (
            run.get("head_sha") == head
            and run.get("conclusion") == "success"
            and run.get("event") == "push"
            and run.get("name") == expected["workflowName"]
            and run.get("path") == expected["workflowPath"]
        )]
        CORE.need(bool(candidates), "live-run-missing:" + repository)
        run = max(candidates, key=lambda value: int(value.get("id", 0)))
        run_id = run.get("id")
        CORE.need(isinstance(run_id, int) and run_id > 0, "live-run-id:" + repository)
        diagnostic["runId"] = run_id
        diagnostic["workflowName"] = run.get("name")
        diagnostic["workflowPath"] = run.get("path")
        listed = api.provider_get_json(repository, f"/actions/runs/{run_id}/artifacts?{CORE.query(per_page=100)}")
        artifacts = [item for item in listed.get("artifacts", []) if item.get("name") == expected["artifactName"] and item.get("expired") is False]
        CORE.need(len(artifacts) == 1, "live-artifact-cardinality:" + repository)
        artifact = artifacts[0]
        artifact_id, artifact_digest = artifact.get("id"), artifact.get("digest")
        CORE.need(isinstance(artifact_id, int) and artifact_id > 0, "live-artifact-id:" + repository)
        CORE.need(isinstance(artifact_digest, str) and CORE.DIGEST.fullmatch(artifact_digest) is not None, "live-artifact-digest:" + repository)
        diagnostic.update({
            "artifactId": artifact_id,
            "artifactName": artifact.get("name"),
            "providerArtifactDigest": artifact_digest,
            "providerArtifactBytes": artifact.get("size_in_bytes"),
        })

        body_source = "actual-current-provider-download"
        authenticated = False
        acquisition_path: str | None = None
        attempts: list[dict[str, Any]] = []
        try:
            body, authenticated, attempts = api.provider_download(repository, f"/actions/artifacts/{artifact_id}/zip")
        except DiagnosticError as error:
            attempts = list(error.diagnostic.get("downloadAttempts", []))
            if not any("github-http:401:" in str(row.get("finding", "")) for row in attempts):
                error.diagnostic = {**diagnostic, **error.diagnostic}
                raise
            acquisition_path = CURRENT_BODY_PATHS[repository]
            body = read_snapshot(current_body_root / acquisition_path, "current-acquisition:" + repository)
            body_source = "current-acquisition-fallback"
        diagnostic.update({
            "downloadAttempts": attempts,
            "artifactBodySource": body_source,
            "artifactDownloadAuthenticated": authenticated,
            "currentAcquisitionPath": acquisition_path,
            "downloadArchiveBytes": len(body),
            "downloadArchiveDigest": "sha256:" + hashlib.sha256(body).hexdigest(),
        })

        receipt, receipt_digest = CORE.parse_artifact(body, expected)
        raw = receipt_raw(body, expected)
        diagnostic.update({
            "receiptParsed": True,
            "receiptBytes": len(raw),
            "receiptDigest": receipt_digest,
            "receiptCandidateSha": receipt.get("candidateSha"),
        })
        CORE.validate_receipt(receipt, expected, head)
        diagnostic["receiptCandidateShaBound"] = True
        diagnostic["providerDigestMatchesDownload"] = diagnostic["downloadArchiveDigest"] == artifact_digest
        if not diagnostic["providerDigestMatchesDownload"]:
            raise DiagnosticError("live-artifact-body-digest:" + repository, diagnostic)
        return {**diagnostic, "body": body}
    except DiagnosticError:
        raise
    except (CORE.LiveError, OSError, ValueError, KeyError, TypeError) as error:
        raise DiagnosticError(str(error), diagnostic) from error


def capture_current(rollout: dict[str, Any], api: CurrentProviderApi, historical_root: Path = ROOT, current_body_root: Path = ROOT) -> dict[str, Any]:
    observed: dict[str, dict[str, Any]] = {}
    with tempfile.TemporaryDirectory() as temporary:
        current_root = Path(temporary)
        for expected in CORE.validate_rollout(rollout):
            current = observe_current(api, expected, current_body_root)
            observed[expected["repository"]] = current
            snapshot = current_root / expected["snapshotPath"]
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            snapshot.write_text(base64.b64encode(current["body"]).decode() + "\n", encoding="utf-8")
        report = CORE.capture(rollout, api, current_root)

    for row in report["repositories"]:
        repository = row["repository"]
        actual = observed[repository]
        CORE.need(row.get("currentHead") == actual["currentHead"], "provider-current-head-substituted:" + repository)
        CORE.need(row.get("runId") == actual["runId"], "provider-current-run-substituted:" + repository)
        CORE.need(row.get("artifactId") == actual["artifactId"], "provider-current-artifact-substituted:" + repository)
        CORE.need(row.get("artifactDigest") == actual["providerArtifactDigest"], "provider-current-digest-substituted:" + repository)
        row.update({key: value for key, value in actual.items() if key != "body"})
        row["currentRefObserved"] = True
        row["currentRefSource"] = "provider-api"
        row["currentArtifactDigestObserved"] = True
        row["currentBodyDigestMatched"] = True
        row["historicalSnapshotUsedForCurrent"] = False

    report["observationMode"] = "actual-current-provider"
    report["currentProviderRefsObserved"] = True
    report["currentArtifactDigestsObserved"] = True
    report["currentBodiesProviderDigestMatched"] = True
    report["currentDownloadArchiveDigestsObserved"] = True
    report["currentReceiptDigestsObserved"] = True
    report["historicalSnapshotsUsedForCurrent"] = False
    report["providerAliases"] = provider_aliases()
    report["historicalReplay"] = historical_snapshot_replay(rollout, historical_root)
    return report


def fake_provider(rollout: dict[str, Any], root: Path) -> FakeCurrentProviderApi:
    base = CORE.fake_fixture(copy.deepcopy(rollout), root)
    json_routes: dict[str, Any] = {}
    byte_routes: dict[str, bytes] = {}
    for logical, provider in PROVIDERS.items():
        prefix = f"/repos/{logical}"
        for path, value in base.json_routes.items():
            if path == prefix or path.startswith(prefix + "/"):
                physical = f"/repos/{provider}" + path[len(prefix):]
                json_routes[physical] = copy.deepcopy(value)
                if physical == f"/repos/{provider}":
                    json_routes[physical]["full_name"] = provider
    for expected in CORE.validate_rollout(rollout):
        provider = PROVIDERS[expected["repository"]]
        body = CORE.snapshot_bytes(root, expected)
        run_route = f"/repos/{provider}/actions/runs?branch={expected['branch']}&event=push&status=success&per_page=100"
        run_id = json_routes[run_route]["workflow_runs"][0]["id"]
        artifact_route = f"/repos/{provider}/actions/runs/{run_id}/artifacts?per_page=100"
        artifact_id = json_routes[artifact_route]["artifacts"][0]["id"]
        byte_routes[f"/repos/{provider}/actions/artifacts/{artifact_id}/zip"] = body
    return FakeCurrentProviderApi(json_routes, byte_routes)


def selftest(rollout: dict[str, Any]) -> dict[str, Any]:
    core = CORE.selftest(rollout)
    rejected = []
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        current_root = root / "current"
        history_root = root / "history"
        api = fake_provider(copy.deepcopy(rollout), current_root)
        for expected in CORE.validate_rollout(rollout):
            receipt, _ = CORE.parse_artifact(CORE.snapshot_bytes(current_root, expected), expected)
            receipt["candidateSha"] = ("9" if expected["repository"] == OPS_LOGICAL else "8") * 40
            body = CORE.make_zip(receipt, expected["receiptPath"])
            path = history_root / expected["snapshotPath"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(base64.b64encode(body).decode() + "\n", encoding="utf-8")
        report = capture_current(rollout, api, history_root, current_root)
        CORE.need(report.get("currentDownloadArchiveDigestsObserved") is True, "selftest-download-digest")
        CORE.need(report.get("currentReceiptDigestsObserved") is True, "selftest-receipt-digest")
        CORE.need(report.get("historicalSnapshotsUsedForCurrent") is False, "selftest-history-boundary")
        stale = fake_provider(copy.deepcopy(rollout), root / "stale")
        stale.json_routes[f"/repos/{OPS_PROVIDER}/git/ref/heads/proposals"]["object"]["sha"] = "f" * 40
        try:
            capture_current(rollout, stale, history_root, current_root)
        except CORE.LiveError as error:
            CORE.need("live-run-missing" in str(error), "selftest-stale-finding:" + str(error))
            rejected.append({"case": "stale-current-head", "status": "rejected", "finding": str(error)})
        else:
            raise CORE.LiveError("false-green:stale-current-head")
        wrong = fake_provider(copy.deepcopy(rollout), root / "wrong-provider")
        wrong.json_routes[f"/repos/{OPS_PROVIDER}"]["full_name"] = "wrong/provider"
        try:
            capture_current(rollout, wrong, history_root, current_root)
        except CORE.LiveError as error:
            CORE.need("provider-metadata" in str(error), "selftest-provider-finding:" + str(error))
            rejected.append({"case": "wrong-provider", "status": "rejected", "finding": str(error)})
        else:
            raise CORE.LiveError("false-green:wrong-provider")
    return {
        "kind": "governance.currentProviderSelectedConsumer.selftest.v3",
        "status": "pass",
        "core": core,
        "positiveCases": 1,
        "destructiveCases": len(rejected),
        "cases": rejected,
        "historicalReplayReleaseEligible": False,
        "authority": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["capture", "selftest", "replay-history"])
    parser.add_argument("--rollout", type=Path, default=Path("governance/selected-final-ci-rollout.v1.json"))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--api-url", default=os.environ.get("GITHUB_API_URL", "https://api.github.com"))
    parser.add_argument("--token-env", default="GITHUB_TOKEN")
    args = parser.parse_args()
    rollout = CORE.read_json(args.rollout)
    try:
        if args.command == "selftest":
            report = selftest(rollout)
        elif args.command == "replay-history":
            report = historical_snapshot_replay(rollout, ROOT)
        else:
            token = os.environ.get(args.token_env, "")
            CORE.need(bool(token), "provider-token-missing")
            report = capture_current(rollout, CurrentProviderApi(token, args.api_url), ROOT, ROOT)
    except (CORE.LiveError, OSError, ValueError, KeyError, TypeError) as error:
        report = {
            "kind": "governance.liveSelectedConsumerPacket.v1" if args.command == "capture" else "governance.currentProviderSelectedConsumer.selftest.v3",
            "status": "fail",
            "finding": str(error),
            "observationMode": "actual-current-provider",
            "historicalSnapshotsUsedForCurrent": False,
            "providerAliases": provider_aliases(),
        }
        if isinstance(error, DiagnosticError):
            report["diagnostics"] = [error.diagnostic]
        text = CORE.canonical(report) + "\n"
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text, encoding="utf-8")
        print(text, end="")
        return 1
    text = CORE.canonical(report) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
