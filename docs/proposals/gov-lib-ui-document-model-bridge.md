# gov-lib to ui document model bridge proposal

## Why

gov-lib owns semantic projection and ui-lib owns Markdown rendering. A bridge keeps those responsibilities separate.

## Direction

Add a mapping from `repoExplainView.v1` to renderer-neutral `document.model.v1`.

## Decision

gov-lib should emit a document model candidate with section ids, block types, text, lists, key-value rows, and provenance references, but no Markdown bytes.

## Boundary

The bridge is a semantic-to-document-model transform. It must not render Markdown, upload artifacts, or mutate repositories.

## Merge Gate

Implementation must prove that the same repoExplainView produces a deterministic document model digest.