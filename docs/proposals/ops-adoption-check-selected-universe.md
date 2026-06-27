# Ops adoption check against selected universe proposal

## Why

Once ADRS defines a selected universe, governance needs a concrete check proving that the selected `ops` repo snapshot adopts the required claim admission check.

## Decision

Add a governance-side check for the `ops` selected repo snapshot.

The check verifies the selected ops cases for:

- required claim admission check presence
- temporary warning mode while upstream grant projection is still missing
- strict mode requirement once upstream grant projection is present

Broader adoption fields such as governance input, CI intent, downstream claim surface, and receipt surface are covered by the general adoption monitor.

## Dependency

Depends on the general claim-check adoption monitor and ADRS selected universe/upstream grant port proposal.

## Boundary

This is a governance verification of adoption, not execution of ops business logic and not a replacement for ops-local CI.

## Implementation proof

`tools/check-ops-claim-adoption-selected-universe.py selftest` reads `fixtures/ops-adoption-check-selected-universe/cases.jsonl` and proves pass, missing-check failure, temporary warning allowance before upstream grant projection, and strict-mode requirement after upstream grant projection.

Fixture count: 4 selected-ops cases.

## Merge gate

Merge only when an `ops` fixture or pinned snapshot demonstrates both pass and missing-check failure cases.
