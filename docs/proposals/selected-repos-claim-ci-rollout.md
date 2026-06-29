# Selected repos claim CI rollout proposal

## Why

After ops proves the first local claim admission path, the same pattern must roll out to each selected repo without turning governance into the repo-local alert owner.

## Decision

Define a staged rollout for selected repos:

1. repo-local staged-warning claim admission CI
2. governance adoption monitor coverage
3. ADRS-derived upstream grant projection coverage
4. strict closure PR per selected repo
5. central report aggregation

## Rollout requirements

Each selected repo must provide:

- downstream claim port
- receipt port
- ADRS-derived upstream grant input
- repo-local CI alert
- adoption monitor evidence

## Boundary

No all-repo hard gate until selected universe and adoption monitor are accepted. Rollout is per selected repo, not implicit across every repository.

## Merge gate

Merge only if rollout stages preserve local alert ownership and governance remains a non-authority checker and monitor.
