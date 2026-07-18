# Recursive contract-modeling admission

This directory implements the deterministic compiler tracked by
`roccho-dev/governance#153` and specified by `roccho-dev/adrs#234`.

## Current authority pin

```text
ADRS_PR=roccho-dev/adrs#237
ADRS_HEAD=c9d4d0afd0679adc2a49e40d5e9e90ca6fd8f068
DECISION_ID=01K0E1CM000000000000000234
DECISION_DIGEST=cc7ac3d6618b31eb0a0979b8aa0e2bfaf6abd95646e45c740d154c8204cd00d1
RELEASE=recursive-contract-modeling-v1.0.0
```

The ADRS PR is still an accepted candidate, not merged authority. Therefore this
implementation remains `authority=false`, `mode=shadow`, and
`migration_complete=false`.

## Boundary

- ADRS owns meaning, purpose, policy, waivers, and cutover decisions.
- Owners submit claims and evidence, not trusted admission results.
- Governance validates, reduces, derives, projects, and reports without production mutation.
- Ops or the owning repository performs effects and returns exact-target readback.
- Deprecated `spec`/`specs` content is historical evidence only.

## Data flow

```text
claims
→ closed validation
→ supersession and recursive containment
→ derived eight-way admission
→ promotion-only current epoch
→ DuckDB gates and stable ABI
→ responsibility closure and exact-SHA receipts
```

The proof includes two unrelated real governance packages, one bounded model-only
package, replay equality, expected-reason destructive cases, and immutable Nix
store materialization.

## Run

```text
python3 -m unittest discover -s tools/contract-modeling/tests -p 'test_*.py'
CANDIDATE_SHA=$(git rev-parse HEAD) bash tools/contract-modeling/run-proof.sh
```

The bounded 36-row legacy corpus is not the final frozen legacy inventory and does
not prove external consumer count zero. Production cutover, external readback, and
the final `migration_complete=true` receipt remain separate residuals.
