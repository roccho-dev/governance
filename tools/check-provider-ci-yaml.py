#!/usr/bin/env python3
"""Read-only check for generated provider CI YAML.

The rule is narrow: provider CI YAML is allowed as generated adapter output,
not as the source of CI meaning. This tool renders a small CI intent to provider
entry files and checks markers, digests, drift, shadow mode, and scoped waivers.
It performs no provider execution and no remote mutation.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from dataclasses import dataclass, replace
from datetime import date
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

PROJECTOR = "governance-provider-ci-yaml-projector"
VERSION = "provider-ci-yaml.v1"
NOTE = "generated non-authority provider CI adapter; edit ci.intent.v1.jsonl instead"
TARGET_PATHS = {
    "github-actions": ".github/workflows/ci.yml",
    "gitlab-ci": ".gitlab-ci.yml",
    "circleci": ".circleci/config.yml",
}
ENTRY_PATTERNS = (
    re.compile(r"^\.github/workflows/.+\.ya?ml$"),
    re.compile(r"^\.gitlab-ci\.ya?ml$"),
    re.compile(r"^\.circleci/config\.ya?ml$"),
)
MARKER_FIELDS = (
    "generated-by",
    "source",
    "source-digest",
    "projection-digest",
    "projector-version",
    "target",
    "authority-note",
)
SHADOW_CODES = {
    "missing",
    "marker-missing",
    "marker-stale",
    "manual-edit",
    "undeclared-entry",
}


@dataclass(frozen=True)
class Policy:
    mode: str
    as_of: date
    shadow_deadline: date
    targets: tuple[str, ...]

    @property
    def shadow_active(self) -> bool:
        return self.mode == "shadow" and self.as_of <= self.shadow_deadline


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    target: str
    path: str
    message: str
    content_sha256: str
    waived_by: str | None = None

    def to_json(self) -> dict[str, Any]:
        return self.__dict__


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"invalid JSONL {path}:{line_no}: {exc}") from exc
        if not isinstance(row, dict):
            raise SystemExit(f"invalid JSONL {path}:{line_no}: row is not object")
        rows.append(row)
    return rows


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(canonical(row) + "\n" for row in rows), encoding="utf-8")


def parse_policy(rows: list[dict[str, Any]]) -> tuple[Policy, list[dict[str, Any]]]:
    policies = [r for r in rows if r.get("type") == "policy"]
    waivers = [r for r in rows if r.get("type") == "waiver"]
    if len(policies) != 1:
        raise SystemExit("exactly one policy row is required")
    row = policies[0]
    mode = row.get("mode")
    if mode not in {"shadow", "blocking"}:
        raise SystemExit("policy.mode must be shadow or blocking")
    targets = tuple(sorted(row.get("targets", TARGET_PATHS)))
    if not targets or any(t not in TARGET_PATHS for t in targets):
        raise SystemExit("policy.targets contains unknown target")
    return Policy(
        mode=mode,
        as_of=date.fromisoformat(row["as_of"]),
        shadow_deadline=date.fromisoformat(row["shadow_deadline"]),
        targets=targets,
    ), waivers


def compile_intent(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str, str]:
    jobs = [r for r in rows if r.get("type") == "job"]
    if not jobs:
        raise SystemExit("ci intent requires at least one job")
    normalized = sorted(rows, key=canonical)
    source_digest = digest("\n".join(canonical(r) for r in normalized))
    plan = [{"id": j["id"], "commands": j["commands"], "needs": sorted(j.get("needs", []))} for j in sorted(jobs, key=lambda r: r["id"])]
    projection_digest = digest(canonical({"jobs": plan}))
    return plan, source_digest, projection_digest


def marker(target: str, source_digest: str, projection_digest: str) -> str:
    values = {
        "generated-by": PROJECTOR,
        "source": "ci.intent.v1.jsonl",
        "source-digest": source_digest,
        "projection-digest": projection_digest,
        "projector-version": VERSION,
        "target": target,
        "authority-note": NOTE,
    }
    return "".join(f"# {k}: {values[k]}\n" for k in MARKER_FIELDS)


def render_target(target: str, plan: list[dict[str, Any]], source_digest: str, projection_digest: str) -> str:
    out = [marker(target, source_digest, projection_digest), "\n"]
    if target == "github-actions":
        out += ["name: ci\non: [pull_request, push]\njobs:\n"]
        for job in plan:
            out += [f"  {job['id']}:\n", "    runs-on: ubuntu-latest\n"]
            if job["needs"]:
                out.append(f"    needs: [{', '.join(job['needs'])}]\n")
            out += ["    steps:\n", "      - shell: bash\n", "        run: |\n"]
            out += [f"          {cmd}\n" for cmd in job["commands"]]
    elif target == "gitlab-ci":
        for job in plan:
            out += [f"{job['id']}:\n", "  script:\n"]
            out += [f"    - {json.dumps(cmd)}\n" for cmd in job["commands"]]
            if job["needs"]:
                out += ["  needs:\n"] + [f"    - {n}\n" for n in job["needs"]]
    elif target == "circleci":
        out += ["version: 2.1\njobs:\n"]
        for job in plan:
            out += [f"  {job['id']}:\n", "    docker:\n      - image: cimg/base:stable\n", "    steps:\n"]
            out += [f"      - run: {json.dumps(cmd)}\n" for cmd in job["commands"]]
        out += ["workflows:\n  ci:\n    jobs:\n"] + [f"      - {job['id']}\n" for job in plan]
    return "".join(out)


def parse_marker(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        if not line.startswith("#"):
            break
        if ":" not in line:
            continue
        key, value = line[1:].split(":", 1)
        values[key.strip()] = value.strip()
    return values


def provider_files(root: Path) -> dict[str, str]:
    found = {}
    for path in root.rglob("*"):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            if any(p.fullmatch(rel) for p in ENTRY_PATTERNS):
                found[rel] = path.read_text(encoding="utf-8")
    return found


def apply_policy(policy: Policy, waivers: list[dict[str, Any]], findings: list[Finding]) -> list[Finding]:
    result: list[Finding] = []
    if policy.mode == "shadow" and policy.as_of > policy.shadow_deadline:
        result.append(Finding("shadow-expired", "fail", "*", "*", "shadow deadline expired", "missing"))
    for finding in findings:
        item = replace(finding)
        if policy.shadow_active and item.code in SHADOW_CODES:
            item = replace(item, severity="warn")
        for waiver in waivers:
            if waiver.get("target") == item.target and waiver.get("path") == item.path and item.code in waiver.get("codes", []):
                if date.fromisoformat(waiver["expires_on"]) >= policy.as_of and waiver.get("content_sha256") == item.content_sha256:
                    item = replace(item, severity="warn", waived_by=waiver["id"])
        result.append(item)
    return sorted(result, key=lambda f: (f.severity, f.code, f.target, f.path))


def check(ci_intent: Path, policy_path: Path, repo: Path) -> dict[str, Any]:
    plan, source_digest, projection_digest = compile_intent(read_jsonl(ci_intent))
    policy, waivers = parse_policy(read_jsonl(policy_path))
    expected = {t: render_target(t, plan, source_digest, projection_digest) for t in policy.targets}
    actual = provider_files(repo)
    findings: list[Finding] = []
    for target in policy.targets:
        path = TARGET_PATHS[target]
        text = actual.get(path)
        if text is None:
            findings.append(Finding("missing", "fail", target, path, "provider entry file is missing", "missing"))
            continue
        markers = parse_marker(text)
        if any(field not in markers for field in MARKER_FIELDS):
            findings.append(Finding("marker-missing", "fail", target, path, "generated marker is incomplete", digest(text)))
        elif markers != parse_marker(expected[target]):
            findings.append(Finding("marker-stale", "fail", target, path, "generated marker is stale", digest(text)))
        if text != expected[target]:
            findings.append(Finding("manual-edit", "fail", target, path, "provider entry differs from projection", digest(text)))
    expected_paths = {TARGET_PATHS[t] for t in policy.targets}
    for path, text in actual.items():
        if path not in expected_paths:
            findings.append(Finding("undeclared-entry", "fail", "unknown", path, "provider entry is not projected", digest(text)))
    findings = apply_policy(policy, waivers, findings)
    fail_count = sum(f.severity == "fail" for f in findings)
    warn_count = sum(f.severity == "warn" for f in findings)
    return {
        "kind": "provider-ci-yaml-report.v1",
        "outcome": "fail" if fail_count else "warn" if warn_count else "pass",
        "fail_count": fail_count,
        "warn_count": warn_count,
        "findings": [f.to_json() for f in findings],
        "source_digest": source_digest,
        "projection_digest": projection_digest,
    }


def sample_ci() -> list[dict[str, Any]]:
    return [
        {"type": "job", "id": "lint", "commands": ["echo lint"]},
        {"type": "job", "id": "check", "needs": ["lint"], "commands": ["echo check"]},
    ]


def sample_policy(mode: str = "blocking", as_of: str = "2026-06-24", deadline: str = "2026-06-30") -> list[dict[str, Any]]:
    return [{"type": "policy", "mode": mode, "as_of": as_of, "shadow_deadline": deadline, "targets": list(TARGET_PATHS)}]


def write_projected(repo: Path, ci: Path, policy_path: Path) -> None:
    plan, source_digest, projection_digest = compile_intent(read_jsonl(ci))
    policy, _ = parse_policy(read_jsonl(policy_path))
    for target in policy.targets:
        path = repo / TARGET_PATHS[target]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_target(target, plan, source_digest, projection_digest), encoding="utf-8")


def assert_case(name: str, expected: str, mutator) -> None:
    with tempfile.TemporaryDirectory(prefix=f"provider-ci-{name}-") as raw:
        root = Path(raw)
        ci = root / "ci.intent.v1.jsonl"
        pol = root / "policy.jsonl"
        repo = root / "repo"
        repo.mkdir()
        write_jsonl(ci, sample_ci())
        write_jsonl(pol, sample_policy())
        write_projected(repo, ci, pol)
        mutator(ci, pol, repo)
        report = check(ci, pol, repo)
        assert report["outcome"] == expected, (name, report)


def selftest() -> int:
    assert_case("pass", "pass", lambda *_: None)
    assert_case("manual", "fail", lambda _ci, _pol, repo: (repo / TARGET_PATHS["github-actions"]).write_text((repo / TARGET_PATHS["github-actions"]).read_text() + "# edit\n"))
    assert_case("shadow", "warn", lambda _ci, pol, repo: (write_jsonl(pol, sample_policy("shadow")), (repo / TARGET_PATHS["gitlab-ci"]).unlink()))
    assert_case("expired", "fail", lambda _ci, pol, repo: (write_jsonl(pol, sample_policy("shadow", "2026-07-01", "2026-06-30")), (repo / TARGET_PATHS["gitlab-ci"]).unlink()))

    def waive(_ci: Path, pol: Path, repo: Path) -> None:
        target = repo / TARGET_PATHS["github-actions"]
        target.write_text(target.read_text() + "# edit\n", encoding="utf-8")
        rows = sample_policy() + [{"type": "waiver", "id": "w1", "target": "github-actions", "path": TARGET_PATHS["github-actions"], "codes": ["manual-edit"], "expires_on": "2026-06-30", "content_sha256": digest(target.read_text())}]
        write_jsonl(pol, rows)
    assert_case("waiver", "warn", waive)

    assert_case("extra", "fail", lambda _ci, _pol, repo: (repo / ".github/workflows/extra.yml").write_text("name: extra\n"))
    print("provider-ci-yaml-selftest: PASS")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    chk = sub.add_parser("check")
    chk.add_argument("--ci-intent", type=Path, required=True)
    chk.add_argument("--policy", type=Path, required=True)
    chk.add_argument("--repo", type=Path, required=True)
    test = sub.add_parser("selftest")
    args = parser.parse_args(argv)
    if args.cmd == "selftest":
        return selftest()
    report = check(args.ci_intent, args.policy, args.repo)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if report["outcome"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
