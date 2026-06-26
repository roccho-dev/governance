# gov-lib negative fixtures proposal

## Why

Projection boundaries must be enforced by failing examples, not only prose.

## Scope Purpose

Projection QA should make every forbidden gov-lib path observable as a red fixture before downstream repos adopt README artifact generation.

This scope serves the full purpose chain by preventing hidden authority drift, renderer drift, and artifact ownership drift from becoming operational debt during later transfer or due diligence.

## Direction

Add negative fixtures for the README artifact projection path.

## Decision

gov-lib tests should cover direct raw authority input, missing accepted decision, stale bundle, active responsibility conflicts, audience leaks, missing source closure, missing nonAuthority marker, Markdown byte output from gov-lib, rendered README output from gov-lib, README write ownership by gov-lib, artifact upload ownership by gov-lib, downstream repository mutation ownership by gov-lib, downstream severity adoption by gov-lib, downstream exception adoption by gov-lib, local policy invention, and generated artifact authority claims.

Each fixture should fail for a named reason so a passing test proves the boundary, not only that an error occurred.

## Boundary

Negative fixtures prove gov-lib boundary behavior. They do not implement downstream repo CI, ui-lib rendering, artifact upload ownership, repository mutation ownership, or policy acceptance.

## Merge Gate

All listed negative fixtures must fail for the intended reason before projector implementation is considered complete. A forbidden gov-lib path must not be downgraded to a silent warning unless an accepted ADR-derived severity rule explicitly allows report-only behavior for that exact case.