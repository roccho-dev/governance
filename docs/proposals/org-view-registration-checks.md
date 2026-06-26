# Organization view registration checks proposal

## Why

After the local organization-join fixture is stable, governance needs a narrow check plan for production organization views.

## Direction

Add a governance production check for official organization views. The check ensures that included subjects have complete upstream records, downstream assertions, matching source closure, and required receipts.

## Decision

The production check reports clear diagnostics for:

- missing downstream assertion;
- missing upstream grant;
- source closure mismatch;
- source closure head mismatch;
- missing required receipt;
- duplicate active assertion;
- revoked upstream grant;
- stale assertion;
- asserted but unproven assertion;
- unresolved latest user or operator intent challenge;
- unaccepted official view digest for execution inputs.

The check must use pinned or checked-in inputs. It must not call live GitHub state or create dynamic authority.

The initial implementation is `tools/check-org-admission-gate.py`. It fails when an official view includes a subject whose admission record is missing, not `organization-active`, has a blocking diagnostic, has a digest or receipt mismatch, has a stale source closure head, has a blocking lifecycle, has duplicate active assertions, lacks accepted view digest evidence for execution, or treats an unresolved latest intent challenge as active.

## Boundary

This proposal does not require branch protection. It defines and implements the local deterministic production-check behavior after the fixture is stable.

## Merge Gate

Merge only if the production-check scope stays limited to organization-active targets, uses checked-in inputs, and does not broaden into DD, transfer, runtime, or raw-ledger cutover work.
