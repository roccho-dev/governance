# gov-lib self-application proposal

## Why

governance should prove the repoExplainView path against itself before downstream repos adopt it.

## Scope Purpose

Self-application should prove that governance can consume its own accepted projection input and produce only semantic, non-authority outputs.

This scope serves the full purpose chain by turning governance into a checked reusable component without making it the README owner, artifact owner, renderer, or repo mutator.

## Direction

Add a proposal for governance to generate its own repoExplainView and document model candidate using gov-lib boundaries.

Self-application depends on the accepted bundle reader, active record resolvers, repoExplainView projector, validator, and negative fixtures. It should run after the validator and negative fixture proposals are satisfied.

## Decision

governance self-application should produce repoExplainView, source closure, diagnostics, and document model candidate for `roccho-dev/governance` without writing README.md, emitting Markdown bytes, uploading the final README artifact, mutating repositories, or deciding downstream adoption.

## Boundary

Self-application validates gov-lib projection only. Artifact writing and upload remain the consuming repository CI responsibility.

## Merge Gate

Implementation must show deterministic output, accepted-bundle input use, validator pass, negative fixture coverage, and no Markdown bytes emitted by gov-lib. It must also show that README writing, artifact upload, repository mutation, and downstream adoption decisions remain outside governance self-application.