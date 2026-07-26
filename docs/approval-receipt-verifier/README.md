# approval-receipt-verifier

Pure provider-neutral verifier owned by `governance`.

```text
accepted authority grant
+ provider evidence envelope
+ exact subject and policy identity
+ explicit as_of and engine identity
  -> approvalReceipt.v1
  -> VALID | INVALID | ERROR
```

## Authority boundary

- ADRS owns accepted grants and actor/provider bindings.
- ops owns provider API readback and `githubApprovalEvidence.v1`.
- governance validates closed envelopes and exact joins only.
- diagrams may consume only a later `VALID` receipt.

This package performs no network access, current-permission lookup, filesystem discovery, implicit clock read, authority mutation, waiver approval, or physical-human identity assertion.

## Current upstream binding

```text
architecture issue   roccho-dev/adrs#260
status               PROPOSED / provider-runner blocked
candidate contract   approvalReceiptContract.v1
```

The implementation proof may run while the architecture is proposed. Merge is forbidden until the exact Accepted ADRS release and digest are substituted and read back.

## Proof

```bash
python3 tools/approval-receipt-verifier.py selftest
nix-build nix/approval-receipt-verifier.nix
nix flake check -L
```

The selftest includes one valid GitHub-shaped provider-neutral envelope and 22 destructive cases. Identical inputs produce byte-equivalent receipts.

## Claim ceiling

```text
providerNeutralVerifierImplemented=true
exactAuthorityGrantJoinProven=true
exactRevisionJoinProven=true
githubEvidenceAdapterImplemented=false
physicalHumanIdentityProven=false
accountNonCompromiseProven=false
providerIndependentNonRepudiationProven=false
allRepositoriesEnforced=false
businessOutcomeAchieved=false
corporateSaleOutcomeAchieved=false
```
