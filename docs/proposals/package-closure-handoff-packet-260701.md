# Package closure handoff packet

## Purpose

Make governance package closure output directly handoffable.

After #69, governance can compile package obligations, inventory, responses, drift, work orders, and strict status. The remaining governance-side gap is not another evaluator. The gap is that a target repo owner should be able to pick up the output without another governance judgment PR.

## Goal

Produce a deterministic handoff packet that converts package closure work orders into:

- owner routing;
- required proof rows;
- returned residual rows;
- a human-readable handoff README;
- a manifest with digests.

## Status semantics

| Status | Meaning |
|---|---|
| `closure-pass` | zero blocking package drift |
| `handoff-ready` | blocking drift exists, but every item has owner, proof, next action, and residual |
| `handoff-blocked` | at least one blocking item lacks owner/proof routing |
| `report-generated` | diagnostic output only; never purpose-level pass |

## Outputs

| File | Role |
|---|---|
| `package-closure-handoff.json` | summary and status |
| `package-work-orders.jsonl` | source work orders from compiler output |
| `package-owner-routing.jsonl` | repo/owner routing for each work order |
| `package-required-proofs.jsonl` | proof and receipt requirements |
| `package-residuals.jsonl` | returned residuals for unclosed blocking work |
| `README.handoff.md` | human handoff instructions |
| `handoff-manifest.json` | required file list and digests |

## Acceptance

The selftest must prove:

- dirty package fixture becomes `handoff-ready`, not `closure-pass`;
- every work order has an owner route;
- every work order has a required proof row;
- every blocking work order has a returned residual;
- all required handoff files are emitted and non-empty;
- the handoff manifest is deterministic;
- governance remains non-authority.

## Boundary

- ADRS remains meaning authority.
- Governance remains non-authority diagnostic/projection.
- This PR does not mutate target repos.
- This PR does not close real target repo drift.
- This PR removes the need for another governance judgment PR before handing work to target repos.
