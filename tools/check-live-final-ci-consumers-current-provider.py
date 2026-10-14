#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORE_PATH = ROOT / "tools/check-live-final-ci-consumers.py"
HISTORICAL_OPS = "roccho-dev/ops"
CURRENT_OPS_PROVIDER = "roccho-org/ops"


def load_core() -> Any:
    spec = importlib.util.spec_from_file_location("live_final_ci_consumers", CORE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("live-consumer-core-load")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CORE = load_core()


class CurrentProviderApi(CORE.GitHubApi):
    """Keep the accepted logical repository ID while observing its current provider location."""

    def get_json(self, path: str) -> Any:
        value = super().get_json(path)
        if path == f"/repos/{HISTORICAL_OPS}":
            if not isinstance(value, dict) or value.get("full_name") != CURRENT_OPS_PROVIDER:
                raise CORE.LiveError("provider-alias-unexpected:" + str(value.get("full_name") if isinstance(value, dict) else type(value).__name__))
            value = copy.deepcopy(value)
            value["provider_full_name"] = value["full_name"]
            value["full_name"] = HISTORICAL_OPS
        return value


def capture(rollout: dict[str, Any], api: CurrentProviderApi, root: Path = ROOT) -> dict[str, Any]:
    report = CORE.capture(rollout, api, root)
    report["providerAliases"] = [
        {
            "logicalRepository": HISTORICAL_OPS,
            "providerRepository": CURRENT_OPS_PROVIDER,
            "relation": "current-provider-of-historical-logical-id",
            "authority": False,
        }
    ]
    for row in report["repositories"]:
        if row.get("repository") == HISTORICAL_OPS:
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
        if args.command == "selftest":
            report = CORE.selftest(rollout)
            report["providerCompatibility"] = {
                "logicalRepository": HISTORICAL_OPS,
                "providerRepository": CURRENT_OPS_PROVIDER,
                "authority": False,
            }
        else:
            token = os.environ.get(args.token_env, "")
            report = capture(rollout, CurrentProviderApi(token, args.api_url), ROOT)
    except (CORE.LiveError, OSError, ValueError, KeyError, TypeError) as error:
        report = {
            "kind": "governance.liveSelectedConsumerPacket.v1",
            "status": "fail",
            "finding": str(error),
            "providerAliases": [
                {
                    "logicalRepository": HISTORICAL_OPS,
                    "providerRepository": CURRENT_OPS_PROVIDER,
                    "relation": "current-provider-of-historical-logical-id",
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
