# Provider-detached code-governance fixture

This directory implements the bounded, non-authority proof tracked by governance#148.

## Boundary

- The semantic ledger lives only in append-only source comments on `roccho-dev/adrs#231`.
- Git contains the engine, adapters, closed schema, destructive tests, Go fixtures, and Nix materializer only.
- Provider metadata is emitted only as transport receipts.
- The engine consumes canonical ledger and sealed tree files and has no provider imports.
- Nix reads only the provider-neutral semantic packet.
- No merge, ref, ruleset, or target-repository write is performed.

## Data flow

```text
ADRS source comments -> provider adapter -> ledger.jsonl
local/Git locator    -> source adapter   -> sealed snapshot
ledger + snapshot    -> engine           -> semantic packet
semantic packet      -> Nix              -> byte-identical store object
```

A plain JSONL adapter and local/Git source adapters prove that the engine is not tied to GitHub.

## Run

Required versions for the fixture digest are Python 3.13.5, Go 1.23.2,
`ast-grep-py==0.44.1`, and `jsonschema==4.26.0`.

```text
ADRS_TOKEN=<read-only token> tools/code-governance/run-live-proof.sh
```

The token is used only by the provider adapter to read `adrs#231` comments.
