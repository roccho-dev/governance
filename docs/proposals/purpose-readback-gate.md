# Purpose readback gate proposal

## Why

Gen1 stop-ok must remain a claim, not approval. A selected-objective accept needs an explicit Gen0 readback.

## Decision

Add `tools/check-purpose-readback.py` and wire its selftest into `nix flake check`.

The gate checks:

- selected objective is present;
- stop-ok with accept needs Gen0 readback;
- stop-ok needs evidence and machine gate rows;
- conflicts, unknowns, and residual risks are explicit fields;
- semantic, business, and top-objective claims are explicit enums;
- CI, PR, or merge rows alone do not prove business value;
- accept with unresolved conflicts keeps residual risks.

## Boundary

This is a local deterministic gate only. It does not change branch protection, merge policy, SSOT adoption, or business-value proof.

## Merge Gate

Merge only if `purpose-readback-gate-selftest` stays in `flake.nix` and the check remains limited to Gen0/Gen1 readback shape.
