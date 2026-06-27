# Repo convention CI branch intent rule proposal

## Why

Repo convention already checks declared workflows and primary Nix entrypoints. It should also compare declared push branch intent with checked-in workflow YAML so active-line drift is visible.

## Decision

Add optional CI intent fields:

- `pushBranches`
- `activeBranch`

The repo convention check should compare those fields with checked-in workflow YAML and report mismatches.

## Boundary

This is a checked-file consistency rule only. It does not decide authority or perform provider mutations.
