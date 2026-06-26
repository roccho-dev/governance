# gov-lib repoExplainView validator proposal

## Why

A repoExplainView can only be consumed safely if required fields, audience rules, freshness, and non-authority provenance are checked before rendering.

## Scope Purpose

Projection QA should make the semantic view safe for downstream rendering by failing closed before any README, artifact, or repository side effect can be implied.

This scope serves the full purpose chain by keeping governance a deterministic non-authority projection layer, keeping renderer and artifact ownership outside gov-lib, and making the output transferable without hidden maintainer judgment.

## Direction

Add a validator for `repoExplainView.v1` output.

## Decision

gov-lib should validate repo identity, source closure, nonAuthority marker, materialization chain, goals, no-goals, responsibility, diagnostics, audience, and projector version.

The validator should also reject forbidden view fields or side-effect claims, including Markdown bytes, rendered README content, artifact upload instructions, README write instructions, repository mutation requests, authority decisions, downstream severity adoption, and downstream exception adoption.

## Boundary

The validator checks semantic view integrity. It does not render Markdown, write README files, upload artifacts, mutate repositories, or decide whether the repository should merge a change.

## Merge Gate

Implementation must fail on missing nonAuthority marker, missing source closure, unknown required field, stale bundle, audience leak, forbidden Markdown output field, forbidden artifact lifecycle field, forbidden repository mutation field, or any field that presents repoExplainView as authority.