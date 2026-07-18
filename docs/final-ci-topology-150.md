# Governance #150 final organization CI topology

## Current status

The earlier completed closure was withdrawn on 2026-07-18 after independent review found that the gate validated checked-in claims about UI/Ops receipts rather than downloading and validating the receipt artifacts themselves. Governance #150 and ADRS #233 are reopened until live receipt binding, continuing canary observation, and the selected control-plane boundary are proved.

## Accepted source

ADRS #233 is accepted through merge `a8fc9e8e04d53f1d783317059e4421c8dc724d01`.

- decision: `01K0D7C3A00000000000000233`
- release: `final-organization-ci-topology-v1.0.0`
- contract digest: `8106d85404e636a9797dfb8e0a1f6343db8a7867ff904577f682e5d82ad9b314`
- stable check identity: `gov-final-scope-purpose-join / gate`
- selected rollout: governance, UI, and Ops only
- `allRepositoriesEnforced=false`

ADRS owns accepted meaning. Governance projects and evaluates that exact accepted decision but cannot change its meaning.

## Provider topology

| Workflow | Trigger | Authority class | Responsibility |
|---|---|---|---|
| `gov-final-scope-purpose-join` | pull request, push to `proposals`, manual | merge-admission | accepted-source capture, live UI/Ops claim and receipt-artifact capture, complete regression, candidate-bound admission, final evidence, push readback |
| `gov-canary` | schedule, manual | evidence-only | ADRS source and Issue observation, live UI/Ops head/claim/run/artifact freshness, adapter drift, active ruleset and required-check exclusivity |

The canary cannot admit a merge or perform an effect.

## Live receipt equation

```text
current UI/Ops proposals head
+ current claim file fetched at that exact head
+ successful push workflow run whose head_sha equals that head
+ non-expired final-ci-consumer-receipt artifact from that run
+ downloaded artifact ZIP digest equal to GitHub artifact metadata digest
+ receipt body candidateSha equal to the current head
+ receipt repository, assertion, bundle, closure, role, and authority boundaries
+ candidate-bound claim-port admission
= organization-active | block
```

The checked-in rollout file contains only expected contracts and paths. It must not contain live candidate heads, merge commits, run IDs, artifact digests, or pass status as substitutes for current readback.

Missing, stale, malformed, revoked, cross-repository, wrong-run, wrong-artifact, or wrong-SHA inputs block.

## Canary equation

Each scheduled/manual canary run must freshly observe:

1. UI and Ops current default-branch heads;
2. their claim files at those exact heads;
3. successful push runs bound to the exact heads;
4. receipt artifact existence, expiry, metadata digest, ZIP bytes, and receipt body;
5. generated adapter and accepted-decision identities;
6. governance workflow intent at the current governance head;
7. active branch rulesets applying to `proposals`;
8. pull-request enforcement, bypass actors, legacy checks, duplicate checks, and exclusivity of `gov-final-scope-purpose-join / gate`;
9. ADRS Git and Issue transport observations.

A static topology selftest or old green artifact cannot satisfy these observations.

## Control-plane boundary

A successful expected-head merge proves one bounded publish effect only. It does not prove a permanent exclusive merge path.

`permanentMergePathProven=true` is permitted only after live ruleset readback proves all of:

- an active ruleset applies to `proposals`;
- pull requests are required;
- bypass actors are absent for the selected boundary;
- the stable final check occurs exactly once;
- no other required status check or legacy final-green interpretation is active.

If the GitHub provider cannot expose this information, the control-plane observation fails closed and #150 remains open.

## Security boundary

- candidate checkouts name the exact PR head or pushed SHA;
- checkout credentials are not persisted;
- candidate code does not share a job with ADRS App credentials;
- artifact and ruleset reads are read-only;
- receipts and artifacts are evidence, not accepted meaning;
- post-effect readback records an exact written and observed SHA but does not establish future exclusivity;
- technical success never implies all-repository enforcement or a business outcome.

## Migration state

The former twelve provider workflow files were reduced to two. This file-count result is retained, but closure depends on the live evidence equations above, not on the number two by itself.

The previous statement that exact consumer heads, run IDs, and artifact digests were authoritatively bound in `governance/selected-final-ci-rollout.v1.json` is withdrawn. That file now declares expectations only; current evidence must be fetched from GitHub on each gate/canary run.

## Closure boundary

Governance #150 may close only after:

- exact-head gate execution downloads and validates live UI/Ops artifact bodies;
- candidate SHA equality survives the final claim-port join;
- canary live consumer observation succeeds;
- control-plane ruleset/required-check observation succeeds or an accepted correction explicitly changes that closure requirement;
- post-effect readback is recorded without claiming more than the observed effect.

This remains a governance/UI/Ops selected rollout. It does not claim every repository is governed, every property is observable, buyer value is created, or the corporate-sale outcome has occurred.
