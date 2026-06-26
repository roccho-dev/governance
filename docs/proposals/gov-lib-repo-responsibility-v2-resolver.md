# gov-lib repository responsibility v2 resolver proposal

## Why

repoExplainView needs exactly one active accepted repo responsibility for a target repo and scope.

## Scope Purpose

This PR fixes the repo responsibility resolver boundary. The local purpose is to resolve one active accepted `repoResponsibility.v2` record per target repo and selected scope. The system purpose is to prevent overlapping repo ownership, hidden effects, and README-as-authority drift. The transfer purpose is to let future DD and handoff checks prove what a repo owns, must not own, consumes, emits, and affects from accepted source records.

## Direction

Add a resolver for `adrs.repoResponsibility.v2` records and migration compatibility with older responsibility rows.

## Decision

gov-lib should resolve active responsibility, owns, mustNotOwn, inputs, outputs, effects, audience, and lifecycle for each target repo.

## Migration Compatibility

Older responsibility rows may be read only in an explicit migration mode. They must be read-only, diagnostics-producing inputs, not active authority. They must not override an accepted `repoResponsibility.v2` record, must not create new responsibility, and must be removed from the active path once accepted v2 bootstrap coverage exists.

## Boundary

The resolver does not create responsibility records and does not treat generated README artifacts as authority.

## Merge Gate

Implementation must fail if a target repo has zero active responsibilities or more than one active responsibility for the selected scope. Migration compatibility must fail if older rows are used without explicit migration mode or if they conflict with accepted v2 records.
