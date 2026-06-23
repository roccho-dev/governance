"""Pure projection and lint core for common repo/package governance."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

from .port import EvaluationResult, Json, Violation

PROJECTOR_VERSION = "repo-governance/0.1.0"
REQUIRED_RULES = (
    "repo-is-packages",
    "core-port-is-lib",
    "adapter-placement",
    "dependency-direction",
    "goal-no-goal",
    "generated-non-authority",
    "readme-contract",
    "waiver-expiry",
    "hidden-input-ban",
)
FORBIDDEN_LIB_CAPABILITIES = frozenset(
    {
        "clock",
        "credential-use",
        "database-write",
        "environment",
        "exit-code",
        "filesystem-read",
        "filesystem-write",
        "github-mutation",
        "network",
        "random",
        "stderr",
        "stdout",
        "subprocess",
    }
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def seq(value: Any) -> list[Any]:
    return list(value) if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) else []


def text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def texts(value: Any) -> list[str]:
    return sorted({text(item) for item in seq(value) if text(item)})


def mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def add(items: list[Violation], refs: Mapping[str, str], rule: str, code: str, subject: str, detail: str) -> None:
    items.append(Violation(rule, code, subject or "<repo>", detail, refs.get(rule, "<unknown>")))


def normalize_package(raw: Mapping[str, Any]) -> Json:
    return {
        "packageId": text(raw.get("packageId")),
        "classification": text(raw.get("classification")),
        "shape": text(raw.get("shape")),
        "goal": text(raw.get("goal")),
        "noGoals": texts(raw.get("noGoals")),
        "dependencies": texts(raw.get("dependencies")),
        "capabilities": texts(raw.get("capabilities")),
        "adapterKind": text(raw.get("adapterKind")) or None,
        "definesRules": bool(raw.get("definesRules", False)),
    }


def normalize_surface(raw: Mapping[str, Any]) -> Json:
    return {
        "surfaceId": text(raw.get("surfaceId")),
        "classification": text(raw.get("classification")),
        "shape": text(raw.get("shape")),
        "goal": text(raw.get("goal")),
        "noGoals": texts(raw.get("noGoals")),
        "adapterKind": text(raw.get("adapterKind")) or None,
        "authority": raw.get("authority"),
    }


def normalize_bundle(raw: Mapping[str, Any]) -> Json:
    rules = [
        {"ruleId": text(row.get("ruleId")), "adrRef": text(row.get("adrRef")), "status": text(row.get("status"))}
        for row in (mapping(item) for item in seq(raw.get("rules")))
    ]
    return {
        "kind": text(raw.get("kind")),
        "bundleId": text(raw.get("bundleId")),
        "status": text(raw.get("status")),
        "sourceRef": text(raw.get("sourceRef")),
        "rules": sorted(rules, key=lambda r: (r["ruleId"], r["adrRef"])),
    }


def normalize_snapshot(raw: Mapping[str, Any]) -> Json:
    waivers = []
    for item in seq(raw.get("waivers")):
        row = mapping(item)
        waivers.append(
            {
                "ruleId": text(row.get("ruleId")),
                "subject": text(row.get("subject")),
                "expiresOn": text(row.get("expiresOn")),
                "adrRef": text(row.get("adrRef")),
            }
        )
    return {
        "kind": text(raw.get("kind")),
        "repoId": text(raw.get("repoId")),
        "evaluationDate": text(raw.get("evaluationDate")),
        "goal": text(raw.get("goal")),
        "noGoals": texts(raw.get("noGoals")),
        "generated": dict(sorted(mapping(raw.get("generated")).items())),
        "readme": dict(sorted(mapping(raw.get("readme")).items())),
        "hiddenInputs": texts(raw.get("hiddenInputs")),
        "packages": sorted([normalize_package(mapping(i)) for i in seq(raw.get("packages"))], key=lambda p: p["packageId"]),
        "surfaces": sorted([normalize_surface(mapping(i)) for i in seq(raw.get("surfaces"))], key=lambda s: s["surfaceId"]),
        "waivers": sorted(waivers, key=lambda w: (w["ruleId"], w["subject"], w["expiresOn"])),
    }


def rule_refs(bundle: Mapping[str, Any], violations: list[Violation]) -> dict[str, str]:
    refs: dict[str, str] = {}
    accepted: set[str] = set()
    for item in seq(bundle.get("rules")):
        row = mapping(item)
        if text(row.get("status")) == "accepted":
            accepted.add(text(row.get("ruleId")))
            refs[text(row.get("ruleId"))] = text(row.get("adrRef"))
    for rule in REQUIRED_RULES:
        if rule not in accepted:
            add(violations, refs, "bundle-contract", "RULE_MISSING", rule, "required rule is missing")
    for rule in sorted(accepted - set(REQUIRED_RULES)):
        add(violations, refs, "bundle-contract", "RULE_UNKNOWN", rule, "rule is not implemented by repo-governance")
    return refs


def add_goal_violations(snapshot: Mapping[str, Any], violations: list[Violation], refs: Mapping[str, str]) -> None:
    repo_id = text(snapshot.get("repoId"))
    if not text(snapshot.get("goal")):
        add(violations, refs, "goal-no-goal", "MISSING_REPO_GOAL", repo_id, "repo goal is required")
    if not texts(snapshot.get("noGoals")):
        add(violations, refs, "goal-no-goal", "MISSING_REPO_NO_GOAL", repo_id, "repo no-goals are required")
    for kind, key, rows in (
        ("PACKAGE", "packageId", seq(snapshot.get("packages"))),
        ("SURFACE", "surfaceId", seq(snapshot.get("surfaces"))),
    ):
        for item in rows:
            row = mapping(item)
            subject = text(row.get(key))
            if not text(row.get("goal")):
                add(violations, refs, "goal-no-goal", f"MISSING_{kind}_GOAL", subject, f"{kind.lower()} goal is required")
            if not texts(row.get("noGoals")):
                add(violations, refs, "goal-no-goal", f"MISSING_{kind}_NO_GOAL", subject, f"{kind.lower()} no-goals are required")


def readme_text(repo: Json, packages: tuple[Json, ...]) -> str:
    lines = [
        "<!-- generated by repo-governance; non-authority view -->",
        f"# {repo['repoId']}",
        "",
        f"Goal: {repo['goal']}",
        "",
        "## Packages",
    ]
    lines.extend(f"- `{package['packageId']}`: {package['goal']}" for package in packages)
    return "\n".join(lines) + "\n"


def evaluate(adr_bundle: Mapping[str, Any], repo_snapshot: Mapping[str, Any]) -> EvaluationResult:
    bundle = normalize_bundle(adr_bundle)
    snapshot = normalize_snapshot(repo_snapshot)
    violations: list[Violation] = []
    refs = rule_refs(bundle, violations)
    raw_packages = [mapping(item) for item in seq(repo_snapshot.get("packages"))]
    package_ids = {text(row.get("packageId")) for row in raw_packages}
    by_id = {text(row.get("packageId")): row for row in raw_packages}

    if not snapshot["packages"]:
        add(violations, refs, "repo-is-packages", "NO_PACKAGES", snapshot["repoId"], "repo must declare at least one package")

    for row in raw_packages:
        pid = text(row.get("packageId"))
        classification = text(row.get("classification"))
        shape = text(row.get("shape"))
        if classification == "lib" and shape != "core+port":
            add(violations, refs, "core-port-is-lib", "LIB_NOT_CORE_PORT", pid, "lib package must use core+port shape")
        if classification.startswith("adapter") and shape != "adapter":
            add(violations, refs, "adapter-placement", "ADAPTER_NOT_ADAPTER_SHAPE", pid, "adapter package must use adapter shape")
        if classification.startswith("adapter") and bool(row.get("definesRules", False)):
            add(violations, refs, "adapter-placement", "ADAPTER_DEFINES_RULES", pid, "adapter package must not define rule semantics")
        if classification == "lib":
            bad = sorted(set(texts(row.get("capabilities"))) & FORBIDDEN_LIB_CAPABILITIES)
            if bad:
                add(violations, refs, "hidden-input-ban", "LIB_HIDDEN_CAPABILITY", pid, "lib package has forbidden capabilities: " + ", ".join(bad))
            for dep in texts(row.get("dependencies")):
                if text(by_id.get(dep, {}).get("classification")).startswith("adapter"):
                    add(violations, refs, "dependency-direction", "LIB_DEPENDS_ON_ADAPTER", pid, f"lib package depends on adapter {dep}")
    for dep in sorted({dep for row in raw_packages for dep in texts(row.get("dependencies"))} - package_ids):
        add(violations, refs, "dependency-direction", "UNKNOWN_DEPENDENCY", dep, "dependency target is not declared as a package")

    for item in seq(repo_snapshot.get("surfaces")):
        row = mapping(item)
        subject = text(row.get("surfaceId"))
        if text(row.get("shape")) != "adapter":
            add(violations, refs, "adapter-placement", "SURFACE_NOT_ADAPTER", subject, "e2e/example surfaces must use adapter shape")
        if row.get("authority") is not False:
            add(violations, refs, "generated-non-authority", "SURFACE_AUTHORITY", subject, "e2e/example surfaces must be non-authority")

    if mapping(repo_snapshot.get("generated")).get("authority") is not False:
        add(violations, refs, "generated-non-authority", "GENERATED_AUTHORITY", snapshot["repoId"], "generated outputs must be non-authority")
    readme = mapping(repo_snapshot.get("readme"))
    if readme.get("authority") is not False or readme.get("contractSource") != "repo-governance" or readme.get("generatedBlock") is not True:
        add(violations, refs, "readme-contract", "README_CONTRACT", snapshot["repoId"], "README must be a generated non-authority view from repo-governance")
    add_goal_violations(repo_snapshot, violations, refs)
    if texts(repo_snapshot.get("hiddenInputs")):
        add(violations, refs, "hidden-input-ban", "HIDDEN_INPUTS", snapshot["repoId"], "hidden inputs are forbidden: " + ", ".join(texts(repo_snapshot.get("hiddenInputs"))))

    evaluation_date = text(repo_snapshot.get("evaluationDate"))
    for item in seq(repo_snapshot.get("waivers")):
        row = mapping(item)
        expiry = text(row.get("expiresOn"))
        try:
            expired = bool(evaluation_date and expiry and date.fromisoformat(expiry) < date.fromisoformat(evaluation_date))
        except ValueError:
            expired = True
        if expired:
            add(violations, refs, "waiver-expiry", "WAIVER_EXPIRED", text(row.get("subject")), f"waiver expiresOn={expiry!r} is not valid after evaluationDate={evaluation_date!r}")

    packages = tuple(snapshot["packages"])
    repo = {
        "repoId": snapshot["repoId"],
        "goal": snapshot["goal"],
        "noGoals": snapshot["noGoals"],
        "packageIds": [p["packageId"] for p in packages],
        "sourceRef": bundle["sourceRef"],
        "generatedAuthority": snapshot["generated"].get("authority"),
        "readmeAuthority": snapshot["readme"].get("authority"),
    }
    ordered = tuple(sorted(violations))
    plan = tuple({"ruleId": v.rule_id, "subject": v.subject, "action": "fix violation before enabling as required check"} for v in ordered)
    provenance = {
        "kind": "governance.repoGovernanceProvenance.v1",
        "projectorVersion": PROJECTOR_VERSION,
        "sourceRef": bundle["sourceRef"],
        "ruleDigest": digest(bundle),
        "snapshotDigest": digest(snapshot),
    }
    generated = readme_text(repo, packages)
    result = {
        "repoContract": repo,
        "packageContracts": list(packages),
        "violations": [v.to_dict() for v in ordered],
        "readmeGenerated": generated,
        "plan": list(plan),
        "provenance": provenance,
    }
    return EvaluationResult(repo, packages, ordered, generated, plan, provenance, digest(result))
