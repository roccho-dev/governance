# e2e/nix-default-surface

This e2e surface documents the fixtures implied by `tools/check-nix-default-surface.py`.

It is not authority. ADRs decide the rule. Governance implements the check.

## Positive path

- `packages.default` is absent.
- `apps.default` and `apps.help` are the same help app.
- help mentions packages, apps, checks, devShells, the authority boundary, and explicit build, run, and check routes.
- help is deterministic stdout only.

## Negative paths covered by the checker

- `packages.default` appears in the package block.
- `apps.default` is not wired to `helpApp`.
- help omits required build, run, check, or default-policy fragments.
- help implies generated text is authority.
- help or check surface introduces hidden or remote behavior.

## Manual smoke expected after checkout

- `nix run .`
- `nix run .#help`
- `nix build .#bootstrap-input`
- `nix flake check`

`nix build .` should remain unsupported unless a later accepted ADR allows `packages.default`.
