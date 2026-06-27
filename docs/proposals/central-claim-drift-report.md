# Central claim drift report proposal

## Why

Repo-local CI gives immediate feedback to feat owners, but the organization also needs a central report showing which side is lagging across selected repos.

## Decision

Add a governance report that aggregates admission diagnostics from selected repos.

The report groups by:

- selected universe
- repo
- subject id
- contract id
- admission result
- diagnostic class
- likely owner
- next action

## Initial severity

Report-only. Do not block all selected repos until adoption monitoring and upstream grant projection are stable.

## Boundary

The report is non-authority and must not replace repo-local CI. It summarizes existing claim admission outputs.

## Implementation proof

`tools/build-central-claim-drift-report.py selftest` reads `fixtures/central-claim-drift-report/admissions.jsonl` and proves `adrs-lagging-feat`, `feat-lagging-adrs`, `claim-unproven`, and `claim-stale` remain separate groups with separate likely owner / next action fields.

## Merge gate

Merge only after a fixture proves that `adrs-lagging-feat`, `feat-lagging-adrs`, `claim-unproven`, and `claim-stale` are grouped distinctly.
