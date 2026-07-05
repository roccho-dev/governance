# README materialization common checks for governance #144

## Purpose

Provide one governance-owned README materialization check that selected repos can import instead of copying repo-local comparison logic.

## Boundary

This is local materialization evidence only.

- README is not authority.
- Generated README artifacts are not authority.
- CI logs are not authority.
- This does not replace governance #81 README projection drift integration.
- This does not mutate branch protection or provider required checks.
- This does not auto-commit generated README output.

## Contract

A selected repo must do one of two things.

| mode | required evidence |
|---|---|
| `generated` | use the governance common materialization check and emit `readmeMaterializationReceipt.v1` |
| non-generated / not-ready | emit `readmeMaterializationResidual.v1` with owner, reason, nextAction, returnCondition, expiry |

## Adoption shape

Each repo should keep only a thin flake connection:

1. import `nix/readme-materialization-checks.nix` from the governance input;
2. pass its `readme-artifact` derivation and committed `README.md` path;
3. expose `checks.readme-materialized` or an explicit residual derivation;
4. keep repo convention and final join as separate checks.

## Final join relationship

This issue closes the selected-repo local README materialization gap. Final README projection enforcement remains under governance #81 / #131.
