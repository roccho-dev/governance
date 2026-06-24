"""Public API for the pure repo-governance lib package."""

from .core import PROJECTOR_VERSION, REQUIRED_RULES, canonical_json, digest, evaluate
from .port import EvaluationResult, Violation

__all__ = [
    "PROJECTOR_VERSION",
    "REQUIRED_RULES",
    "EvaluationResult",
    "Violation",
    "canonical_json",
    "digest",
    "evaluate",
]
