# Export claim admission checker proposal

## Why

Downstream feat repos should not duplicate governance claim admission logic. Governance should expose one reusable checker surface for claim-port compilation, admission diagnostics, and official-view gate wiring.

## Decision

Export a stable claim admission checker from governance as a Nix-facing surface.

Implemented surface:

- `packages.claim-admission-check`
- `apps.claim-admission-check`
- CLI inputs:
  - `--upstream-grants` / `--grants`
  - `--downstream-assertions` / `--assertions`
  - `--receipts`
  - `--out`
  - optional `--official-view`
  - optional `--require-active`
- stable JSONL admission output with `governance.organizationAdmission.v1` and `diagnosticClass`
- stable JSONL official-view output with `governance.organizationOfficialView.v1` when `--official-view` is supplied

## Boundary

This does not make governance authority. ADRS accepted records remain authority. The exported checker is a deterministic non-authority judge that downstream repos may call from local CI.

## Implementation proof

`nix flake check` includes `checks.claim-admission-check-export`. That check builds and runs the exported checker through the Nix-facing surface and proves both admission output and official-view output.

## Merge gate

Merge only after the checker export is covered by `nix flake check` and the existing claim-port fixture continues to pass.
