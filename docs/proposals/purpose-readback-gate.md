# Purpose readback gate proposal

## Why

Gen1 stop-ok must remain a claim, not approval. A selected-objective accept needs an explicit Gen0 readback.

## Decision

Add `tools/check-purpose-readback.py` and run its selftest from the GitHub CI workflow before the existing flake contract step.

The gate checks:

- selected objective is present;
- stop-ok with accept needs Gen0 readback;
- stop-ok needs evidence and machine gate rows;
- conflicts, unknowns, and residual risks are explicit fields;
- semantic, business, and top-objective claims are explicit enums;
- CI, PR, or merge rows alone do not prove business value;
- accept with unresolved conflicts keeps residual risks.

## Boundary

This is a local deterministic gate only. It does not change branch protection, merge policy, SSOT adoption, flake surface, or business-value proof.

## Merge Gate

Merge only if the GitHub CI step `Check purpose readback gate` stays present and the check remains limited to Gen0/Gen1 readback shape.
