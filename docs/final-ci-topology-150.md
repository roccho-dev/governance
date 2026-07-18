# Governance #150 final organization CI topology

## Accepted source

ADRS #233 is accepted through merge `a8fc9e8e04d53f1d783317059e4421c8dc724d01`.

- decision: `01K0D7C3A00000000000000233`
- release: `final-organization-ci-topology-v1.0.0`
- contract digest: `8106d85404e636a9797dfb8e0a1f6343db8a7867ff904577f682e5d82ad9b314`
- stable required check: `gov-final-scope-purpose-join / gate`
- rollout: governance, UI, and Ops only
- `allRepositoriesEnforced=false`

ADRS owns accepted meaning. Governance projects and enforces that exact accepted decision but cannot change its meaning.

## Final provider topology

| Workflow | Trigger | Authority class | Responsibility |
|---|---|---|---|
| `gov-final-scope-purpose-join` | pull request, push to `proposals`, manual | merge-admission | exact candidate capture, complete regression, accepted decision join, selected-repository admission, final evidence, push readback |
| `gov-canary` | schedule, manual | evidence-only | ADRS source drift, GitHub App read capacity, topology and lifecycle observation |

Exactly one job has the stable check identity `gov-final-scope-purpose-join / gate`.
The canary cannot admit a merge or perform an effect.

## Gate equation

```text
accepted ADRS #233 decision
+ exact governance candidate SHA
+ complete governance regression
+ governance self assertion and receipt
+ merged UI positive-consumer assertion and exact-head receipt
+ merged Ops migration-consumer assertion and exact-head receipt
+ claim-port classification = organization-active for all selected repositories
= allow | block
```

Missing, stale, malformed, revoked, cross-repository, or wrong-SHA inputs block.
Technical success never implies all-repository enforcement or a business outcome.

## Security boundary

- every candidate checkout names the exact PR head or pushed SHA;
- checkout credentials are never persisted;
- the required gate receives no write secret;
- candidate code does not share a job with ADRS App credentials;
- ADRS live observation is isolated in the scheduled read-only canary;
- post-effect is push-only and records the exact written and observed SHA;
- artifacts and receipts are evidence, not accepted meaning.

## Migration closure

The former twelve workflows were reduced to the two accepted surfaces only after:

1. responsibility transfer was represented in the accepted ADRS contract;
2. the existing regression commands were retained by the final gate or canary;
3. UI and Ops selected-consumer receipts were independently green;
4. the stable check name was preserved;
5. the ruleset plan was corrected from `main` and the legacy check to `proposals` and the stable final check;
6. the deletion checker required no workflow, CI-intent, ruleset-plan, or selected-consumer residual.

The exact consumer heads, merge commits, run IDs, and artifact digests are bound in `governance/selected-final-ci-rollout.v1.json`.

## Closure boundary

This implementation closes the accepted governance/UI/Ops rollout only.
It does not claim:

- every repository is governed;
- every code property is statically observable;
- CI completion creates buyer value by itself;
- the corporate-sale outcome has occurred.

Rollback restores the last accepted topology and exact accepted source/engine identities; it does not infer an implicit latest state.
