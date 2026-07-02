# README projection receipts

## Purpose

This directory records proposal-stage README projection evidence for `governance#77`.

It connects the ADRS README projection plane to the actual governance root README and package README surfaces.

## Surfaces

| Surface | Role |
|---|---|
| `README.md` | root README projection candidate |
| `tools/README.md` | tools package README projection candidate |
| `modules/README.md` | modules package README projection candidate |

## Receipt rule

A README projection receipt is evidence only. It must not become meaning authority.

A pass means the README surface currently includes the required projection sections and does not claim final merge authority.

## Final join use

The final-scope purpose join may consume these receipts as evidence that human-readable README surfaces match ADRS-derived projection expectations.

A README projection failure should become a finding with `expected`, `actual`, `delta`, `likelyOwner`, and `nextAction`.
