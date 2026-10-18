#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
from pathlib import Path
import runpy
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.contract_632_topology_view import canonical_final_topology

PROVIDERS = {
    "roccho-dev/ops": "roccho-org/ops",
    "roccho-dev/ui": "roccho-dev/ui",
}
BODY_SOURCES = {
    "actual-current-provider-download",
    "current-acquisition-provider-digest-matched",
}


def need(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError("current-live-packet:" + code)


def validate_current_live_packet(value: dict[str, Any]) -> None:
    need(value.get("kind") == "governance.liveSelectedConsumerPacket.v1", "kind")
    need(value.get("status") == "pass", "status")
    need(value.get("observationMode") == "actual-current-provider", "observation-mode")
    need(value.get("currentProviderRefsObserved") is True, "current-ref-observation")
    need(value.get("currentArtifactDigestsObserved") is True, "current-artifact-digest")
    need(value.get("currentBodiesProviderDigestMatched") is True, "current-body-digest")
    need(value.get("historicalSnapshotsUsedForCurrent") is False, "historical-substitution")
    aliases = value.get("providerAliases")
    need(isinstance(aliases, list) and aliases == [{
        "logicalRepository": "roccho-dev/ops",
        "providerRepository": "roccho-org/ops",
        "relation": "current-provider-for-logical-contract",
        "authority": False,
    }], "provider-alias")
    history = value.get("historicalReplay")
    need(isinstance(history, dict), "historical-replay")
    need(history.get("kind") == "governance.historicalSelectedConsumerReplay.v1", "historical-kind")
    need(history.get("status") == "pass", "historical-status")
    need(history.get("current") is False and history.get("live") is False, "historical-not-live")
    need(history.get("releaseEligible") is False and history.get("usedForCurrent") is False, "historical-ceiling")
    rows = value.get("repositories")
    need(isinstance(rows, list) and len(rows) == len(PROVIDERS), "repository-cardinality")
    by_repository = {row.get("repository"): row for row in rows if isinstance(row, dict)}
    need(set(by_repository) == set(PROVIDERS), "repository-universe")
    historical_rows = history.get("repositories")
    need(isinstance(historical_rows, list) and {row.get("repository") for row in historical_rows if isinstance(row, dict)} == set(PROVIDERS), "historical-universe")
    for repository, provider in PROVIDERS.items():
        row = by_repository[repository]
        need(row.get("providerRepository") == provider, "provider:" + repository)
        need(row.get("currentRefObserved") is True and row.get("currentRefSource") == "provider-api", "current-ref:" + repository)
        need(row.get("currentArtifactDigestObserved") is True, "current-artifact-digest:" + repository)
        need(row.get("currentBodyDigestMatched") is True, "current-body-digest:" + repository)
        source = row.get("artifactBodySource")
        need(source in BODY_SOURCES, "artifact-source:" + repository)
        if source == "actual-current-provider-download":
            need(row.get("artifactDownloadAuthenticated") is True, "artifact-auth:" + repository)
            need(row.get("currentAcquisitionPath") is None, "download-acquisition-path:" + repository)
        else:
            need(row.get("artifactDownloadAuthenticated") is False, "acquisition-auth:" + repository)
            need(isinstance(row.get("currentAcquisitionPath"), str) and bool(row["currentAcquisitionPath"]), "acquisition-path:" + repository)
        need(row.get("historicalSnapshotUsedForCurrent") is False, "row-historical-substitution:" + repository)


def validate_live_argument(argv: list[str]) -> None:
    if not argv or argv[0] != "check":
        return
    need("--live-consumers" in argv, "live-argument")
    index = argv.index("--live-consumers")
    need(index + 1 < len(argv), "live-argument-value")
    path = Path(argv[index + 1])
    need(path.is_file(), "live-file")
    value = json.loads(path.read_text(encoding="utf-8"))
    need(isinstance(value, dict), "live-object")
    validate_current_live_packet(value)


def selftest_current_live_packet() -> None:
    rows = []
    history_rows = []
    for index, (repository, provider) in enumerate(PROVIDERS.items(), 1):
        rows.append({
            "repository": repository,
            "providerRepository": provider,
            "currentRefObserved": True,
            "currentRefSource": "provider-api",
            "currentArtifactDigestObserved": True,
            "currentBodyDigestMatched": True,
            "artifactBodySource": "current-acquisition-provider-digest-matched",
            "artifactDownloadAuthenticated": False,
            "currentAcquisitionPath": f"current/{index}.zip.b64",
            "historicalSnapshotUsedForCurrent": False,
        })
        history_rows.append({"repository": repository, "historicalHead": str(index) * 40, "usedForCurrent": False})
    packet = {
        "kind": "governance.liveSelectedConsumerPacket.v1",
        "status": "pass",
        "observationMode": "actual-current-provider",
        "currentProviderRefsObserved": True,
        "currentArtifactDigestsObserved": True,
        "currentBodiesProviderDigestMatched": True,
        "historicalSnapshotsUsedForCurrent": False,
        "providerAliases": [{
            "logicalRepository": "roccho-dev/ops",
            "providerRepository": "roccho-org/ops",
            "relation": "current-provider-for-logical-contract",
            "authority": False,
        }],
        "historicalReplay": {
            "kind": "governance.historicalSelectedConsumerReplay.v1",
            "status": "pass",
            "current": False,
            "live": False,
            "releaseEligible": False,
            "usedForCurrent": False,
            "repositories": history_rows,
        },
        "repositories": rows,
    }
    validate_current_live_packet(packet)
    cases = [
        ("historical-substitution", lambda value: value.update(historicalSnapshotsUsedForCurrent=True)),
        ("wrong-provider", lambda value: value["repositories"][0].update(providerRepository="wrong/provider")),
        ("missing-current-ref", lambda value: value["repositories"][0].update(currentRefObserved=False)),
        ("missing-artifact-digest", lambda value: value["repositories"][0].update(currentArtifactDigestObserved=False)),
        ("body-digest-mismatch", lambda value: value["repositories"][0].update(currentBodyDigestMatched=False)),
        ("historical-release", lambda value: value["historicalReplay"].update(releaseEligible=True)),
    ]
    for name, mutate in cases:
        candidate = copy.deepcopy(packet)
        mutate(candidate)
        try:
            validate_current_live_packet(candidate)
        except ValueError:
            continue
        raise ValueError("current-live-packet:false-green:" + name)


argv = sys.argv[1:]
if argv and argv[0] == "selftest":
    selftest_current_live_packet()
else:
    validate_live_argument(argv)

with canonical_final_topology(ROOT):
    runpy.run_path(str(Path(__file__).with_name("check-package-final-ci-production-core.py")), run_name="__main__")
