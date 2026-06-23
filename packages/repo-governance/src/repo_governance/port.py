"""Stable input/output contracts for the pure repo-governance core."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

Json = dict[str, Any]


@dataclass(frozen=True, order=True)
class Violation:
    """One deterministic rule violation."""

    rule_id: str
    code: str
    subject: str
    detail: str
    adr_ref: str
    severity: str = "error"

    def to_dict(self) -> Json:
        return {
            "ruleId": self.rule_id,
            "code": self.code,
            "subject": self.subject,
            "detail": self.detail,
            "adrRef": self.adr_ref,
            "severity": self.severity,
        }


@dataclass(frozen=True)
class EvaluationResult:
    """Complete deterministic projection returned by the pure core."""

    repo_contract: Json
    package_contracts: tuple[Json, ...]
    violations: tuple[Violation, ...]
    readme_generated: str
    plan: tuple[Json, ...]
    provenance: Json
    result_digest: str

    @property
    def passed(self) -> bool:
        return not self.violations

    def to_dict(self) -> Json:
        return {
            "kind": "governance.repoEvaluation.v1",
            "passed": self.passed,
            "repoContract": self.repo_contract,
            "packageContracts": list(self.package_contracts),
            "violations": [item.to_dict() for item in self.violations],
            "readmeGenerated": self.readme_generated,
            "plan": list(self.plan),
            "provenance": self.provenance,
            "resultDigest": self.result_digest,
        }
