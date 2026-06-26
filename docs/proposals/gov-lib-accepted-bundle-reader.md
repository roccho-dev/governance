# gov-lib accepted projection bundle reader proposal

## Why

gov-lib must not read raw ADR rows as final README meaning. It should consume accepted projection bundles defined by adrs.

## Direction

Add a reader surface for `adrs.acceptedProjectionBundle.v1` and reject direct raw-input operation for README artifact projection.

## Decision

The reader should require bundle id, scope, source closure, accepted decision refs, source digests, and projector compatibility metadata.

## Boundary

This proposal only defines the reader boundary. It does not implement authority resolution, Markdown rendering, or artifact upload.

## Merge Gate

Implementation must fail on pending decisions, missing source closure, missing projector compatibility, or direct raw-row authority input.