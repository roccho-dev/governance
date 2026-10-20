#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.machinery
import importlib.util
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any

_IMPL_RELATIVE = "tools/package_contract_target_impls/logger.py"
_IMPL_PATH = Path(__file__).resolve().parents[1] / "package_contract_target_impls" / "logger.py"
_IMPL_SHA256 = "sha256:e44a269b5db0385c2510990782f1d71925a6fb19b38e2072117b605c09c78ff1"
_BUNDLE_IMPL = "sources/observer/logger-implementation.py"
_EXTRA_SOURCE_PATHS = {
    "retainedSupplement": "packages/shiftleft-admission/tests/fixtures/logger-language-neutral-establishment/retained-k-supplement.json",
    "baselineMetadata": "packages/shiftleft-admission/tests/fixtures/logger-language-neutral-establishment/baseline-metadata.json",
    "baselineSha256sums": "packages/shiftleft-admission/tests/fixtures/logger-language-neutral-establishment/baseline-SHA256SUMS",
    "materialityDecisionOriginal": "packages/shiftleft-admission/tests/fixtures/logger-language-neutral-establishment/r-v18-comment.md",
    "aggregateRejectionOriginal": "packages/shiftleft-admission/tests/fixtures/logger-language-neutral-establishment/r-v31-comment.md",
    "admissionSourceDecisionOriginal": "packages/shiftleft-admission/tests/fixtures/logger-language-neutral-establishment/r-v21-comment.md",
    "canonicalEffectDecisionOriginal": "packages/shiftleft-admission/tests/fixtures/logger-language-neutral-establishment/r-v22-comment.md",
}
_BASELINE_METADATA = {
    "bytes": 750,
    "sha256": "sha256:8473407a8012c283cc0ec2dfef0943ffe644500941c5a1196db9d311ce8ca2a5",
    "gitBlob": "d32216934b4a028a9555db658404319bb3c0dacd",
}
_BASELINE_SUMS = {
    "bytes": 1056,
    "sha256": "sha256:cd4d1676120b548bd45cad043384d64a446b38b90fdc02f366b94e684ad2d8e3",
    "gitBlob": "49310c60fa4155b9df62ebb1a2bf3d098158add5",
}
_FINDING_SHA256 = "sha256:1ecdcc85fc40c84c86ae270d59725ce579b0c555f1d33247b19cfab13981f10f"
_CAUSAL_ORDER = [
    "materiality",
    "aggregate-rejection",
    "technical-closure",
    "admission-source-acceptance",
    "canonical-effect-readback",
]
_DECISIONS = [
    {
        "role": "materiality",
        "dependsOn": [],
        "repository": "roccho-dev/adrs",
        "pullRequest": 655,
        "commentId": 6280208952,
        "sourceUrl": "https://github.com/roccho-dev/adrs/pull/655#issuecomment-6280208952",
        "path": "r-v18-comment.md",
        "bytes": 12310,
        "sha256": "sha256:8aa3a47a51d620f1da205899c20bf90c13aaaa18371776d1f9bb37cfd4e9bd7c",
        "gitBlob": "64c687c69a48a8caf9d049949b0c23b275e3bd40",
        "sourceRole": "materialityDecisionOriginal",
    },
    {
        "role": "aggregate-rejection",
        "dependsOn": [6280208952],
        "repository": "roccho-org/ops",
        "pullRequest": 602,
        "commentId": 6283074344,
        "sourceUrl": "https://github.com/roccho-org/ops/pull/602#issuecomment-6283074344",
        "path": "r-v31-comment.md",
        "bytes": 9677,
        "sha256": "sha256:ffff0bfabf79751d24aa3f3278ca3c3449770561ef646f36da5933fb8e9da2e7",
        "gitBlob": "0943e6f8ce2a02b8cf8938f4aa08d285ee8d3030",
        "sourceRole": "aggregateRejectionOriginal",
    },
    {
        "role": "technical-closure",
        "dependsOn": [6283074344],
        "repository": "roccho-org/ops",
        "pullRequest": 602,
        "commentId": 6283358664,
        "sourceUrl": "https://github.com/roccho-org/ops/pull/602#issuecomment-6283358664",
        "path": "r-v32-comment.md",
        "bytes": 9488,
        "sha256": "sha256:56945f7657ae16089fa299dead5dfbd50b462196fc3976cb2c6b056cf71021f4",
        "gitBlob": "a039df34b8dec20910cb37c3a7e146e63f5daf28",
        "sourceRole": "independentJudgmentOriginal",
    },
    {
        "role": "admission-source-acceptance",
        "dependsOn": [6283358664],
        "repository": "roccho-dev/adrs",
        "pullRequest": 655,
        "commentId": 6283469134,
        "sourceUrl": "https://github.com/roccho-dev/adrs/pull/655#issuecomment-6283469134",
        "path": "r-v21-comment.md",
        "bytes": 6278,
        "sha256": "sha256:96fee828b78bf30dfbcaa4fe038420b961a39428c11bf5e59ceaac0dc9566444",
        "gitBlob": "aa54a7cba2219fc8ffc674634be38e43dfa1fb27",
        "sourceRole": "admissionSourceDecisionOriginal",
    },
    {
        "role": "canonical-effect-readback",
        "dependsOn": [6283469134],
        "repository": "roccho-dev/adrs",
        "pullRequest": 655,
        "commentId": 6283505423,
        "sourceUrl": "https://github.com/roccho-dev/adrs/pull/655#issuecomment-6283505423",
        "path": "r-v22-comment.md",
        "bytes": 7832,
        "sha256": "sha256:3030ec6da48109a31eed1d47806eb536940ab802c7039e8195829ab2fa80baad",
        "gitBlob": "ac95bcda4009bb5898512b0bd038b4b7b285c5b7",
        "sourceRole": "canonicalEffectDecisionOriginal",
    },
]


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _git_blob(path: Path) -> str:
    raw = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_canonical(value) + "\n", encoding="utf-8")


def _load_impl():
    if not _IMPL_PATH.is_file() or _sha256(_IMPL_PATH) != _IMPL_SHA256:
        raise ValueError("logger-adapter:implementation-identity")
    loader = importlib.machinery.SourceFileLoader("_logger_contract_target_impl", str(_IMPL_PATH))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None:
        raise ValueError("logger-adapter:implementation-spec")
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


_impl = _load_impl()
for _name in dir(_impl):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_impl, _name)

_impl.SOURCE_PATHS.update(_EXTRA_SOURCE_PATHS)
SOURCE_PATHS = _impl.SOURCE_PATHS


def _strict_checks(raw: bytes) -> dict[str, str]:
    output: dict[str, str] = {}
    for line in raw.decode("utf-8").splitlines():
        _impl._need(
            len(line) > 68 and line[64:68] == "  ./",
            "k-checksum-row",
            line[:80],
        )
        digest, name = line[:64], line[68:]
        _impl._safe(name)
        _impl._need(
            len(digest) == 64
            and all(character in "0123456789abcdef" for character in digest)
            and name not in output,
            "k-checksum",
        )
        output[name] = "sha256:" + digest
    return output


# The retained producer emitted ordinary `sha256sum` rows (`<64hex>  ./path`).
# Keep the old implementation byte-identical and correct only its four-byte separator
# interpretation at the source-bound W adapter.
_impl._checks = _strict_checks

_BASE_PRODUCE = _impl.produce
_BASE_EXPECTED_EVIDENCE = _impl.expected_evidence
_BASE_VERIFY_K = _impl._verify_k


def _source_path(root: Path, role: str) -> Path:
    return root / Path(SOURCE_PATHS[role]).name


def _verify_file(path: Path, expected: dict[str, Any], code: str) -> None:
    _impl._need(path.is_file() and not path.is_symlink(), code + "-missing")
    _impl._need(path.stat().st_size == expected["bytes"], code + "-bytes")
    _impl._need(_sha256(path) == expected["sha256"], code + "-sha256")
    _impl._need(_git_blob(path) == expected["gitBlob"], code + "-git-blob")


def _verify_retained_completion(
    manifest_path: Path,
    artifact_path: Path,
    judgment_path: Path,
    original_path: Path,
) -> dict[str, Any]:
    base = _BASE_VERIFY_K(manifest_path, artifact_path, judgment_path, original_path)
    root = manifest_path.parent
    supplement_path = _source_path(root, "retainedSupplement")
    baseline_metadata_path = _source_path(root, "baselineMetadata")
    baseline_sums_path = _source_path(root, "baselineSha256sums")
    _impl._need(supplement_path.is_file() and not supplement_path.is_symlink(), "k-supplement-missing")
    supplement = json.loads(supplement_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _impl._need(
        supplement.get("schema") == "ops.logger-language-neutral.retained-k-supplement/2"
        and supplement.get("authority") is False,
        "k-supplement",
    )
    _impl._need(supplement.get("canonicalMeaning") == manifest.get("canonicalMeaning"), "k-supplement-meaning")

    actual = supplement.get("baselineActualOriginal", {})
    _impl._need(
        actual.get("workflowRunId") == 39246951391
        and actual.get("artifactId") == 12182908410
        and actual.get("artifactBytes") == 44926
        and actual.get("artifactSha256") == "sha256:ccd9a41adbaa4b620d49e8980860d083a4a7db1624c60119fd5015290473686f"
        and actual.get("observationHead") == "b8c9a0eb1436d1d1218621c41d39a9b5a60fc9d2"
        and actual.get("observationTree") == "cfeee63db40e42260252872f273acaf5354a1975"
        and actual.get("repairAllowed") is False,
        "k-baseline-identity",
    )
    retained = actual.get("retainedOriginals", {})
    _impl._need(retained.get("metadata") == {"path": "baseline-metadata.json", **_BASELINE_METADATA}, "k-baseline-metadata-declaration")
    _impl._need(retained.get("sha256sums") == {"path": "baseline-SHA256SUMS", **_BASELINE_SUMS}, "k-baseline-sums-declaration")
    finding = retained.get("finding", {})
    _impl._need(
        finding.get("sourcePath") == "technical-closure.zip:finding.json"
        and finding.get("bytes") == 27810
        and finding.get("sha256") == _FINDING_SHA256
        and finding.get("baselineSha256sumsEntry") == "1ecdcc85fc40c84c86ae270d59725ce579b0c555f1d33247b19cfab13981f10f  ./finding.json"
        and finding.get("correctedArchiveEntrySha256") == _FINDING_SHA256
        and finding.get("byteIdenticalAcrossBaselineAndCorrectedArchives") is True,
        "k-baseline-finding-declaration",
    )
    _verify_file(baseline_metadata_path, _BASELINE_METADATA, "k-baseline-metadata")
    _verify_file(baseline_sums_path, _BASELINE_SUMS, "k-baseline-sums")
    baseline_metadata = json.loads(baseline_metadata_path.read_text(encoding="utf-8"))
    _impl._need(
        baseline_metadata.get("schema") == "ops.logger-language-neutral.baseline-evidence/1"
        and baseline_metadata.get("authority") is False
        and baseline_metadata.get("workflowRunId") == "39246951391"
        and baseline_metadata.get("observationHead") == actual.get("observationHead")
        and baseline_metadata.get("observationTree") == actual.get("observationTree")
        and baseline_metadata.get("correctedScopeT0") == actual.get("fixedT0")
        and baseline_metadata.get("candidateMeaningSha256") == manifest.get("canonicalMeaning", {}).get("meaningSha256")
        and baseline_metadata.get("repairAllowed") is False,
        "k-baseline-metadata-body",
    )
    sums_lines = baseline_sums_path.read_text(encoding="utf-8").splitlines()
    _impl._need(finding["baselineSha256sumsEntry"] in sums_lines, "k-baseline-finding-sum")
    with zipfile.ZipFile(artifact_path) as archive:
        finding_bytes = archive.read("finding.json")
    _impl._need(len(finding_bytes) == finding["bytes"] and "sha256:" + hashlib.sha256(finding_bytes).hexdigest() == _FINDING_SHA256, "k-baseline-finding-body")

    sequence = supplement.get("independentDecisionSequence")
    _impl._need(supplement.get("causalOrder") == _CAUSAL_ORDER, "k-causal-order")
    _impl._need(isinstance(sequence, list) and len(sequence) == len(_DECISIONS), "k-decision-sequence")
    for observed, expected in zip(sequence, _DECISIONS, strict=True):
        source_role = expected["sourceRole"]
        body_path = original_path if source_role == "independentJudgmentOriginal" else _source_path(root, source_role)
        public_expected = {key: value for key, value in expected.items() if key != "sourceRole"}
        _impl._need(observed == public_expected, "k-decision-row", expected["role"])
        _verify_file(body_path, public_expected, "k-decision-" + expected["role"])

    coverage = supplement.get("coverage", {})
    expected_coverage = {
        "baselineOriginalProvenance": "COVERED",
        "fixedFiveProfileMatrix": "COVERED",
        "materialityDecisionOriginal": "COVERED",
        "aggregateRejectionOriginal": "COVERED",
        "technicalClosureDecisionOriginal": "COVERED",
        "admissionSourceDecisionOriginal": "COVERED",
        "canonicalEffectDecisionOriginal": "COVERED",
        "causalDecisionOrder": "COVERED",
        "remaining": 0,
    }
    _impl._need(coverage == expected_coverage, "k-supplement-coverage")
    return {
        **base,
        "kind": "governance.loggerRetainedKReadback.v3",
        "supplementDigest": _sha256(supplement_path),
        "baselineOriginalProvenance": "COVERED",
        "causalDecisionOrder": _CAUSAL_ORDER,
        "decisionOriginalsVerified": len(_DECISIONS),
        "remaining": 0,
    }


def _implementation_proof(bundle: Path, revision: str) -> dict[str, Any]:
    carried = bundle / _BUNDLE_IMPL
    if _sha256(_IMPL_PATH) != _IMPL_SHA256:
        raise ValueError("logger-adapter:implementation-source-drift")
    if not carried.is_file() or carried.is_symlink() or _sha256(carried) != _IMPL_SHA256:
        raise ValueError("logger-adapter:implementation-carry-drift")
    return {
        "source": {
            "repository": "roccho-dev/governance",
            "revision": revision,
            "path": _IMPL_RELATIVE,
            "digest": _IMPL_SHA256,
        },
        "bundlePath": _BUNDLE_IMPL,
        "loadedBy": "tools/package_contract_targets/logger.py",
        "coldCodeRoot": "_cold/adrs",
        "checksumRowFormat": "<64hex><two spaces>./<path>",
    }


def expected_evidence(**kwargs):
    evidence = _BASE_EXPECTED_EVIDENCE(**kwargs)
    bundle = Path(kwargs["bundle"]).resolve()
    bindings = kwargs["bindings"]
    revision = kwargs["sources"]["observer"]["revision"]
    proof = _implementation_proof(bundle, revision)
    stored = kwargs["read_object"](bundle / "logger-implementation.json", "logger-implementation")
    if stored != proof:
        raise ValueError("logger-adapter:implementation-readback")
    completion = _verify_retained_completion(
        _impl._bundle(bundle, bindings, "retainedManifest"),
        _impl._bundle(bundle, bindings, "retainedArtifact"),
        _impl._bundle(bundle, bindings, "independentJudgment"),
        _impl._bundle(bundle, bindings, "independentJudgmentOriginal"),
    )
    stored_completion = kwargs["read_object"](bundle / "logger-retained-completion-readback.json", "logger-retained-completion")
    if stored_completion != completion:
        raise ValueError("logger-adapter:retained-completion-readback")
    evidence["observerImplementation"] = proof
    evidence["retainedCompletion"] = completion
    evidence["retainedOriginalSources"] = {
        role: kwargs["sources"][role]
        for role in sorted(_EXTRA_SOURCE_PATHS)
    }
    return evidence


def produce(context: dict[str, Any]) -> dict[str, Any]:
    from tools import package_contract_port_cold as cold

    target = Path(context["targetSourceRoot"]).resolve()
    _verify_retained_completion(
        target / SOURCE_PATHS["retainedManifest"],
        target / SOURCE_PATHS["retainedArtifact"],
        target / SOURCE_PATHS["independentJudgment"],
        target / SOURCE_PATHS["independentJudgmentOriginal"],
    )

    original = cold.select_cold_record

    def select_with_existing_codec(*args, **kwargs):
        code_root = Path("_cold/adrs").resolve()
        if not code_root.is_dir():
            raise ValueError("logger-adapter:cold-code-root")
        kwargs["code_root"] = code_root
        return original(*args, **kwargs)

    cold.select_cold_record = select_with_existing_codec
    try:
        result = _BASE_PRODUCE(context)
    finally:
        cold.select_cold_record = original

    bundle = Path(context["bundle"]).resolve()
    candidate = str(context["targetCandidate"])
    bindings_path = bundle / "source-bindings.json"
    bindings = json.loads(bindings_path.read_text(encoding="utf-8"))
    for role, relative in _EXTRA_SOURCE_PATHS.items():
        destination = "sources/ops/" + Path(relative).name
        bindings[role] = _impl._copy(
            PROVIDER_REPOSITORY,
            candidate,
            relative,
            target / relative,
            bundle,
            destination,
        )
    _write(bindings_path, bindings)

    completion = _verify_retained_completion(
        _impl._bundle(bundle, bindings, "retainedManifest"),
        _impl._bundle(bundle, bindings, "retainedArtifact"),
        _impl._bundle(bundle, bindings, "independentJudgment"),
        _impl._bundle(bundle, bindings, "independentJudgmentOriginal"),
    )
    _write(bundle / "logger-retained-completion-readback.json", completion)

    carried = bundle / _BUNDLE_IMPL
    carried.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(_IMPL_PATH, carried)
    proof = _implementation_proof(bundle, str(context["governanceCandidate"]))
    _write(bundle / "logger-implementation.json", proof)

    evidence_path = bundle / "phase4-evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence["observerImplementation"] = proof
    evidence["retainedCompletion"] = completion
    evidence["retainedOriginalSources"] = {
        role: bindings[role]["source"]
        for role in sorted(_EXTRA_SOURCE_PATHS)
    }
    _write(evidence_path, evidence)

    manifest = [
        {"path": path.relative_to(bundle).as_posix(), "sha256": _sha256(path)}
        for path in sorted(bundle.rglob("*"))
        if path.is_file() and path.name != "bundle-manifest.json"
    ]
    _write(bundle / "bundle-manifest.json", manifest)

    files = list(result.get("producerFiles", []))
    files.extend(["logger-implementation.json", "logger-retained-completion-readback.json", _BUNDLE_IMPL])
    result["producerFiles"] = sorted(set(files))
    return result
