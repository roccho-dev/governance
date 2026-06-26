# gov-lib to ui document model bridge proposal

## Purpose lineage

This proposal serves the full chain: keep governance semantic, keep ui rendering independent, prevent renderer-side ADR joins, and make README production reproducible enough for handoff, due diligence, and company sale.

## Scope purpose

Viewpack scope is `repoExplainView.v1 -> document.model.v1 candidate`. The bridge prepares renderer-neutral structure only; it does not render or own artifacts.

## Why

gov-lib owns semantic projection and ui-lib owns Markdown rendering. A bridge keeps those responsibilities separate.

## Direction

Add a mapping from `repoExplainView.v1` to renderer-neutral `document.model.v1`.

## Decision

gov-lib should emit a document model candidate with section ids, block types, text, lists, key-value rows, and provenance references, but no Markdown bytes.

## Boundary

The bridge is a semantic-to-document-model transform. It must not render Markdown, upload artifacts, or mutate repositories.

## Done definition

The PR is complete when the bridge contract fixes deterministic document model output and makes Markdown rendering, artifact upload, and repository mutation explicitly impossible in gov-lib.

## Merge Gate

Implementation must prove that the same repoExplainView produces a deterministic document model digest.
