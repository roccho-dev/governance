# gov-lib repoExplainView projector proposal

## Purpose lineage

This proposal serves the full chain: remove raw-to-README drift, keep gov/ui/repo CI responsibilities separate, produce a deterministic semantic view, make repository responsibility explainable without the original owner, and improve transfer / due-diligence readiness for a higher-value company exit.

## Scope purpose

Viewpack scope is `accepted bundle + resolved records -> repoExplainView.v1`. The output is a non-authority semantic viewpack for later rendering and artifact ownership by other layers.

## Why

README generation needs a resolved semantic viewpack, not raw ADR rows or renderer-side joins.

## Direction

Add a projector that combines accepted bundle reading, authority lifecycle resolution, scope goal resolution, materialization chain resolution, and responsibility resolution into `repoExplainView.v1`.

## Decision

gov-lib should emit repo identity, materialization chain, direct and inherited goals, no-goals, responsibility, provenance, source closure digest, and diagnostics summary.

## Boundary

The projector emits semantic data only. It does not emit Markdown bytes, upload artifacts, or mutate repositories.

## Done definition

The PR is complete when the proposal fixes the output contract, keeps Viewpack non-authority, and makes deterministic source closure / projector provenance mandatory for implementation.

## Merge Gate

Implementation must produce deterministic output and include source closure and projector provenance.
