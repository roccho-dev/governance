# Organization admission join fixture proof proposal

## Why

The claim-port compiler is useful only if its output can pass the existing official organization admission gate and reject blocking subjects.

## Decision

Add checked fixtures under `fixtures/claim-port/org-admission/` and a GitHub workflow that proves this route:

1. normalized grant/assertion/receipt ports
2. `tools/compile-claim-port-joins.py`
3. `governance.organizationAdmission.v1` JSONL
4. `tools/check-org-admission-gate.py`
5. pass for the admitted official view and fail for a blocking view

## Fixture cases

| case | expected result |
|---|---|
| matching grant + assertion + receipt | `organization-active` |
| assertion with no grant | `orphan-assertion` |
| grant with no assertion | `unclaimed-grant` |
| stale source closure | `stale-assertion` |
| official view includes stale subject | gate fail |

## Boundary

Fixture-only. No live GitHub reads. No all-repo rollout. No production admission gate.

## Merge gate

The checked-in workflow `claim-port org admission` must compile the fixtures, run the existing organization admission gate, and prove the blocking view is rejected.
