# Issue 73 final-scope purpose join ledger

Parent issue: #73

## Status

This document is non-authority execution tracking. It does not define ADRS meaning, change CI behavior, alter branch protection, or claim package closure.

## Purpose

Keep child PRs small while moving `governance` toward the source-defined final shape:

- ADRS is the expectation source.
- Feature/package repos produce assertions.
- CI output is receipt evidence.
- Governance joins ADRS grant, package assertion, and receipt.
- Merge authority eventually comes from `gov-final-scope-purpose-join`, not from artifact or selftest workflows.

## Small-test invariant

Every child PR must add exactly one durable invariant and must not weaken an earlier invariant.

If a PR only proves that something fails correctly, it must not be merged as product behavior. It can remain a negative proof or be closed after the evidence is recorded.

## Child PR order

| Wave | Child | Merge meaning | Must not do |
|---:|---|---|---|
| W0 | G0 negative proof cleanup | expected-failure proof is not a merge candidate | merge #66 |
| W0 | G1 handoff producer | drift is routed to owner/proof/residual without calling it pass | claim closure |
| W1 | B2 final report shape | `govFinalScopePurposeJoin.report.v1` output is stable | required-protect workflow |
| W2 | B3 final join compiler | existing join parts are grouped into one report | delete old CI |
| W2 | B4 receipt producer | checks emit machine-joinable receipts | treat `nix flake check` as final pass |
| W3 | B5 shadow report | real inputs can be observed without merge authority | call shadow green a pass |
| W4 | B6 strict final gate | non-active, missing receipt, inventory gap, or provider CI drift fails | change branch protection |
| W5 | D1 cutover plan | required check can move after same-name green run | cut over before green run |
| W6 | D2 old CI demotion | artifact/selftest workflows stop looking like final gates | remove checks before final gate exists |

## First trial scope

This PR only adds this ledger file. It is intentionally small so the issue-to-child-PR process can be tested without touching workflows, rulesets, or checker code.

## Acceptance

- The PR references #73.
- The PR changes documentation only.
- No workflow file is changed.
- No ruleset plan is changed.
- No checker behavior is changed.
- The document states that it is non-authority and not a closure claim.
