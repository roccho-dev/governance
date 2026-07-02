# governance modules

## Package purpose

`modules/` contains Nix building blocks that support governance projection and check surfaces.

The package exists to package reusable Nix logic without making the repo root README carry module-level responsibility details.

## Responsibilities

- Provide Nix building blocks for deterministic governance checks and projection surfaces.
- Keep package behavior explicit through declared inputs.
- Support receipt-producing or artifact-producing checks.
- Preserve the boundary between Nix build success and final ADRS compliance.

## Public contract

A module may assemble or expose check/projector building blocks. It must not decide accepted meaning or imply final merge authority by itself.

## Required assertion

This package asserts:

```text
modules are reusable Nix building blocks for governance projection/check surfaces
```

## Required receipt

A module-derived check should produce or support receipts that identify:

- module or check id;
- input digest;
- output digest;
- package or contract id;
- whether the result is a receipt producer, artifact producer, selftest, shadow report, or final-join input.

## Entrypoints

- `modules/*.nix`
- imports from `flake.nix`
- checks using module-provided functions

## Dependencies

Modules may depend on declared Nix inputs and explicit repo paths.

## Non-goals

- Do not create accepted meaning.
- Do not mutate repositories.
- Do not approve branch protection or provider cutover.
- Do not make standalone `nix flake check` a final merge gate.

## Residuals

If a module cannot support a required receipt or projection row, the gap must remain visible as a residual or finding.

## ADRS refs

- Proposed: `roccho-dev/adrs#105` governance final-scope purpose join
- Proposed: `roccho-dev/adrs#106` README projection plane

Until those ADRS proposals are accepted, this README is a projection candidate.
