# Organization view registration checks proposal

## Why

After the local organization-join fixture is stable, governance needs a narrow check plan for production organization views.

## Direction

Add a governance proposal for checking that official organization views only include subjects with complete upstream records, downstream assertions, matching source closure, and required receipts.

## Decision

A later implementation may turn the local diagnostic into a production check for organization-active targets. The check should report clear diagnostics for:

- missing downstream assertion;
- missing upstream grant;
- source closure mismatch;
- missing required receipt;
- duplicate active assertion;
- revoked upstream grant.

The check must use pinned or checked-in inputs. It must not call live GitHub state or create dynamic authority.

## Boundary

This proposal does not implement the check and does not require branch protection. It only defines the next production-check scope after the fixture is stable.

## Merge Gate

Merge only if the production-check scope stays limited to organization-active targets and does not broaden into DD, transfer, runtime, or raw-ledger cutover work.
