# Repo convention CI branch intent rule proposal

## Why

Repo convention already checks declared workflows and primary Nix entrypoints. It should also compare declared push branch intent with checked-in workflow YAML so active-line drift is visible.

## Decision

Add a checked sidecar `ci.branch-intent.v1.jsonl` with:

- workflow `path`
- `activeBranch`
- `pushBranches`

Extend `tools/check-repo-convention.py` so repo convention checks compare that declared branch intent with checked-in workflow YAML.

This PR also moves `.github/workflows/ci.yml` push trigger from `main` to `proposals`, matching the active line.

## Boundary

This is a checked-file consistency rule only. It does not decide authority, mutate branch protection, or call provider APIs.

## Merge gate

`nix flake check` must include repo convention selftest and reject branch-intent mismatches through `tools/check-repo-convention.py`.
