# gov-lib scope goal and no-goal resolver proposal

## Why

README views need direct and inherited goals without duplicating company or product goals in each repo.

## Direction

Add a resolver for scoped `goal` and `noGoal` records from accepted projection bundles.

## Decision

gov-lib should output direct goals, inherited goals, direct no-goals, inherited no-goals, and diagnostics for cycles, missing roots, or audience leaks.

## Boundary

This resolver does not decide goals. It only resolves accepted ADR-derived records.

## Merge Gate

Implementation must fail on scope cycles, missing roots, or internal records selected for public output.