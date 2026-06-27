# Claim drift classification proposal

## Why

The organization admission result says whether a subject is active or blocked. Operators and agents also need to know which side is lagging.

## Decision

Add `diagnosticClass` to `governance.organizationAdmission.v1` rows emitted by the claim port join compiler.

| admissionResult | diagnosticClass | meaning |
|---|---|---|
| `organization-active` | `organization-active` | grant, downstream claim, and receipt match |
| `unclaimed-grant` | `feat-lagging-adrs` | ADRS-derived grant exists but downstream feat claim is missing |
| `orphan-assertion` | `adrs-lagging-feat` | downstream feat claim exists but upstream grant is missing |
| `asserted-but-unproven` | `claim-unproven` | grant and claim exist but receipt is missing |
| `stale-assertion` | `claim-stale` | digest or source closure no longer matches |
| `conflict` | `claim-conflict` | duplicate subject or lifecycle conflict blocks admission |
| `revoked-grant` | `claim-revoked` | upstream grant no longer admits the subject |

## Boundary

Do not add new admission results in this PR. Keep the machine vocabulary stable and add operator-readable classification only.

## Merge gate

`tools/compile-claim-port-joins.py selftest` must verify every diagnostic class above.
