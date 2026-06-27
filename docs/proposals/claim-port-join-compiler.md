# Claim port join compiler proposal

## Why

Governance already has an admission gate for admission rows and official views. The missing seam is the small deterministic step that joins normalized upstream grant, downstream assertion, and receipt ports into admission rows.

## Decision

Add `tools/compile-claim-port-joins.py`, a port-only compiler that reads checked JSONL inputs and emits `governance.organizationAdmission.v1` JSONL.

The compiler reads only normalized ports:

- upstream grant port JSONL
- downstream assertion port JSONL
- receipt port JSONL

## Join rules

| condition | result |
|---|---|
| grant, assertion, and receipt match | `organization-active` |
| assertion exists without grant | `orphan-assertion` |
| grant exists without assertion | `unclaimed-grant` |
| grant and assertion exist without receipt | `asserted-but-unproven` |
| bundle or source closure digest differs | `stale-assertion` |
| lifecycle is revoked | `revoked-grant` |
| duplicate subject or blocking lifecycle conflict | `conflict` |

## Boundary

The compiler reads normalized ports only. Repo-specific sources are handled by thin adapters before the compiler runs. Governance emits non-authority admission rows; accepted meaning remains in ADRS.

## Merge gate

The checked-in GitHub workflow `claim-port join` must run `tools/compile-claim-port-joins.py selftest` and cover both admitted and rejected joins.
