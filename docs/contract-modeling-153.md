# Recursive contract-modeling implementation for #153

## Current dependency

- ADRS PR: `roccho-dev/adrs#237`
- exact candidate head: `c9d4d0afd0679adc2a49e40d5e9e90ca6fd8f068`
- decision ID: `01K0E1CM000000000000000234`
- decision digest: `cc7ac3d6618b31eb0a0979b8aa0e2bfaf6abd95646e45c740d154c8204cd00d1`
- release: `recursive-contract-modeling-v1.0.0`

The decision is not merged authority yet. The compiler is therefore a mergeable
shadow implementation and must not claim cutover or migration completion.

## Implemented here

- closed recursive envelope and two closed profiles;
- evidence-derived eight-way admission;
- typed containment, purpose closure, and explicit supersession;
- quarantine with previous-current preservation;
- promotion-only current and real incremental/full replay equality;
- DuckDB gate catalog and version-normalizing ABI;
- exact-SHA package receipts for two unrelated real packages;
- bounded model-only package;
- 36-row bounded legacy responsibility ledger;
- responsibility-closure projection;
- expected-reason destructive proof;
- content-addressed Nix store readback.

## CI placement

The implementation is connected to the accepted two-workflow topology:

- `gov-final-scope-purpose-join` runs exact-candidate blocking regression;
- `gov-canary` performs evidence-only observation after merge.

No deleted legacy workflow is restored.

## Remaining migration closure

The bounded legacy corpus does not replace the final frozen legacy snapshot.
ADRS merge/release/replay, final inventory, external consumer count zero,
production cutover, effect readback, anti-reintroduction guard, and the final
`migration_complete=true` receipt remain open.
