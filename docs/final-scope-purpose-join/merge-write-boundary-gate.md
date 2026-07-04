# Provider-neutral merge/write boundary gate

Parent: governance #125  
Phase issue: governance #115

## Purpose

This file documents the provider-neutral enforcement contract for the selected ref update boundary.

The selected ref must not move merely because CI or artifact exporters are green. The final gate must accept the exact target SHA before an enforcement provider may update the selected ref.

Required final gate name:

```text
gov-final-scope-purpose-join / gate
```

Selected ref in the current fixture set:

```text
refs/heads/proposals
```

## Enforcement providers

Any provider is acceptable when it calls the same decision rule before updating the selected ref:

- GitHub ruleset / branch protection;
- self-hosted server-side hook;
- merge daemon;
- bot-only merge path;
- SSOT publish gate.

Human convention, PR comments, artifact upload success, shadow report success, and old CI success are not enforcement providers.

## Decision rule

An update is allowed only when all of the following are true:

1. target ref equals the selected ref;
2. target SHA is the exact SHA accepted by the final gate;
3. final gate name equals `gov-final-scope-purpose-join / gate`;
4. final gate status is `pass`;
5. final gate output digest is present;
6. the enforcement point is one of the accepted providers;
7. the attempt emits an audit receipt.

All other attempts are rejected.

## Proof artifacts

- `merge-write-boundary-cases.jsonl` defines the accepted/rejected fixture matrix.
- `merge-write-boundary-proof.json` is the checked proof artifact.
- `tools/check-merge-write-boundary-final-gate.py selftest` verifies the fixture decisions and audit receipts.
- `tools/check-package-final-scope-purpose-join.py selftest` invokes the merge/write boundary selftest as part of the final gate adapter surface.

## Boundary

This proof is provider-neutral. It does not mutate a GitHub ruleset by itself and does not make governance meaning authority.

It is sufficient merge-quality evidence for the gate rule implementation, but #115 should close only when the chosen provider path is accepted as the active selected ref boundary or when this PR is intentionally accepted as that provider path.
