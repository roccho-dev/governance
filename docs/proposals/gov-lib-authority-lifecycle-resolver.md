# gov-lib authority lifecycle resolver proposal

## Why

CUE pass, CI green, PR merge, and latest rows must not be treated as accepted authority.

## Scope Purpose

This PR fixes the resolver authority boundary. The local purpose is to compute active accepted records from accepted inputs without accepting anything itself. The system purpose is to prevent validation, recency, CI success, or generated artifacts from becoming authority. The transfer purpose is to let a later reviewer see why a record is active, pending, superseded, stale, or conflicting without trusting conversation history.

## Direction

Add a resolver that computes active accepted records from accepted projection bundles, supersedes links, delegation, lifecycle state, and observed scope.

## Decision

gov-lib should expose resolved active records and diagnostics for pending, deprecated, superseded, conflicting, or stale records.

## Boundary

The resolver computes a read model. It does not grant authority, accept proposals, mutate repos, render Markdown, or upload artifacts.

## Merge Gate

Implementation must fail closed when validated records are present without accepted decision authority.
