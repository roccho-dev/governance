# e2e/repo-governance

This directory is for proof-only adapters and fixtures around `repo-governance`.

It is not an authority source and is not a reusable package in V1.

## Goal

Prove the package strategy can fail closed before the actual implementation becomes blocking.

## Required future fixtures

- valid minimal repo contract passes
- core reading adapter-only input fails
- adapter defining rule semantics fails
- generated README treated as authority fails
- hidden input changes digest fails
- same input produces same digest
- base accepted package removed at head fails

## Promotion rule

This surface may become a package only if it later gains an independent port, independent consumer, separate version cadence, and no duplicated shared model.
