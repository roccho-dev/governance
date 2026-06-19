# policy.git Boundary Deletion Gates for Governance

Status: proposal only.

This proposal does not edit generated feat inputs and does not delete policy.git.

## Decision

Governance must treat policy.git deletion as a package-consumer cutover problem,
not as a documentation cleanup. Any package contract or feat input that still
requires policy.git, policy-master, or a policy repo source URI keeps the cutover
blocked.

## Governance Cutover Gates

| Gate | Required state before deletion |
|---|---|
| Consumer inventory | every governance record and generated feat input that mentions policy.git, policy-master, or repoId policy is inventoried. |
| Replacement authority | each live policy package has an accepted adrs/governance typed source or an accepted successor repo placement. |
| Build contract parity | generated build definitions still produce the required outputs and checks after replacing policy.git input. |
| Lock behavior | failed replacement projections do not update consumer locks. |
| Backward references | legacy references are either migrated, explicitly archived as evidence, or marked inactive. |
| Gate output | records-gate or an equivalent governance check reports zero active policy.git consumers before deletion. |

## Non-Goals

- Do not rewrite generated feat inputs by hand in this proposal.
- Do not delete accepted package contracts.
- Do not treat adrs raw rows as direct repo operation authority.
- Do not remove policy package responsibilities without accepted successor placement.

## Verification

This proposal is documentation-only. Verification for this branch is:

- governance flake checks pass.
- records gate remains executable.
- git diff whitespace check passes.

