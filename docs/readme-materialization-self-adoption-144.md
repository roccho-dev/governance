# Governance README materialization self adoption for #144

## Purpose

Use the same README materialization common checker in governance that governance distributes to selected repos.

## Implemented state

- governance keeps its README artifact producer.
- governance imports the common `nix/readme-materialization-checks.nix` surface from governance #145.
- governance exposes `checks.<system>.readme-materialization-self-residual`.
- the residual row is `readmeMaterializationResidual.v1` with owner, reason, nextAction, returnCondition, expiry, and non-authority boundary.
- README remains checked non-authority evidence.

## Why residual, not generated-mode receipt

The current committed root `README.md` is the active ADRS projection and boundary document. The existing `packages.<system>.readme-artifact` emits a README artifact packet, but that artifact is not yet byte-identical to the committed root README.

Using `mkReadmeMaterializedCheck` now would correctly fail with `readme-materialization-drift`. This PR therefore records the bounded governance self residual instead of pretending generated mode is complete.

## Return condition

Switch governance from residual to generated materialization only when:

- `packages.<system>.readme-artifact/README.md` and committed `README.md` are byte-identical;
- the non-authority README boundary remains present;
- the change still does not claim final README projection compliance outside governance #81 / #131.

## Boundary

No branch protection mutation. No final README projection compliance claim. No README authority claim.

Refs: #144, #145, #131, #81
