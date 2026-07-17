# Governance #150 pre-acceptance implementation

## Boundary

Parent decision `roccho-dev/adrs#233` is proposed and is not accepted decision authority.
This change therefore performs only:

- machine-readable inventory of the current 12 workflows;
- explicit current and target authority classes;
- exact-candidate-SHA non-authority gate fixture;
- current claim-port and selected-scope closure reuse;
- destructive migration-safety tests;
- same-name current-head fixture execution.

It does not grant merge-admission or effect authority, change required checks, delete workflows, or claim all-repository enforcement.

## Current topology findings

| Finding | Current fact | Required later action |
|---|---|---|
| Default branch | `proposals` | preserve exact default identity |
| `repo-governance` push | `main` | move proof before deletion |
| ruleset plan | `main`, legacy check, `authority:false` | accepted cutover and readback |
| ADRS shadow default | `main` | bind accepted ADRS ref/release |
| repo-explain fallback | fallback artifact can still become green | remove only after accepted output transfer |
| merge-admission surfaces | `0` | exactly `1` only after accepted decision |
| current workflow count | `12` | converge only with no-loss and no-residual proof |

## Implemented fixture equation

```text
proposed ADRS fixture identity
+ governance fixture assertion
+ exact-candidate-SHA fixture receipt
+ current claim-port organization admission
+ scope/package/purpose pass
+ source and engine identity equality
+ zero current merge/effect authority
= fixture-pass | block
```

`fixture-pass` is evidence-only and is never production `allow`.

## Destructive coverage

The selftest rejects 25 cases including missing/stale decision, assertion and receipt inputs; repository/SHA mismatches; source and candidate races; authority collisions; fallback or generated artifacts offered as admission; expired exceptions; incomplete deletion; effect readback mismatch; write-secret exposure; and technical-to-business overclaims.

## Residuals intentionally left open

- accepted ADRS #233 decision/release digest;
- accepted positive feature consumer and current assertion;
- accepted migration consumer with a known mismatch;
- accepted receipt contract and production receipts;
- required-check or publish-gate control-plane adapter;
- protected-ref/effect readback;
- responsibility transfer and deletion readback;
- final two-workflow cutover;
- all-repository enforcement.

These residuals block closure of governance #150, but not merge of this bounded pre-acceptance fixture and inventory.
