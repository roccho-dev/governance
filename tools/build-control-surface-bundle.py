#!/usr/bin/env python3
"""Bind exact current-state lanes into one non-authority control surface bundle.

Upstream projectors own discovery and semantic derivation. This tool only verifies
exact bytes, kinds, source refs, and canonical binding. It never crawls repositories,
infers accepted meaning or conformance, renders UI, or performs provider effects.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any, Iterable

BUNDLE_KIND = "controlSurface.bundle.v1"
EXPECTED_KINDS = {
    "contractGraph": "contractGraph.current.v1",
    "decisionImpact": "decisionImpact.current.v1",
    "obligationState": "obligationState.current.v1",
    "workCurrent": "workLifecycle.current.v1",
    "responsibilityClosure": "responsibilityClosure.current.v1",
    "evidenceState": "evidenceState.current.v1",
}
ROLES = tuple(sorted(EXPECTED_KINDS))


class ContractError(ValueError):
    pass


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def digest_value(value: Any) -> str:
    return digest_bytes(canonical(value).encode("utf-8"))


def assignments(values: Iterable[str], label: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in values:
        role, separator, value = raw.partition("=")
        role, value = role.strip(), value.strip()
        if not separator or not role or not value:
            raise ContractError(f"{label} must be ROLE=VALUE: {raw!r}")
        if role in result:
            raise ContractError(f"duplicate {label} role: {role}")
        result[role] = value
    return result


def exact_roles(values: dict[str, Any], label: str) -> None:
    actual, expected = set(values), set(ROLES)
    missing, extra = sorted(expected - actual), sorted(actual - expected)
    if missing or extra:
        raise ContractError(f"{label} roles differ: missing={missing} extra={extra}")


def read_json(path: Path, role: str) -> tuple[bytes, dict[str, Any]]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ContractError(f"{role}: cannot read {path}: {exc}") from exc
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ContractError(f"{role}: UTF-8 BOM is forbidden")
    if b"\r" in raw:
        raise ContractError(f"{role}: CR bytes are forbidden")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"{role}: invalid UTF-8 JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"{role}: input must be one JSON object")
    return raw, value


def sha256(value: str, role: str) -> str:
    prefix, separator, suffix = value.partition(":")
    if prefix != "sha256" or not separator or len(suffix) != 64:
        raise ContractError(f"{role}: expected digest must be sha256:<64 lowercase hex>")
    if suffix.lower() != suffix or any(char not in "0123456789abcdef" for char in suffix):
        raise ContractError(f"{role}: expected digest must be lowercase hexadecimal")
    return value


def build_bundle(
    *,
    decision_ref: str,
    inputs: dict[str, Path],
    sources: dict[str, str],
    expected_digests: dict[str, str],
) -> dict[str, Any]:
    decision_ref = decision_ref.strip()
    if not decision_ref:
        raise ContractError("decision-ref is required")
    exact_roles(inputs, "input")
    exact_roles(sources, "source")
    exact_roles(expected_digests, "expect")

    metadata: list[dict[str, str]] = []
    states: dict[str, dict[str, Any]] = {}
    for role in ROLES:
        raw, state = read_json(inputs[role], role)
        actual = digest_bytes(raw)
        expected = sha256(expected_digests[role], role)
        if actual != expected:
            raise ContractError(f"{role}: input digest mismatch: expected={expected} actual={actual}")
        kind = EXPECTED_KINDS[role]
        if state.get("kind") != kind:
            raise ContractError(f"{role}: kind mismatch: expected={kind!r} actual={state.get('kind')!r}")
        if state.get("authority") is True:
            raise ContractError(f"{role}: generated current-state input must not claim authority")
        source_ref = sources[role].strip()
        if not source_ref:
            raise ContractError(f"{role}: source ref is required")
        metadata.append({"role": role, "kind": kind, "sourceRef": source_ref, "digest": actual})
        states[role] = state

    base: dict[str, Any] = {
        "kind": BUNDLE_KIND,
        "authority": False,
        "decisionRef": decision_ref,
        "inputDigest": digest_value({"decisionRef": decision_ref, "inputs": metadata}),
        "inputs": metadata,
        "states": states,
    }
    return {**base, "semanticDigest": digest_value(base)}


def write_bundle(path: Path | None, bundle: dict[str, Any]) -> None:
    output = canonical(bundle) + "\n"
    if path is None:
        print(output, end="")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output, encoding="utf-8", newline="\n")


def fixture(role: str, *, authority: bool = False) -> dict[str, Any]:
    return {
        "kind": EXPECTED_KINDS[role],
        "authority": authority,
        "rows": [{"id": f"{role}:1", "status": "current"}],
    }


def write_fixture(path: Path, value: dict[str, Any], *, crlf: bool = False, bom: bool = False) -> str:
    raw = (canonical(value) + "\n").encode()
    if crlf:
        raw = raw.replace(b"\n", b"\r\n")
    if bom:
        raw = b"\xef\xbb\xbf" + raw
    path.write_bytes(raw)
    return digest_bytes(raw)


def fails(fragment: str, call: Any, cases: list[str]) -> None:
    try:
        call()
    except ContractError as exc:
        if fragment not in str(exc):
            raise AssertionError(f"expected {fragment!r}, got {exc!r}") from exc
        cases.append(fragment)
        return
    raise AssertionError(f"expected ContractError containing {fragment!r}")


def selftest() -> int:
    cases: list[str] = []
    with tempfile.TemporaryDirectory() as raw_dir:
        root = Path(raw_dir)
        inputs, sources, expected = {}, {}, {}
        for role in ROLES:
            path = root / f"{role}.json"
            inputs[role] = path
            sources[role] = f"fixture://{role}@rev-1"
            expected[role] = write_fixture(path, fixture(role))

        args = {
            "decision_ref": "doc://adrs/internal-organization-semantic-map-v1@decision-1",
            "inputs": inputs,
            "sources": sources,
            "expected_digests": expected,
        }
        clean = build_bundle(**args)
        reordered = build_bundle(
            decision_ref=args["decision_ref"],
            inputs=dict(reversed(tuple(inputs.items()))),
            sources=dict(reversed(tuple(sources.items()))),
            expected_digests=dict(reversed(tuple(expected.items()))),
        )
        assert canonical(clean) == canonical(reordered)
        assert [row["role"] for row in clean["inputs"]] == list(ROLES)
        cases.extend(["clean", "reordered-input"])

        missing = dict(inputs)
        missing.pop(ROLES[0])
        fails("input roles differ", lambda: build_bundle(**{**args, "inputs": missing}), cases)

        extra = dict(inputs)
        extra["unexpected"] = root / "unexpected.json"
        fails("input roles differ", lambda: build_bundle(**{**args, "inputs": extra}), cases)

        role = ROLES[0]
        original = inputs[role].read_bytes()
        inputs[role].write_text("{}\n")
        fails("input digest mismatch", lambda: build_bundle(**args), cases)
        inputs[role].write_bytes(original)

        wrong = {**fixture(role), "kind": "wrong.v1"}
        expected[role] = write_fixture(inputs[role], wrong)
        fails("kind mismatch", lambda: build_bundle(**args), cases)

        expected[role] = write_fixture(inputs[role], fixture(role, authority=True))
        fails("must not claim authority", lambda: build_bundle(**args), cases)

        expected[role] = write_fixture(inputs[role], fixture(role), crlf=True)
        fails("CR bytes are forbidden", lambda: build_bundle(**args), cases)

        expected[role] = write_fixture(inputs[role], fixture(role), bom=True)
        fails("UTF-8 BOM is forbidden", lambda: build_bundle(**args), cases)

    print(canonical({
        "kind": "governance.controlSurfaceBundle.selftest.v1",
        "status": "pass",
        "authority": False,
        "caseCount": len(cases),
        "cases": cases,
    }))
    return 0


def run_build(args: argparse.Namespace) -> int:
    bundle = build_bundle(
        decision_ref=args.decision_ref,
        inputs={role: Path(path) for role, path in assignments(args.input, "input").items()},
        sources=assignments(args.source, "source"),
        expected_digests=assignments(args.expect, "expect"),
    )
    write_bundle(args.out, bundle)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--decision-ref", required=True)
    build.add_argument("--input", action="append", default=[], metavar="ROLE=PATH")
    build.add_argument("--source", action="append", default=[], metavar="ROLE=REF")
    build.add_argument("--expect", action="append", default=[], metavar="ROLE=SHA256")
    build.add_argument("--out", type=Path)
    build.set_defaults(run=run_build)
    check = commands.add_parser("selftest")
    check.set_defaults(run=lambda _args: selftest())
    args = parser.parse_args()
    try:
        return int(args.run(args))
    except ContractError as exc:
        raise SystemExit(f"control-surface-bundle: {exc}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
