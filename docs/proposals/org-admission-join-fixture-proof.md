# Organization admission join fixture proof proposal

## Why

The design is only credible if it proves both pass and fail behavior in CI.

## Decision

Add fixture-backed proof for:

1. upstream grant + downstream assertion + receipt -> `organization-active`
2. missing downstream assertion -> `unclaimed-grant`
3. missing upstream grant -> `orphan-assertion`
4. missing receipt -> `asserted-but-unproven`
5. stale receipt or digest mismatch -> `stale-assertion`
6. blocking subject in official view -> gate fail

## CI

`nix flake check` must run:

1. port fixture validation
2. join compiler
3. existing organization admission gate

## Boundary

This PR does not roll out to real repos.
It proves the model with checked-in fixtures only.
