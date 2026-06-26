# gov-lib self-application proposal

## Why

governance should prove the repoExplainView path against itself before downstream repos adopt it.

## Direction

Add a proposal for governance to generate its own repoExplainView and document model candidate using gov-lib boundaries.

## Decision
governance self-application should produce repoExplainView, source closure, diagnostics, and document model candidate for `roccho-dev/governance` without writing or uploading the final README artifact.

## Boundary

Self-application validates gov-lib projection only. Artifact writing and upload remain the consuming repository CI responsibility.

## Merge Gate

Implementation must show deterministic output and no Markdown bytes emitted by gov-lib.