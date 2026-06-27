# Log route fixture join check

## Why

ADRS now defines deploy log route policy. Governance needs a deterministic fixture join before any production gate is added.

## Scope

This PR adds the governance-side proposal and fixture cases for joining:

- ADRS log route policy
- ops deployment inventory
- ops observed log route receipt

## Decision

The fixture join should report these diagnostics:

- missing-policy
- missing-receipt
- stale-receipt
- sink-drift
- policy-conflict
- authority-leak

## Boundary

- No provider API access.
- No live deployment scan.
- No production admission gate.
- No ops receipt emission.

## Merge gate

The PR must remain fixture/check-scope only. Production fail-closed admission belongs to a later governance PR after ops feeds exist.
