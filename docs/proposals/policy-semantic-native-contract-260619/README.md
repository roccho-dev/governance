# Policy Semantic Native Contract

Status: proposal only.

This proposal records Codex readback of the ChatGPT proposal
`policy-semantic-authority-closure-260619`. It does not implement cutover,
consumer migration, or deletion.

## Review Decision

Adopt with corrections as the next sequencing target. Governance should define
the package and projection contracts for a policy semantic compiler candidate,
but it must not mark any consumer migrated or any cutover gate green until repo
changes and executable evidence exist.

## Corrected Target

The repo target is `governance`. The existing authority label
`governance-records-main` may remain inside records, but `governance-records`
is not a separate repo target in this proposal.

## Proposed Contract Surface

| Surface | Required proposal content |
|---|---|
| `records/specs/package-contract.v1.jsonl` | planned `policy-semantic-compiler` package contract |
| `records/specs/policy-semantic-projection-contract.v1.jsonl` | required native outputs and graph trace requirements |
| `generated/feat-inputs/policy-semantic-compiler.json` | generated candidate input after accepted package contract, not hand authority |
| native policy records | `policy.definition.v1`, `policy.activation.v1`, `policy.obligation.v1`, `policy.deny.v1`, `policy.superseded.v1` |
| native role records | `role.binding.v1`, `role.exit-edge.v1` |

## Required Boundaries

- `policy.sourceSpan.v1` is the current span family. Do not introduce
  `policy.semanticSpan.v1` as a second authority.
- Every native output row must trace back through `policy.projectionEdge.v1` to
  a semantic node and exact source span.
- The 63 legacy role rows must be derived from current semantic records, not
  copied or hand-edited.
- `consumerEdge` rows may inventory old policy.git consumers, but they may not
  be marked migrated without consumer diffs and executable checks.

## Gates

| Gate | Governance candidate status |
|---|---|
| control-plane-native-record-types | addressed only after schema-valid native records exist |
| legacy-role-projection-refresh | addressed only after derived role projection matches current head |
| old-policy-repo-consumers-zero | remains blocked |
| nix-consumer-cutover | remains blocked |
| deletion approval | forbidden |

## Reject If

- Counts are hardcoded from old evidence instead of recomputed.
- Generated feat inputs are edited as authority.
- `policy.git` consumers are marked migrated without repo changes.
- Proposal rows are labeled accepted by the implementing actor.

