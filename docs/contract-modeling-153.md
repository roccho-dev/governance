# Recursive contract-modeling implementation for #153

## Accepted dependency

- ADRS Issue: `roccho-dev/adrs#234` — completed
- ADRS PR: `roccho-dev/adrs#241`
- accepted merge: `458ab4267882083de0593754d1bf9766bf8d54da`
- decision ID: `01K0E1CM000000000000000234`
- publication correction ID: `01K0E1CM000000000000000235`
- decision digest: `cc7ac3d6618b31eb0a0979b8aa0e2bfaf6abd95646e45c740d154c8204cd00d1`
- release: `recursive-contract-modeling-v1.0.1`
- compiler shadow merge: `495fb26a6794155586f2b7af52e7da09285fa780`

## Implemented

- closed recursive envelope and package/data-model profiles;
- evidence-derived eight-way admission;
- typed containment, purpose closure, and explicit supersession;
- quarantine with previous-current preservation;
- promotion-only current and incremental/full replay equality;
- DuckDB gate catalog and version-normalizing ABI;
- exact-SHA receipts for two unrelated required packages;
- bounded model-only package;
- responsibility-closure projection;
- expected-reason destructive proof;
- content-addressed Nix store readback.

## Final legacy inventory

The preserved historical capability is represented by 36 semantic responsibilities:
11 contracts/ledgers, 24 DuckDB gates, and one package-contract ABI. The inventory
is frozen at `tools/contract-modeling/production/legacy-inventory.json`; all 36 are
mapped and unexplained count is zero. The original archive and specs repository
commit remain provenance evidence, not runtime inputs or authority.

## Production CI placement

The accepted two-workflow topology is preserved:

- `gov-final-scope-purpose-join` is the only blocking merge-admission surface;
- `gov-canary` remains evidence-only observation.

The blocking gate verifies the accepted ADRS merge/digest, production policy,
final inventory, current package receipts, active legacy consumer count zero,
anti-reintroduction, and exact candidate identity.

## Closure

Before merge, the production receipt must retain `migrationComplete=false` and
require effect readback. After the admitted merge reaches `proposals`, the existing
push-only post-effect job binds written and observed SHA. That readback closes
Governance #153 with `migration_complete=true`.

The closure remains scoped to `selected-required-universe-v1`; it does not claim
all-repository enforcement, causal business support, or corporate-sale outcome.
