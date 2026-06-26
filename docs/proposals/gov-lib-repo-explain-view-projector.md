# gov-lib repoExplainView projector proposal

## Why

README generation needs a resolved semantic viewpack, not raw ADR rows or renderer-side joins.

## Direction

Add a projector that combines accepted bundle reading, authority lifecycle resolution, scope goal resolution, materialization chain resolution, and responsibility resolution into `repoExplainView.v1`.

## Decision

gov-lib should emit repo identity, materialization chain, direct and inherited goals, no-goals, responsibility, provenance, source closure digest, and diagnostics summary.

## Boundary

The projector emits semantic data only. It does not emit Markdown bytes, upload artifacts, or mutate repositories.

## Merge Gate

Implementation must produce deterministic output and include source closure and projector provenance.