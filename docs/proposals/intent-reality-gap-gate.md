# Intent reality projection gate

## Why

ADRS now treats work as reconciliation between selected intent and deployed reality. To keep the loop small, governance must not require a new gap source ledger when the gap can be recomputed from purpose and reality.

## Direction

Keep the checked-input fixture gate, but treat `gap` as a projection, not as SSOT.

Primary inputs:

- `purpose` records: selected objective, intent refs, desired state, close condition
- `reality` records: observed facts, receipts, detected events, actual state

Derived outputs:

- projected gap
- routing diagnostics
- closure report

## Decision

`tools/check-intent-reality-gap.py` must project the gap from purpose and reality fixture rows. A persisted gap row may be used as a report, but not as the source of truth for the mismatch.

The gate reports clear diagnostics for:

- missing selected objective
- missing intent refs
- missing reality refs or missing-actual-state marker
- action without a projected gap
- action kind mismatch
- closure without post-action receipt
- PR/CI/merge-only closure
- unqualified semantic or business claims

## Boundary

This PR is a local deterministic fixture gate only.

It does not implement live runtime collection, provider adapters, agent repair queue, branch protection, production fail-closed admission, business value proof, semantic correctness proof, or SSOT adoption.

It also does not add `gap.jsonl` or `incident.jsonl` as source ledgers. Incident remains a reality event or view. Gap remains a projection.

## Merge Gate

Merge only if the fixture gate remains generic, checked-input only, projection-first, and does not claim runtime closure or agent repair completion.
