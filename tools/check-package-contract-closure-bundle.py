#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import contract_632_phase4_acquire as _acquire  # noqa: E402
from tools import contract_632_source3 as _source3  # noqa: E402
from tools import package_contract_port_cli as _cli  # noqa: E402
from tools import package_contract_port_common as _common  # noqa: E402
from tools import package_contract_port_verify as _verify  # noqa: E402
from tools.package_contract_port_common import *  # noqa: F401,F403,E402

TARGET_DIR = _common.TARGET_DIR
_BASE_VERIFY_EVIDENCE = _common.verify_evidence_input
_ORIGINAL_PRODUCE = _cli.produce_bundle
_ORIGINAL_PREFLIGHT = _cli.cross_target_preflight
_ORIGINAL_VERIFY = _verify.verify_bundle
_RAW_APPS_BINDING = _source3.apps_preflight_binding


def apps_preflight_binding() -> dict[str, Any]:
    """Pins from caller-owned release; argv-shaped provenance keeps run values as strings."""
    binding = _RAW_APPS_BINDING()
    provider = binding["evidenceMaterial"]["provider"]
    provider["runId"] = str(provider["runId"])
    provider["runAttempt"] = str(provider["runAttempt"])
    return binding


_source3.apps_preflight_binding = apps_preflight_binding


def load_target(target_id):
    _common.TARGET_DIR = TARGET_DIR
    return _common.load_target(target_id)


def discover_targets():
    _common.TARGET_DIR = TARGET_DIR
    return _common.discover_targets()


def _closed(target_source: Path):
    def verify(root, binding, target_id, candidate):
        effective = binding
        executor = binding.get("evidenceExecutor", {})
        if executor.get("kind") == "exact-existing-release" and "evidenceMaterial" not in binding:
            expected = apps_preflight_binding()
            need(target_id == expected["targetId"], "preflight-binding-target")
            need(candidate == expected["targetSource"]["revision"], "preflight-binding-candidate")
            need(binding.get("targetSource", {}).get("revision") == candidate, "preflight-binding-source")
            need(executor == expected["evidenceExecutor"], "preflight-binding-executor")
            effective = expected
        return _source3.verify_closed_evidence_input(
            _BASE_VERIFY_EVIDENCE,
            root,
            effective,
            target_id,
            candidate,
            target_source,
        )

    return verify


def verify_bundle(
    bundle: Path,
    target_source: Path,
    target_candidate: str,
    accepted_requirement_source: Path,
    target_id: str = "ops",
    governance_candidate: str | None = None,
    governance_policy_source: Path | None = None,
    contract_runtime_source: Path | None = None,
    evidence_input: Path | None = None,
):
    previous = _verify.verify_evidence_input
    _verify.verify_evidence_input = _closed(target_source)
    try:
        return _ORIGINAL_VERIFY(
            bundle,
            target_source,
            target_candidate,
            accepted_requirement_source,
            target_id,
            governance_candidate,
            governance_policy_source,
            contract_runtime_source,
            evidence_input,
        )
    finally:
        _verify.verify_evidence_input = previous


def produce_bundle(
    *,
    target_id: str,
    bundle: Path,
    target_source: Path,
    accepted_requirement_source: Path,
    governance_policy_source: Path,
    governance_candidate: str,
    contract_runtime_source: Path | None = None,
    evidence_input: Path | None = None,
):
    if evidence_input is None:
        raise ValueError("package-contract-bundle:evidence-input-root")
    _, binding, _ = load_target(target_id)
    _source3.prepare_target_evidence(_acquire, target_id, binding, target_source, evidence_input)
    previous = _cli.verify_evidence_input
    _cli.verify_evidence_input = _closed(target_source)
    try:
        return _ORIGINAL_PRODUCE(
            target_id=target_id,
            bundle=bundle,
            target_source=target_source,
            accepted_requirement_source=accepted_requirement_source,
            governance_policy_source=governance_policy_source,
            governance_candidate=governance_candidate,
            contract_runtime_source=contract_runtime_source,
            evidence_input=evidence_input,
        )
    finally:
        _cli.verify_evidence_input = previous


def cross_target_preflight(
    target_source: Path,
    runtime_source: Path,
    accepted_source: Path,
    evidence_input: Path,
):
    binding = apps_preflight_binding()
    _source3.prepare_target_evidence(
        _acquire,
        binding["targetId"],
        binding,
        target_source,
        evidence_input,
    )
    previous = _cli.verify_evidence_input
    _cli.verify_evidence_input = _closed(target_source)
    try:
        report = _ORIGINAL_PREFLIGHT(target_source, runtime_source, accepted_source, evidence_input)
    finally:
        _cli.verify_evidence_input = previous
    negatives = _source3.verify_exact_release_negatives(
        _BASE_VERIFY_EVIDENCE,
        binding,
        target_source,
        evidence_input,
    )
    return {
        **report,
        "evidenceMaterialClosed": True,
        "genericEvidencePreparation": True,
        "manifestFilesVerified": binding["evidenceMaterial"]["manifest"]["fileCount"],
        **negatives,
    }


_cli.verify_bundle = verify_bundle
_cli.produce_bundle = produce_bundle
_cli.cross_target_preflight = cross_target_preflight
main = _cli.main


if __name__ == "__main__":
    raise SystemExit(main())
