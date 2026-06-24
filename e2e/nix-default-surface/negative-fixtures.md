# Negative fixtures

The checker must reject these future regressions:

- an implicit package default is introduced;
- default run app no longer points to help;
- help omits the public flake surface;
- help presents generated text as decision authority;
- help depends on non-explicit state.

The current branch implements these as source and help-output checks in `tools/check-nix-default-surface.py`.
