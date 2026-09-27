# Selected repo README materialization readback for governance #144

## Purpose

Collect selected-repo readback after common-check rollout PRs land.

## Current rollout state

This document is intentionally pre-readback while rollout PRs are still unmerged. It records which evidence is expected and which PR must land before default-branch readback can be trusted.

| repo | rollout PR | current PR state | selected path | expected readback after merge | status |
|---|---|---|---|---|---|
| roccho-dev/adrs | roccho-dev/adrs#197 | open / draft | generated-mode common checker adoption | `readmeMaterializationReceipt.v1`, check name, merge commit, default-branch README readback | blocked: real wiring still draft |
| roccho-dev/governance | roccho-dev/governance#146 | open / ready / mergeable | bounded residual through common checker | `readmeMaterializationResidual.v1`, check name `readme-materialization-self-residual`, merge commit, default-branch readback | waiting for merge |
| roccho-dev/ui | roccho-dev/ui#107 | open / ready | generated-mode common checker adoption | `readmeMaterializationReceipt.v1`, check name `readme-materialized`, merge commit, default-branch README readback | waiting for merge |
| roccho-dev/ops | roccho-dev/ops#36 | open / ready | not-generated-ready residual mode | `readmeMaterializationResidual.v1`, residual artifact, merge commit, default-branch readback | waiting for merge |

## Merge-readback checklist

Complete this PR only after every selected rollout PR has merged.

| requirement | needed evidence | current state |
|---|---|---|
| selected repo universe listed | adrs, governance, ui, ops | listed |
| adrs readback | #197 merge commit and default-branch receipt | missing |
| governance readback | #146 merge commit and default-branch residual proof | missing |
| ui readback | #107 merge commit and default-branch receipt | missing |
| ops readback | #36 merge commit and default-branch residual proof | missing |
| bounded residuals | owner, reason, nextAction, returnCondition, expiry | expected for governance and ops |
| final enforcement boundary | no final README projection compliance claim | preserved |

## Boundary

This readback is not final until rollout PRs merge and default-branch README readback evidence is attached.

It does not claim final README projection compliance. It does not replace governance #81 / #131 final README projection drift enforcement. It does not mutate branch protection.

Refs: #144, #145, #146, roccho-dev/adrs#197, roccho-dev/ui#107, roccho-dev/ops#36, #131, #81
