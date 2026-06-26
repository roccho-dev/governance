# gov-lib source closure and diagnostics proposal

## Why

Repo artifacts need traceability back to source decisions and clear diagnostics for missing, stale, unknown, or forbidden states.

## Direction

Add source closure and diagnostics outputs beside repoExplainView.

## Decision

gov-lib should emit `source-closure.jsonl` and `diagnostics.jsonl` with deterministic digests, source references, severity, finding code, target, and provenance.

## Boundary

Diagnostics are evidence and checks, not authority decisions. Source closure is provenance, not a replacement for accepted ADR records.

## Merge Gate

Implementation must include stable finding codes and deterministic output ordering.