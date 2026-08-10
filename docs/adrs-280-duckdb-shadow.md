# ADRS #280 DuckDB shadow reducer/projector

Parent: `roccho-dev/adrs#280`.

## Purpose

Prove the provider-detached part of the proposed ADRS decision-event architecture:

```text
materialized fixture
  -> authorization results
  -> DuckDB deterministic reducer
  -> current ADR state
  -> accepted-decision projection
  -> gov input projection
```

The test boundary starts at a materialized fixture. Fetching a real GitHub Issue,
pagination, actor evidence collection, and Issue-to-fixture materialization are a
separate adapter/conformance implementation and are intentionally not tested by
this child PR.

## Authority boundary

This is shadow evidence only.

- `authority=false` for every generated projection;
- the reducer consumes authorization results but does not mint authority;
- this PR does not replace current ADRS Git records;
- this PR does not authorize #280, cutover, source-shard retirement, release
  replay retirement, merge-gate adoption, or Issue write-back;
- gov input is generated from reduced state and never reads GitHub directly.

Current accepted ADRS records remain authoritative until #280 has separate
acceptance, parity, migration, and cutover proof.

## Bounded lifecycle contract

The fixture reuses the `decisionEvent.v1` name requested by #280 and covers:

- `propose`;
- `amend` targeting the exact current candidate;
- `accept` targeting the exact current candidate;
- `reject` targeting the exact current candidate;
- `revoke` targeting the exact current accepted state;
- `supersede` targeting the exact current candidate while naming the exact
  accepted state being superseded.

State order comes only from explicit `predecessorDigest` links. Physical JSONL
row order and timestamps do not select a winner.

A branch from one predecessor is projected as `conflict`; candidate and accepted
state are withheld from gov admission rather than arbitrarily choosing a branch.
Unauthorized events remain visible input but do not change reduced state.

## Outputs

The SQL produces three deterministic JSONL projections:

- `adr.current.jsonl`;
- `accepted-decision.current.jsonl`;
- `gov-input.jsonl`.

`gov-input.v1.admissionAllowed` is true only for `accepted` and
`accepted-with-pending-amendment`. In the pending-amendment case, gov input keeps
using the previously accepted payload until an authorized exact-target accept or
supersede changes it.

## CI proof

`adrs-280-duckdb-shadow` installs the repository's existing pinned DuckDB version
from `tools/contract-modeling/requirements.txt` and runs
`tools/adrs-280-duckdb-shadow/verify.py`.

The check fails unless all of these hold:

1. DuckDB version equals the shared repository pin;
2. materialized fixture bytes match their pinned SHA-256 values;
3. actual reducer/projector outputs equal committed expected projections;
4. reversing physical JSONL row order produces byte-identical outputs;
5. an unauthorized accept leaves the ADR only proposed;
6. a branch is quarantined as conflict and cannot be admitted;
7. unknown kinds fail closed;
8. duplicate event identity fails closed;
9. missing authorization fails closed;
10. broken predecessor continuity fails closed;
11. stale exact-target acceptance fails closed;
12. provider metadata leaking into the semantic lane fails closed.

The receipt printed by the verifier is CI evidence only and cannot create ADRS
accepted meaning.
