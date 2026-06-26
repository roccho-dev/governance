# gov-lib repoExplainView validator proposal

## Why

A repoExplainView can only be consumed safely if required fields, audience rules, freshness, and non-authority provenance are checked before rendering.

## Direction

Add a validator for `repoExplainView.v1` output.

## Decision

gov-lib should validate repo identity, source closure, nonAuthority marker, materialization chain, goals, no-goals, responsibility, diagnostics, audience, and projector version.

## Boundary

The validator checks semantic view integrity. It does not render Markdown or decide whether the repository should merge a change.

## Merge Gate

Implementation must fail on missing nonAuthority marker, missing source closure, unknown required field, stale bundle, or audience leak.