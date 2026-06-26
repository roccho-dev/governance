# gov-lib capability manufacture materialization chain proposal

## Why

A repo should not appear in README projection without the upstream capability, manufacture, and materialization decisions that explain why it exists.

## Direction

Add a resolver that joins capability, manufacture decision, and materialization decision records.

## Decision

gov-lib should emit a materialization chain for repoExplainView and diagnostics for missing, cyclic, conflicting, or non-repo materialization references.

## Boundary

The resolver joins accepted records. It does not decide manufacturing strategy, create repos, or render artifacts.

## Merge Gate

Implementation must fail when a repo responsibility points to no accepted repo materialization chain.