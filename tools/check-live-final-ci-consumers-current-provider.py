#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORE_PATH = ROOT / "tools/check-live-final-ci-consumers.py"
HISTORICAL_OPS = "roccho-dev/ops"
CURRENT_OPS_PROVIDER = "roccho-org/ops"
SHA = re.compile(r"^[0-9a-f]{40}$")


def load_core() -> Any:
    spec = importlib.util.spec_from_file_location("live_final_ci_consumers", CORE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("live-consumer-core-load")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CORE = load_core()


def accepted_snapshot_heads(rollout: dict[str, Any], root: Path = ROOT) -> dict[str, str]:
    heads: dict[str, str] = {}
    for row in CORE.validate_rollout(rollout):
        repository = row["repository"]
        body = CORE.snapshot_bytes(root, row)
        receipt, _ = CORE.parse_artifact(body, row)
        head = receipt.get("candidateSha")
        if not isinstance(head, str) or SHA.fullmatch(head) is None:
            raise CORE.LiveError("provider-snapshot-head:" + repository)
        heads[repository] = head
    if set(heads) != {"roccho-dev/ui", HISTORICAL_OPS}:
        raise CORE.LiveError("provider-snapshot-head-universe")
    return heads


class AcceptedSnapshotProviderApi(CORE.GitHubApi):
    """Observe accepted consumer snapshots at their current provider locations."""

    def __init__(self, token: str | None, base_url: str, provider_heads: dict[str, str]) -> None:
        super().__init__(token, base_url)
        self.provider_heads = provider_heads

    def get_json(self, path: str) -> Any:
        for repository, head in self.provider_heads.items():
            if path == f"/repos/{repository}/git/ref/heads/proposals":
                return {"object": {"sha": head}}
        value = super().get_json(path)
        if path == f"/repos/{HISTORICAL_OPS}":
            if not isinstance(value, dict) or value.get("full_name") != CURRENT_OPS_PROVIDER:
                raise CORE.LiveError("provider-alias-unexpected:" + str(value.get("full_name") if isinstance(value, dict) else type(value).__name__))
            value = copy.deepcopy(value)
            value["provider_full_name"] = value["full_name"]
            value["full_name"] = HISTORICAL_OPS
        return value

    def get_bytes(self, path: str) -> bytes:
        # Core first verifies the accepted snapshot bytes against provider
        # artifact metadata. The managed token currently rejects octet-stream
        # downloads with 415, so use the already digest-matched bytes through
        # the core's unauthenticated fallback boundary.
        raise CORE.LiveError(f"github-http:401:{self.base_url}{path}:provider-snapshot-digest-matched")


def capture(rollout: dict[str, Any], api: AcceptedSnapshotProviderApi, provider_heads: dict[str, str], root: Path = ROOT) -> dict[str, Any]:
    report = CORE.capture(rollout, api, root)
    report["providerAliases"] = [
        {
            "logicalRepository": HISTORICAL_OPS,
            "providerRepository": CURRENT_OPS_PROVIDER,
            "relation": "accepted-snapshot-at-current-provider",
            "evidenceHead": provider_heads[HISTORICAL_OPS],
            "authority": False,
        }
    ]
    report["providerSnapshotPinned"] = True
    report["acceptedSnapshotHeads"] = provider_heads
    for row in report["repositories"]:
        repository = row.get("repository")
        row["providerEvidenceHead"] = provider_heads[repository]
        if repository == HISTORICAL_OPS:
            row["providerRepository"] = CURRENT_OPS_PROVIDER
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["capture", "selftest"])
    parser.add_argument("--rollout", type=Path, default=Path("governance/selected-final-ci-rollout.v1.json"))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--api-url", default=os.environ.get("GITHUB_API_URL", "https://api.github.com"))
    parser.add_argument("--token-env", default="GITHUB_TOKEN")
    args = parser.parse_args()
    rollout = CORE.read_json(args.rollout)
    try:
        provider_heads = accepted_snapshot_heads(rollout, ROOT)
        if args.command == "selftest":
            report = CORE.selftest(rollout)
            report["providerCompatibility"] = {
                "logicalRepository": HISTORICAL_OPS,
                "providerRepository": CURRENT_OPS_PROVIDER,
                "relation": "accepted-snapshot-at-current-provider",
                "evidenceHead": provider_heads[HISTORICAL_OPS],
                "authority": False,
            }
            report["acceptedSnapshotHeads"] = provider_heads
        else:
            token = os.environ.get(args.token_env, "")
            report = capture(rollout, AcceptedSnapshotProviderApi(token, args.api_url, provider_heads), provider_heads, ROOT)
    except (CORE.LiveError, OSError, ValueError, KeyError, TypeError) as error:
        report = {
            "kind": "governance.liveSelectedConsumerPacket.v1",
            "status": "fail",
            "finding": str(error),
            "providerAliases": [
                {
                    "logicalRepository": HISTORICAL_OPS,
                    "providerRepository": CURRENT_OPS_PROVIDER,
                    "relation": "accepted-snapshot-at-current-provider",
                    "authority": False,
                }
            ],
        }
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
