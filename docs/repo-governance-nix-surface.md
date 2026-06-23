# repo-governance Nix surface

## Goal

Expose `repo-governance` so feature repos can consume the governance checker through a pinned flake input rather than copying local scripts or rule logic.

## Consumer contract

A feature repo should need only:

1. a `governance` flake input;
2. one call to `governance.lib.mkRepoGovernanceChecks`;
3. one explicit `governance/repo-governance.json` repo snapshot.

## Provided outputs

- `packages.<system>.repo-governance`
- `apps.<system>.repo-governance`
- `lib.mkRepoGovernanceCheck`
- `lib.mkRepoGovernanceChecks`
- `checks.<system>.repo-governance-proof`
- `checks.<system>.repo-governance-self`
- `checks.<system>.repo-governance-feat-consumer-example`

## Example consumer

See `example/feat-consumer`.

Its check is intentionally small: it does not implement governance rules. It imports the governance flake and asks governance to produce the check.

## Boundary

- `adrs` owns rule meaning.
- `governance` owns the non-authority implementation and Nix distribution surface.
- feature repos own their own `governance/repo-governance.json` snapshot.
- generated outputs are not authority.
- this PR does not add a source scanner.
