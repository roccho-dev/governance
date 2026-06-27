# Intent reality gap gate

## Why

ADRS now defines work as reconciliation between selected intent and deployed reality. Governance needs a deterministic gate so a work item can be rejected before it becomes an ungrounded PR, self-approved stop-ok, or green-check-only closure.

## Direction

Add a small checked-input fixture gate for the common object shape:

- `intent_reality_gap`
- `reconciliation_action`
- `reconciliation_closure`

This is the first governance step toward the state where defining a gap is enough to route, act, and close work with evidence.

## Decision

Add `tools/check-intent-reality-gap.py` and fixture rows under `fixtures/intent-reality-gap/cases.jsonl`.

The gate reports clear diagnostics for:

- missing selected objective
- missing intent refs
- missing reality refs or missing-actual-state marker
- missing owner or close condition
- action without gap
- action kind mismatch
- closure without post-action receipt
- PR/CI/merge-only closure
- unqualified semantic or business claims

## Boundary

This PR is a local deterministic fixture gate only.

It does not implement live runtime collection, provider adapters, agent repair queue, branch protection, production fail-closed admission, business value proof, semantic correctness proof, or SSOT adoption.

## Merge Gate

Merge only if the fixture gate remains generic, checked-input only, and does not claim runtime closure or agent repair completion.
