# gov package output

## Purpose

This directory defines the repo-local `govPackageOutput.v1` packet for `roccho-dev/governance`.

The same packet is exposed through:

```text
packages.<system>.gov-package-output
checks.<system>.gov-package-output
```

It is evidence for governance joins, not meaning authority.

## Packet files

| File | Role |
|---|---|
| `manifest.json` | packet metadata and digest surface |
| `repo.json` | repo purpose, repo class, authority boundary, final gate target |
| `packages.jsonl` | package rows for current package-like surfaces |
| `assertions.jsonl` | package assertions against ADRS-derived contracts |
| `receipts.jsonl` | evidence rows proving assertions |
| `readmeProjectionReceipt.jsonl` | root/package README projection receipts |
| `provider-ci.jsonl` | provider CI rows relevant to governance output |
| `findings.jsonl` | blocking and non-blocking diagnostics |
| `admission.jsonl` | organization-active admission rows |
| `input-manifest.jsonl` | producer source input closure and `inputLockDigest` source |
| `producer-provenance.json` | producer repo/rev/digest and recomputable output digest claim |

## Reusable producer

The reusable producer surface is `nix/gov-package-output-producer.nix`.
Downstream repos can import it from `inputs.governance` and call:

```text
mkGovPackageOutput
mkGovPackageOutputCheck
```

The producer requires explicit `repoId`, `repoClass`, package inventory,
assertions, receipts, README projection receipts, provider CI rows, findings,
admission rows, and declared source paths. Missing required inputs fail closed.

## Provenance verification

`tools/check-package-gov-package-output-provenance.py` verifies provenance fields
by recomputing the input lock digest and output digest. Packet-internal
provenance is treated as a claim, not proof.

Destructive cases live under `fixtures/gov-package-output-provenance/` and cover
shape-only packets, fake provenance, stale producer revisions, wrong producer
digests, missing source inputs, wrong input locks, wrong output digests, and
undeclared packet output.

## Current status

This phase adds reusable producer/provenance evidence only.

It does not claim final join active status, downstream rollout, branch protection
cutover, accepted ADRS meaning, or final merge authority.

## Boundary

- ADRS remains meaning authority.
- This packet is evidence and projection output.
- A green packet is not final merge authority unless consumed by final join after accepted cutover.
