# gov-lib repository responsibility v2 resolver proposal

## Why

repoExplainView needs exactly one active accepted repo responsibility for a target repo and scope.

## Direction

Add a resolver for `adrs.repoResponsibility.v2` records and migration compatibility with older responsibility rows.

## Decision

gov-lib should resolve active responsibility, owns, mustNotOwn, inputs, outputs, effects, audience, and lifecycle for each target repo.

## Boundary

The resolver does not create responsibility records and does not treat generated README artifacts as authority.

## Merge Gate

Implementation must fail if a target repo has zero active responsibilities or more than one active responsibility for the selected scope.