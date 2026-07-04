# Console README projection observation

## Purpose

This note defines the governance-side readback surface for `roccho-dev/console` README projection.

Governance observes the console README projection only as non-blocking evidence. The observation does not admit `console` into selected real package closure, does not make a final gate pass, and does not make README, dashboards, screenshots, GitHub Projects, deployed pages, or generated artifacts authoritative.

## Current mode

| Field | Value |
|---|---|
| observation mode | `proposal-preview` |
| readback status | `blocked` |
| blocking level | non-blocking |
| selected real package closure | no |
| final gate admission | no |

The observation is blocked because the ADRS-side contract and the matching console README projection receipt are not yet accepted inputs.

## Inputs

| Input | Current state | Governance use |
|---|---|---|
| `roccho-dev/console#1` | open purpose issue | originating repo-purpose signal only |
| `roccho-dev/adrs#187` | open proposal issue | proposal-preview meaning input only |
| console README projection PR | not observed here | future projection surface input |
| console README projection receipt | not observed here | future receipt input |

## Observation rule

Governance may record that `console` is expected to project ADRS-defined repository purpose and deployment-visualization boundary into README.

Until an accepted ADRS contract and a matching console receipt exist, governance must report this as:

- proposal-preview;
- blocked for accepted readback;
- non-blocking;
- non-authority;
- not selected real package closure;
- not final active admission.

## Future accepted upgrade

A future PR may upgrade this observation from `proposal-preview` to `accepted` only when both are true:

1. ADRS has accepted the console README projection contract.
2. `console` has emitted a matching README projection receipt that governance can join to that contract.

That later upgrade still must not treat README or deployed output as meaning authority. It may only prove that the reader-facing projection matches accepted ADRS expectations.

## Final-scope behavior

Future final-scope reports may display this row as observation-only context.

This row must not increase selected repo universe, selected package closure, active organization admission, final merge authority, or cutover readiness.

## Closure statement

Governance observes `console` README projection as non-blocking evidence only; `console` is not admitted to selected closure or final gate authority by this work.
