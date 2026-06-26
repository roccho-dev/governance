# gov-lib negative fixtures proposal

## Why

Projection boundaries must be enforced by failing examples, not only prose.

## Direction

Add negative fixtures for the README artifact projection path.

## Decision

gov-lib tests should cover direct raw authority input, missing accepted decision, stale bundle, active responsibility conflicts, audience leaks, missing source closure, missing nonAuthority marker, and Markdown byte emission from gov-lib.

## Boundary

Negative fixtures prove gov-lib boundary behavior. They do not implement downstream repo CI or ui-lib rendering.

## Merge Gate

All listed negative fixtures must fail for the intended reason before projector implementation is considered complete.