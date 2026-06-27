# Export claim admission checker proposal

## Why

Downstream feat repos should not duplicate governance claim admission logic. Governance should expose one reusable checker surface for claim-port compilation, admission diagnostics, and official-view gate wiring.

## Decision

Export a stable claim admission checker from governance as a Nix-facing surface.

Minimum surface:

- `packages.claim-admission-check`
- `apps.claim-admission-check`
- documented CLI inputs for upstream grants, downstream assertions, receipts, and official view
- stable JSONL output with `governance.organizationAdmission.v1` and `diagnosticClass`

## Boundary

This does not make governance authority. ADRS accepted records remain authority. The exported checker is a deterministic non-authority judge that downstream repos may call from local CI.

## Merge gate

Merge only after the checker export is covered by `nix flake check` and the existing claim-port fixture continues to pass.
