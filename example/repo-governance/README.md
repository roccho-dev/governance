# example/repo-governance

This directory is for minimal examples that explain how `repo-governance` is intended to be consumed.

It is not authority, not evidence, and not a gating surface in V1.

## Goal

Show the smallest input and output shape for the package strategy without introducing runtime behavior.

## Expected future example

Input:

- accepted ADR bundle fixture
- explicit repo snapshot fixture

Output:

- repo contract
- package contracts
- violations
- generated README block
- migration plan

## Boundary

Examples must not define new rules. If an example needs a rule that is not in the ADR-derived contract, the rule must be proposed in `adrs` first.
