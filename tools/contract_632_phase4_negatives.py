#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def refresh_manifest(root: Path, relative: str):
    path = root / "bundle-manifest.json"
    rows = json.loads(path.read_text())
    for row in rows:
        if row["path"] == relative:
            row["sha256"] = "sha256:" + hashlib.sha256((root / relative).read_bytes()).hexdigest()
    path.write_text(canonical(rows) + "\n")


def main():
    parser = argparse.ArgumentParser()
    for name in ("bundle", "sources", "evidence", "governance", "b0", "out"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("checker", ROOT / "tools/check-package-contract-closure-bundle.py")
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    final_spec = importlib.util.spec_from_file_location("final", ROOT / "tools/check-package-final-scope-purpose-join.py")
    final = importlib.util.module_from_spec(final_spec)
    final_spec.loader.exec_module(final)
    sources = Path(args.sources)
    evidence = Path(args.evidence)
    target = sources / "ops/targetSource"
    accepted = sources / "ops/acceptedRequirementSource"
    policy = sources / "ops/governancePolicySource"
    runtime = sources / "ops/contractRuntimeSource"
    target_evidence = evidence / "ops"
    base = Path(args.bundle)

    def verify(folder: Path, governance=args.governance, evidence_root=target_evidence):
        return checker.verify_bundle(
            folder,
            target,
            "5eb98c82417b399978c1e38aebab5e3fb39752d4",
            accepted,
            "ops",
            governance,
            policy,
            runtime,
            evidence_root,
        )

    rejected = {}
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        fake = root / "fake"
        fake.mkdir()
        shutil.copy2(base / "run-scope.json", fake / "run-scope.json")
        shutil.copy2(base / "phase4-evidence.json", fake / "phase4-evidence.json")
        cases = [("fabricatedDigestOnly", fake, None)]

        accepted_bad = root / "accepted"
        shutil.copytree(base, accepted_bad)
        rel = "sources/governance/selected-final-ci-rollout.v1.json"
        (accepted_bad / rel).write_bytes((accepted_bad / rel).read_bytes() + b"\n")
        refresh_manifest(accepted_bad, rel)
        cases.append(("acceptedSourceTamper", accepted_bad, None))

        runtime_bad = root / "runtime"
        shutil.copytree(base, runtime_bad)
        bindings = json.loads((runtime_bad / "source-bindings.json").read_text())
        rel = bindings["comparatorCore"]["bundlePath"]
        (runtime_bad / rel).write_bytes((runtime_bad / rel).read_bytes() + b"\n")
        refresh_manifest(runtime_bad, rel)
        cases.append(("runtimeSourceTamper", runtime_bad, None))

        extra = root / "extra"
        shutil.copytree(base, extra)
        path = extra / "source-bindings.json"
        value = json.loads(path.read_text())
        value["unexpectedRole"] = value["providerClaim"]
        path.write_text(canonical(value) + "\n")
        refresh_manifest(extra, "source-bindings.json")
        cases.append(("extraSourceRole", extra, None))
        cases.append(("wrongGovernanceCandidate", base, "0" * 40))

        missing_evidence = root / "missing-evidence"
        missing_evidence.mkdir()
        evidence_cases = [("missingEvidenceInput", missing_evidence)]
        wrong_evidence = root / "wrong-evidence"
        shutil.copytree(target_evidence, wrong_evidence)
        evidence_path = wrong_evidence / "evidence.json"
        evidence_value = json.loads(evidence_path.read_text())
        evidence_value["candidate"] = "0" * 40
        evidence_path.write_text(canonical(evidence_value) + "\n")
        evidence_cases.append(("wrongEvidenceCandidate", wrong_evidence))
        wrong_operation = root / "wrong-operation"
        shutil.copytree(target_evidence, wrong_operation)
        evidence_path = wrong_operation / "evidence.json"
        evidence_value = json.loads(evidence_path.read_text())
        evidence_value["executor"]["operation"] = "wrong-operation"
        evidence_path.write_text(canonical(evidence_value) + "\n")
        evidence_cases.append(("wrongEvidenceOperation", wrong_operation))

        for name, folder, governance in cases:
            try:
                verify(folder, governance or args.governance)
            except (ValueError, FileNotFoundError, json.JSONDecodeError):
                rejected[name] = True
            else:
                raise SystemExit(name + " unexpectedly passed")
        for name, evidence_root in evidence_cases:
            try:
                verify(base, evidence_root=evidence_root)
            except (ValueError, FileNotFoundError, json.JSONDecodeError):
                rejected[name] = True
            else:
                raise SystemExit(name + " unexpectedly passed")

    try:
        checker.validate_provider_relation(
            {
                "logicalRepository": "logical/repo",
                "providerRepository": "provider/repo",
                "targetSource": {"repository": "wrong/repo"},
            }
        )
    except ValueError:
        rejected["unrelatedProviderRelation"] = True
    else:
        raise SystemExit("provider relation unexpectedly passed")

    original_dir = checker.TARGET_DIR
    with tempfile.TemporaryDirectory(dir=ROOT) as temp:
        folder = Path(temp)
        source = (ROOT / "tools/package_contract_targets/ops.py").read_text().replace(
            "EXPECTED_NEGATIVE = {", "EXPECTED_NEGATIVE = {}\nDISABLED_NEGATIVE = {"
        )
        binding = json.loads((ROOT / "tools/package_contract_targets/ops.target.json").read_text())
        binding["adapterPath"] = (folder / "ops.py").relative_to(ROOT).as_posix()
        (folder / "ops.py").write_text(source)
        (folder / "ops.target.json").write_text(canonical(binding) + "\n")
        checker.TARGET_DIR = folder
        try:
            checker.load_target("ops")
        except ValueError as error:
            if "adapter-negative-contract" not in str(error):
                raise
            rejected["weakenedNegativeContract"] = True
        else:
            raise SystemExit("weakened negative contract unexpectedly passed")
        finally:
            checker.TARGET_DIR = original_dir

    legacy = json.loads((Path(args.b0) / "package-contract-member.json").read_text())
    _, binding, _ = checker.load_target("ops")
    try:
        final.validate_member(
            legacy,
            binding,
            "ops",
            "5eb98c82417b399978c1e38aebab5e3fb39752d4",
            args.governance,
            checker,
        )
    except ValueError as error:
        if "member-kind" not in str(error):
            raise
        rejected["legacyMemberV2"] = True
    else:
        raise SystemExit("legacy member unexpectedly passed")

    report = {
        "kind": "governance.contract632.phase4FinalEntranceNegative.v6",
        "status": "pass",
        "authority": False,
        **rejected,
    }
    Path(args.out).write_text(canonical(report) + "\n")


if __name__ == "__main__":
    main()
