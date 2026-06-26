# Seed repo note proposal

## Why

The governance repository needs a small repo-owned note that points back to the accepted ADR records it follows.

## Direction

Add a proposal for a governance-owned seed repo note. The note should identify governance as projection and check surface, not accepted meaning authority and not artifact lifecycle owner.

## Decision

A later implementation may include a repo-owned note beside the README artifact packet. For governance, the note should say that governance resolves accepted inputs and emits non-authority outputs.

## Boundary

This proposal is documentation only. It does not change artifact packet shape, CI, branch protection, or runtime behavior.

## Merge Gate

Merge only if governance remains projection and check surface rather than accepted meaning source.
