# Policy Consumer Cutover Graph

Status: proposal only.

This proposal does not edit generated feat inputs and does not delete policy.git.

## Decision

Governance must make policy.git retirement a graph of package and build
consumer edges. A package remains blocked while any accepted contract, generated
feat input, lock, or build route requires policy.git as live source authority.

## Governance Consumer Edges

| Edge | Required behavior |
|---|---|
| package-to-policy-source | every package that depends on policy rules names the accepted replacement authority |
| feat-input-to-governance-function | feat-local builds use governance functions plus local raw JSONL, not policy.git |
| lock-to-input | successful builds may update locks; failed projections do not update locks |
| stale-policy-ref | legacy policy.git refs are migrated, archived inactive, or reported as blockers |
| build-contract-parity | replacement inputs preserve required outputs and checks |

## Completion Inputs

Governance may report its side green only when:

- active policy.git consumer references are zero;
- generated feat inputs are reproducible from accepted records;
- broken adrs/governance projections fail without updating locks;
- package contracts preserve goal/no-goal and build semantics;
- fresh-agent tests can explain the same consumer graph from accepted entries.

## Non-Goals

- Do not rewrite generated feat inputs by hand.
- Do not make adrs raw rows direct repo operation authority.
- Do not remove package responsibilities without successor placement.
- Do not approve repo-boundary deletion from governance alone.

## Verification

Documentation-only proposal verification:

- governance flake check passes.
- git diff whitespace check passes.

