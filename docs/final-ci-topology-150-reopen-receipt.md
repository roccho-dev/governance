# Governance #150 reopen receipt

The prior completed closure receipt is superseded as a closure claim, but retained as historical evidence.

## Reopen findings

1. The final gate accepted checked-in UI/Ops run and artifact identifiers without downloading the artifact body.
2. Claim-port admission did not carry or compare the selected consumer receipt candidate SHA.
3. The canary did not observe current UI/Ops claims, current heads, current successful receipt runs, artifact bodies, or control-plane rulesets.
4. One expected-head merge proved one bounded effect but not a permanent exclusive merge path.

## Required correction

- static rollout data contains expectations only;
- each gate run captures live UI/Ops heads, claims, push runs, artifacts, ZIP digests, and receipt bodies;
- receipt candidate SHA is preserved through claim-port admission;
- canary repeats live consumer and control-plane observation;
- missing or unobservable ruleset state blocks a permanent-path claim;
- `allRepositoriesEnforced=false` remains fixed.

Refs: governance#150, adrs#233.
