# Organization join diagnostic fixture proposal

## Why

Governance needs a deterministic fixture that checks how accepted upstream records, downstream assertions, and receipts join before any real repository is failed.

## Direction

Add a governance-side diagnostic fixture for organization joins. The first implementation should run through `nix flake check` but remain fixture-only and non-blocking for real repositories.

## Decision

Define fixture cases for:

- `organization-active`
- `orphan-assertion`
- `unclaimed-grant`
- `stale-assertion`
- `asserted-but-unproven`
- `conflict`
- `revoked-grant`

The fixture must use local checked-in inputs only. It must not call GitHub, read remote branches, or treat README artifacts as authority.

## Boundary

This proposal does not implement the fail gate and does not require all repositories to emit assertion packets yet.

## Merge Gate

Merge only if the diagnostic fixture remains local, deterministic, and fixture-scoped.
