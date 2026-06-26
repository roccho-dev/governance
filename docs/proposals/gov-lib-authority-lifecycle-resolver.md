# gov-lib authority lifecycle resolver proposal

## Why

CUE pass, CI green, PR merge, and latest rows must not be treated as accepted authority.

## Direction

Add a resolver that computes active accepted records from accepted projection bundles, supersedes links, delegation, lifecycle state, and observed scope.

## Decision

gov-lib should expose resolved active records and diagnostics for pending, deprecated, superseded, conflicting, or stale records.

## Boundary

The resolver computes a read model. It does not grant authority, accept proposals, mutate repos, render Markdown, or upload artifacts.

## Merge Gate

Implementation must fail closed when validated records are present without accepted decision authority.