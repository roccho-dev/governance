# Recursive contract-modeling admission

This directory implements the deterministic production compiler tracked by
`roccho-dev/governance#153` and specified by accepted `roccho-dev/adrs#234`.

## Accepted authority pin

```text
ADRS_PR=roccho-dev/adrs#241
ADRS_MERGE=458ab4267882083de0593754d1bf9766bf8d54da
DECISION_ID=01K0E1CM000000000000000234
CORRECTION_DECISION_ID=01K0E1CM000000000000000235
DECISION_DIGEST=cc7ac3d6618b31eb0a0979b8aa0e2bfaf6abd95646e45c740d154c8204cd00d1
RELEASE=recursive-contract-modeling-v1.0.1
```

## Boundary

- ADRS owns meaning, purpose, policy, waivers, and cutover decisions.
- Owners submit claims and evidence, not trusted admission results.
- Governance validates, reduces, derives, projects, and reports without meaning authority.
- Ops or the owning repository performs external effects and returns exact-target readback.
- Deprecated spec repositories remain preserved evidence only.

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

The production proof includes two unrelated required governance packages, one
bounded model-only package, 36 mapped legacy responsibilities with zero unexplained,
replay equality, query/raw-access enforcement, expected-reason destructive cases,
and immutable Nix store materialization.

## Production cutover

The only blocking provider check remains:

```text
gov-final-scope-purpose-join / gate
```

That gate verifies the accepted ADRS identity, final frozen legacy inventory,
active legacy consumer count zero in the accepted universe, anti-reintroduction,
current package receipts, and the exact governance candidate. Migration completion
becomes true only after the admitted merge is observed by the existing push-only
post-effect readback.

## Run

```text
python3 -m unittest discover -s tools/contract-modeling/tests -p 'test_*.py'
python3 tools/check-contract-modeling-production-migration.py selftest
CANDIDATE_SHA=$(git rev-parse HEAD) bash tools/contract-modeling/run-proof.sh
```

Technical migration closure does not claim all-repository enforcement, business
outcome achievement, or corporate-sale achievement.
