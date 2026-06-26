# gov-lib source closure and diagnostics proposal

## Purpose lineage

This proposal serves the full chain: make every rendered or transferred explanation traceable, keep README artifacts non-authority, expose missing / stale / forbidden states early, and reduce handoff risk for due diligence and company sale.

## Scope purpose

Viewpack scope is `repoExplainView.v1 -> source-closure.jsonl + diagnostics.jsonl`. These files explain where the view came from and why it is safe or unsafe to consume.

## Why

Repo artifacts need traceability back to source decisions and clear diagnostics for missing, stale, unknown, or forbidden states.

## Direction

Add source closure and diagnostics outputs beside repoExplainView.

## Decision

gov-lib should emit `source-closure.jsonl` and `diagnostics.jsonl` with deterministic digests, source references, severity, finding code, target, and provenance.

## Boundary

Diagnostics are evidence and checks, not authority decisions. Source closure is provenance, not a replacement for accepted ADR records.

## Done definition

The PR is complete when source closure and diagnostics are required beside the viewpack, ordered deterministically, and unable to replace accepted ADR authority.

## Merge Gate

Implementation must include stable finding codes and deterministic output ordering.
