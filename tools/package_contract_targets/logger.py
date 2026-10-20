#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.machinery
import importlib.util
import json
import shutil
from pathlib import Path
from typing import Any

_IMPL_RELATIVE = "tools/package_contract_target_impls/logger.py"
_IMPL_PATH = Path(__file__).resolve().parents[1] / "package_contract_target_impls" / "logger.py"
_IMPL_SHA256 = "sha256:e44a269b5db0385c2510990782f1d71925a6fb19b38e2072117b605c09c78ff1"
_BUNDLE_IMPL = "sources/observer/logger-implementation.py"


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


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

_BASE_PRODUCE = _impl.produce
_BASE_EXPECTED_EVIDENCE = _impl.expected_evidence


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
    }


def expected_evidence(**kwargs):
    evidence = _BASE_EXPECTED_EVIDENCE(**kwargs)
    bundle = Path(kwargs["bundle"]).resolve()
    revision = kwargs["sources"]["observer"]["revision"]
    proof = _implementation_proof(bundle, revision)
    stored = kwargs["read_object"](bundle / "logger-implementation.json", "logger-implementation")
    if stored != proof:
        raise ValueError("logger-adapter:implementation-readback")
    evidence["observerImplementation"] = proof
    return evidence


def produce(context: dict[str, Any]) -> dict[str, Any]:
    from tools import package_contract_port_cold as cold

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
    carried = bundle / _BUNDLE_IMPL
    carried.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(_IMPL_PATH, carried)
    proof = _implementation_proof(bundle, str(context["governanceCandidate"]))
    _write(bundle / "logger-implementation.json", proof)

    evidence_path = bundle / "phase4-evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence["observerImplementation"] = proof
    _write(evidence_path, evidence)

    manifest = [
        {"path": path.relative_to(bundle).as_posix(), "sha256": _sha256(path)}
        for path in sorted(bundle.rglob("*"))
        if path.is_file() and path.name != "bundle-manifest.json"
    ]
    _write(bundle / "bundle-manifest.json", manifest)

    files = list(result.get("producerFiles", []))
    files.extend(["logger-implementation.json", _BUNDLE_IMPL])
    result["producerFiles"] = sorted(set(files))
    return result
