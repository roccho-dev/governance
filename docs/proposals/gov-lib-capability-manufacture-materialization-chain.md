# gov-lib capability manufacture materialization chain proposal

## Why

A repo should not appear in README projection without the upstream capability, manufacture, and materialization decisions that explain why it exists.

## Scope Purpose

This PR fixes the repo-existence explanation boundary. The local purpose is to connect repo responsibility to the upstream capability, manufacture decision, and materialization decision. The system purpose is to prevent repo-first explanations that hide why the repo exists. The transfer purpose is to let a buyer or maintainer trace a repo back to the capability it serves and the choice that made it a repo instead of another artifact or service.

## Direction

Add a resolver that joins capability, manufacture decision, and materialization decision records.

## Decision

gov-lib should emit a materialization chain for repoExplainView and diagnostics for missing, cyclic, conflicting, or non-repo materialization references.

## Boundary

The resolver joins accepted records. It does not decide manufacturing strategy, create repos, or render artifacts.

## Merge Gate

Implementation must fail when a repo responsibility points to no accepted repo materialization chain.
