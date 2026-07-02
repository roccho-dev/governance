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

## Current status

This PR adds the packet as checked-in proposal evidence and wires it to the flake surface.

The package output copies the checked-in packet files into the Nix store and validates the required packet files, non-authority boundary, proposal-preview mode, final gate reference, package rows, assertions, receipts, provider CI rows, findings, and admission rows.

## Boundary

- ADRS remains meaning authority.
- This packet is evidence and projection output.
- A green packet is not final merge authority unless consumed by the final join after accepted cutover.
