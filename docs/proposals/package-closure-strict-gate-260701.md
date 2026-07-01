# Package closure strict gate

## Purpose

Make unclosed package responsibility red.

A generated drift report is useful, but it is not a purpose-level pass. `pass` is reserved for the state where ADRS package obligations, repo package inventory, package responses, required tests, receipts/residuals, and authority boundaries have no blocking drift.

## Change

Add `tools/check-package-closure-strict.py`.

The gate wraps the package responsibility closure compiler and provides two modes:

| Mode | Meaning | Exit |
|---|---|---|
| `strict` | blocking drift means package closure failed | non-zero when blocking drift exists |
| `shadow` | report generation is allowed, but not called pass | zero, status is `report-generated` when drift exists |

## Pass rule

```text
pass = blockingDrifts == 0
```

The following are not pass:

- report generated;
- canonical output generated;
- drift rows emitted;
- work orders emitted;
- unregistered package discovered.

Those are evidence or diagnostics only.

## Selftest contract

The selftest proves three cases:

| Case | Expected |
|---|---|
| dirty fixture in strict mode | `fail` |
| dirty fixture in shadow mode | `report-generated` |
| clean fixture in strict mode | `pass` |

## Boundary

- Governance remains non-authority.
- ADRS remains meaning authority.
- This gate does not mutate target repos.
- This gate does not silently enable all-repo strict rollout.
- This gate only defines correct package closure status behavior.

## Acceptance

This PR is acceptable when the strict gate selftest proves that unclosed package responsibility becomes red and report generation is no longer named pass.
