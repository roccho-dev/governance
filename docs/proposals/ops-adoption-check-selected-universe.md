# Ops adoption check against selected universe proposal

## Why

Once ADRS defines a selected universe, governance needs a concrete check proving that the selected `ops` repo snapshot adopts the required claim admission check.

## Decision

Add a governance-side check for the `ops` selected repo snapshot.

The check verifies:

- `ops` is in the selected universe
- `ops` declares the claim admission check in generated checks or CI intent
- `ops` keeps a governance checker input
- `ops` exposes downstream claim and receipt surfaces
- warning-only mode is allowed only when the selected universe still lacks upstream grant projection

## Dependency

Depends on the general claim-check adoption monitor and ADRS selected universe/upstream grant port proposal.

## Boundary

This is a governance verification of adoption, not execution of ops business logic and not a replacement for ops-local CI.

## Implementation proof

`tools/check-ops-claim-adoption-selected-universe.py selftest` reads `fixtures/ops-adoption-check-selected-universe/cases.jsonl` and proves pass, missing-check failure, warning-only temporary allowance before upstream grant projection, warning-only failure after upstream grant projection, and ops-not-selected failure.

Fixture count: 5 cases.

## Merge gate

Merge only when an `ops` fixture or pinned snapshot demonstrates both pass and missing-check failure cases.
