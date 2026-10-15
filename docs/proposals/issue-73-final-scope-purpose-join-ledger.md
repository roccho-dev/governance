# Issue 73 child PR work protocol

Parent issue: #73

## Status

This document is a non-authority work protocol. It does not define ADRS meaning, change CI behavior, alter branch protection, or claim package closure.

## Responsibility split

| Surface | Responsibility | Volatility | Holds | Must not hold |
|---|---|---:|---|---|
| #73 issue | live control plane | high | current phase, child PR registry, blockers, next actions, progress comments | long implementation specs, full schemas, CI logs, duplicated PR bodies |
| this document | stable work protocol | low | child PR work-order shape, completion criteria shape, comment templates, forbidden moves, post-state expectations | live PR status, checkbox progress, current CI result |
| child PR body | local contract | medium | one invariant, concrete change, local acceptance, local boundary | whole roadmap redefinition |
| child PR diff | implementation evidence | medium | actual file changes | live status or broad planning |
| #73 comments | event log | high | PR opened, blocked, merged, closed, evidence summary | durable protocol text |

Short form:

```text
#73 = live ledger
this doc = completion protocol
child PR = one invariant
#73 comment = progress evidence
```

## Source invariant

The staged work converges on this shape:

```text
ADRS grant x package assertion x CI receipt x governance join = active-only merge
```

The roles must not drift:

| Role | Owner |
|---|---|
| expectation / accepted decision | ADRS |
| package claim | feature/package repo |
| evidence | CI receipt |
| join / diagnosis | governance |
| final merge decision | `gov-final-scope-purpose-join / gate` after cutover |

## Four-principle rules

### DRY

- Store live status only in #73 and #73 comments.
- Store stable work-order protocol only in this document.
- Store PR-local facts only in each PR body and diff.
- Store CI truth in GitHub checks, not copied into this document.

### KISS

- Each child PR adds exactly one invariant.
- Each child PR has one clear post-state.
- Each child PR uses the same small interface.

### YAGNI

- Do not create child issues per PR yet.
- Do not add GitHub Projects, milestones, or many labels yet.
- Do not automate status sync until the manual protocol is proven.

### SOLID

| Principle | Application |
|---|---|
| Single responsibility | #73 tracks state; this doc defines protocol; PRs change repo state. |
| Open/closed | Add new child PR rows to #73 without rewriting this protocol unless the interface is wrong. |
| Substitutability | Any child PR can be reviewed through the same work-order interface. |
| Interface segregation | A child PR only fills fields relevant to its one invariant. |
| Dependency inversion | Child PRs depend on the protocol and parent ledger, not on chat history. |

## Child PR work-order interface

Every child PR must be expressible in this form.

```text
Work order:
Repo:
Parent issue:
Lane:
Purpose:
Added invariant:
Pre-state:
Change:
Files allowed:
Files forbidden:
Positive evidence:
Negative evidence:
Definition of Done:
Definition of Not Done:
Post-state:
Issue comment required:
Merge blocker:
```

## Completion criteria shape

A child PR is complete only when all three sections are true.

```text
Done when:
- observable condition A
- observable condition B
- observable condition C

Not done when:
- forbidden state A
- misleading state B
- missing evidence C

Post-state:
- after merge or close, the repo/issue/PR world must look like this
```

A condition is not acceptable if it depends on private memory, chat context, or unstated reviewer judgment.

## Issue comment template

When a child PR is opened, comment on #73:

```text
Child PR opened: #<number>

Work order:
- <A1/G0/G1/B2/...>

Lane:
- <A/B/C/D>

Added invariant:
- <one invariant>

Post-state when merged:
- <observable state>

Boundary:
- <what this PR does not claim>

Current state:
- open / draft / blocked / ready
```

When a child PR is completed or closed, comment on #73:

```text
Child PR completed: #<number>

Result:
- merged / closed-not-planned / blocked

Invariant status:
- added / not added / deferred

Evidence:
- <CI result, review result, or close reason>

Next:
- <next child PR or blocker>
```

## Global forbidden moves

These are forbidden unless a child PR explicitly owns that step and all dependencies are satisfied:

- making governance a meaning authority;
- treating a feature wish as an accepted ADRS grant;
- calling `nix flake check` green a final-scope pass;
- calling `handoff-ready` a closure pass;
- required-protecting a shadow report;
- deleting old CI before the final join exists and has run green;
- changing branch protection before a same-name final gate green run exists;
- merging expected-failure proof PRs as product behavior;
- copying live status into this document as if it were stable protocol.

## Work-order catalog

### A1: ADRS package responsibility closure contract

Done when:

- the ADRS contract PR remains contract-only;
- package obligation, inventory, response, drift, and work-order concepts are accepted on the ADRS side;
- no implementation, deploy, production gate, or closure claim is mixed into the ADRS PR;
- #73 has a child PR comment for A1.

Not done when:

- governance is used as meaning authority;
- pending/proposed ADRS rows are treated as accepted merge authority;
- implementation code is required to understand the contract PR.

Post-state:

- final gate work can read ADRS as expectation source without minting new meaning in governance.

### G0: negative proof cleanup

Done when:

- the expected-failure PR is not treated as a merge candidate;
- the evidence is preserved in #73 or an appropriate doc/comment;
- the PR is closed or otherwise marked as non-product proof;
- #73 records the result.

Not done when:

- the expected-failure PR remains an ordinary open merge candidate;
- the expected-failure PR is merged;
- evidence is lost;
- #73 has no reason trail.

Post-state:

- red-by-design proof cannot be mistaken for source-closing progress.

### G1: package closure handoff producer

Done when:

- every work order has owner routing;
- every work order has required proof routing;
- every blocking work order has a returned residual;
- dirty fixture is `handoff-ready`, not `closure-pass`;
- outputs are deterministic;
- `authority` remains false;
- #73 links the PR as G1.

Not done when:

- `handoff-ready` is described as final pass;
- unclosed drift disappears from residual output;
- governance claims target repo mutation;
- final gate or ruleset files are changed.

Post-state:

- unclosed drift can be handed to owners without being mistaken for closure.

### B2: final report shape

Done when:

- `govFinalScopePurposeJoin.report.v1` is documented;
- clean fixture has expected pass report;
- dirty fixture has expected fail report;
- stale assertion fixture includes stale diagnostic;
- orphan assertion fixture includes orphan diagnostic;
- missing receipt fixture includes unproven diagnostic;
- provider CI drift fixture includes provider CI failure;
- every blocking finding includes `packageId`, `contractId`, `expected`, `actual`, `delta`, `likelyOwner`, and `nextAction`;
- no workflow, ruleset, or checker behavior is changed unless the PR explicitly owns that.

Not done when:

- report only says pass/fail;
- `nextAction` is absent;
- pending ADRS is accepted as authority;
- missing receipt can pass;
- final merge authority is claimed.

Post-state:

- B3 can implement the compiler without redefining report shape.

### B3: final join compiler

Done when:

- existing claim join output is consumed;
- org admission output is consumed;
- package closure strict output is consumed;
- provider CI YAML findings are consumed;
- clean fixture produces a pass report;
- dirty fixture produces blocking findings with next actions;
- old CI remains available for comparison.

Not done when:

- any partial join green is presented as final green;
- old CI is deleted in the same PR;
- report shape is redefined instead of consuming B2;
- provider CI drift is outside the report.

Post-state:

- final-scope report can be built from existing parts while preserving comparison safety.

### B4: canonical receipt producer

Done when:

- receipt rows include `packageId`, `contractId`, `assertionDigest`, `decisionDigest`, `checkId`, `status`, and `evidenceDigest`;
- package/internal/contract checks can emit or materialize those rows;
- final join can consume the rows without interpreting raw CI logs;
- `nix flake check` remains evidence producer, not final authority.

Not done when:

- receipt is only a human log;
- status lacks package or contract identity;
- decision/assertion digest is absent;
- green CI is called final-scope pass.

Post-state:

- checks are joinable evidence instead of ambiguous green/red signals.

### C1: ops canonical package closure outputs

Done when:

- ops emits canonical package inventory rows;
- ops emits canonical package response rows;
- ops emits residual rows when work remains;
- ops emits drift rows that governance can join;
- authority remains false;
- no final closure claim is made.

Not done when:

- response shape is only locally readable;
- residuals are hidden;
- generated artifact rows are treated as source package drift;
- ops becomes meaning authority.

Post-state:

- ops acts as downstream evidence producer for the final join.

### C2: UI preview overclaim cleanup

Done when:

- UI preview/artifact status is explicitly bounded;
- current preview cannot claim final product UI status;
- future-retirement residual is represented where needed;
- red artifact-retirement PRs are not merged until failures are resolved.

Not done when:

- placeholder artifacts look like production evidence;
- preview path is treated as final pass;
- failing Nix/A2UI checks are ignored.

Post-state:

- UI artifacts cannot masquerade as final governance closure.

### B5: shadow report workflow

Done when:

- real inputs can produce a final-scope report artifact;
- workflow name does not look like the strict required gate;
- blocking drift yields `report-generated`, not `pass`;
- output is useful for deciding whether B6 can be made strict.

Not done when:

- shadow output is required-protected;
- shadow success is used as merge authority;
- report omits blockers or next actions.

Post-state:

- real repo gaps are visible before strict enforcement.

### B6: strict final gate workflow

Done when:

- `gov-final-scope-purpose-join / gate` exists;
- it fails on non-active admission;
- it fails on missing inventory;
- it fails on missing assertion;
- it fails on missing or stale receipt;
- it fails on provider CI drift;
- it passes only when all in-scope packages are active or explicitly waived.

Not done when:

- strict gate ignores provider CI drift;
- missing receipt can pass;
- shadow status is reused as strict pass;
- branch protection is changed in the same PR.

Post-state:

- source-defined final gate exists but is not yet the required branch-protection check.

### D1: ruleset and CI intent cutover

Done when:

- same-name `gov-final-scope-purpose-join / gate` has run green at least once;
- ruleset plan moves required check to the final gate;
- `repo-governance / proof` is no longer the primary merge signal in the plan;
- rollback text is present;
- #73 records the cutover evidence.

Not done when:

- required check is moved before same-name green run;
- rollback is absent;
- old and new required checks create conflicting authority;
- branch protection points to a non-existing check.

Post-state:

- branch protection plan depends on the final gate, not unrelated green workflows.

### D2: old CI producerization or deletion

Done when:

- `repo-explain-artifact-minimal` is optional artifact producer or removed;
- `README artifact exporter` is optional artifact producer;
- `intent reality gap` is a final join internal step or tool selftest;
- `log route join` is a final join internal step or tool selftest;
- `claim-port join` is a final join internal step or tool selftest;
- `claim-port org admission` is a final join admission step;
- generic `CI` is split into receipt producers and tool selftests;
- useful tests are not lost.

Not done when:

- old CI is removed before final gate is active;
- artifact generation remains merge-looking;
- checker selftests disappear without replacement;
- any producer claims final merge authority.

Post-state:

- false-positive CI surfaces are retired without losing evidence production.

### C3: target repo rollout template

Done when:

- target repos can adopt the same final gate shape;
- old target repo governance validation is absorbed or demoted;
- target README/artifact workflows cannot claim final scope pass;
- target repo receipts use the same joinable shape.

Not done when:

- governance repo closes while target repos remain on incompatible claim/receipt shape;
- target repo artifact workflows remain merge-looking;
- target repo checks cannot be joined by governance.

Post-state:

- downstream repos participate in the same source-defined closure model.

## First trial scope

The first trial PR is this documentation update. It is intentionally safe: it changes only this non-authority protocol document and does not touch workflows, rulesets, or checker behavior.

## Acceptance for this PR

- The PR references #73.
- The PR changes documentation only.
- No workflow file is changed.
- No ruleset plan is changed.
- No checker behavior is changed.
- This document clearly separates #73, this document, child PRs, and #73 comments.
- This document contains done / not done / post-state criteria for child PRs.
- This document states that it is non-authority and not a closure claim.
