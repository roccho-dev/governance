# Recursive contract-modeling admission

This tool implements the deterministic, non-authority compiler tracked by
`roccho-dev/governance#153` and specified by `roccho-dev/adrs#234`.

## Boundary

- ADRS owns accepted meaning, purpose paths, promotion policy, waivers, and cutover.
- Package and feature owners submit claims and evidence.
- Governance validates, reduces, derives, projects, and reports; it does not mint meaning.
- Ops or the owning repository performs effects and emits exact-target readback receipts.
- `spec` and `specs` are historical evidence only.

The current fixture pins accepted-decision candidate
`01K0E1CM000000000000000234`, release
`recursive-contract-modeling-v1.0.0`, and digest
`b72502f7845ead05f61d0640ef8b3f50789c7db0afafd3764b4c19d39a9fd4e0`.
Until the ADRS decision is merged and released, all outputs are shadow evidence and
cannot grant production admission or cutover authority.

## Data flow

```text
append-only claims
→ closed envelope validation
→ explicit supersession and recursive containment reduction
→ derived package/data-model admission
→ promotion-only current epoch
→ versioned DuckDB ABI and query contract checks
→ responsibility closure and exact-SHA receipts
```

## Implemented proof surface

- one closed common envelope;
- `package-contract-v1` and `data-model-v1` closed payload profiles;
- stable opaque subject identity with typed containment edges;
- no fixed semantic depth, with node/edge/byte safety caps;
- deterministic eight-way admission;
- conflicts quarantine while the previous current state remains active;
- all trusted decision values derived from claims and evidence;
- legacy migration ledger with no unexplained active row;
- promotion-only current state;
- byte-identical full replay and incremental evaluation;
- shared versioned ABI for compatible old/new rows;
- approved query contracts reject raw JSONL access;
- exact candidate SHA binding;
- two unrelated real package assertions;
- one bounded model-only package;
- destructive proof covering the ADRS rejection catalog.

## Run

```text
python3 -m unittest discover -s tools/contract-modeling/tests -p 'test_*.py'
CANDIDATE_SHA=$(git rev-parse HEAD) bash tools/contract-modeling/run-proof.sh
```

`run-proof.sh` requires the pinned Python dependencies, DuckDB, and Nix. It emits
only non-authority proof artifacts under `tools/contract-modeling/out/`.

## Closure ceiling

A green shadow result proves that this exact governance candidate implements the
accepted-candidate contract and can reproduce its proof packet. It does not prove:

- accepted ADRS merge/release readback;
- production required-check cutover;
- effect execution or readback outside the bounded fixture;
- active legacy consumer count zero in every external repository;
- business outcome achievement.

Those residuals remain explicit and block `migration_complete=true`.
