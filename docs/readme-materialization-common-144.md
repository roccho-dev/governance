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
- This does not claim selected-repo rollout completion.

## Contract

A selected repo must do one of two things.

| mode | required evidence | common surface |
|---|---|---|
| `generated` | `readmeMaterializationReceipt.v1` | `mkReadmeMaterializedCheck` |
| non-generated / not-ready | `readmeMaterializationResidual.v1` with owner, reason, nextAction, returnCondition, expiry | `mkReadmeMaterializationResidual` |

`mkReadmeMaterializedCheck` is only for generated mode. Passing a non-generated mode to that surface is a failure; a non-generated repo must use the explicit residual surface instead.

## Adoption shape

Each repo should keep only a thin flake connection:

1. import `nix/readme-materialization-checks.nix` from the governance input;
2. pass its `readme-artifact` derivation and committed `README.md` path;
3. expose `checks.readme-materialized` or an explicit residual derivation;
4. keep repo convention and final join as separate checks.

## Proof added by governance #145

| proof | checks |
|---|---|
| `tools/check-readme-materialization.py selftest` | generated pass, generated drift failure, wrong-surface failure, explicit residual |
| `checks.readme-materialization-common-selftest` | same destructive proof under Nix |
| `checks.readme-materialization-generated-fixture` | exported Nix function emits a `readmeMaterializationReceipt.v1` for byte-identical generated/committed README |
| `checks.readme-materialization-residual-fixture` | exported Nix function emits a complete `readmeMaterializationResidual.v1` for not-ready mode |
| CI named steps | runs the Python selftest and each Nix proof surface |

## Finding / receipt shape

Generated mode success emits `receipt.json`.

Required fields:

- `kind=readmeMaterializationReceipt.v1`
- `repoId`
- `status=pass`
- `mode=generated`
- `artifactDigest`
- `committedDigest`
- `producerRepo`
- `generatedBy`
- `authority=false`
- `nonAuthority=true`

Generated mode drift emits `finding.json` and exits non-zero.

Required fields:

- `kind=readmeMaterializationFinding.v1`
- `diagnosticClass=readme-materialization-drift`
- `expected`
- `actual`
- `artifactDigest`
- `committedDigest`
- `delta`
- `nextAction`
- `authority=false`
- `nonAuthority=true`

Residual mode emits `residual.json`.

Required fields:

- `kind=readmeMaterializationResidual.v1`
- `repoId`
- `mode`
- `owner`
- `reason`
- `nextAction`
- `returnCondition`
- `expires`
- `authority=false`
- `nonAuthority=true`

## Final join relationship

This PR closes only the common selected-repo local README materialization check distribution gap. Final README projection enforcement remains under governance #81 / #131.

The output of this check is future final-join evidence, not merge authority by itself.
