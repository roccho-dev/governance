# README projection receipts

## Purpose

This directory records proposal-stage README projection evidence for `governance#77` and governance-side observation rows for external README projection receipts.

It connects the ADRS README projection plane to the actual governance root README, package README surfaces, and explicitly non-blocking external projection readbacks.

## Surfaces

| Surface | Role |
|---|---|
| `README.md` | root README projection candidate |
| `tools/README.md` | tools package README projection candidate |
| `modules/README.md` | modules package README projection candidate |
| `console-observation-260704.md` | `roccho-dev/console` README projection observation note for `governance#134` |
| `consoleReadmeProjectionReceipt.jsonl` | proposal-preview / blocked observation rows for future console README receipt readback |

## Receipt rule

A README projection receipt is evidence only. It must not become meaning authority.

A pass means the README surface currently includes the required projection sections and does not claim final merge authority.

For external repos such as `roccho-dev/console`, proposal-preview observation rows must remain blocked for accepted readback until an accepted ADRS contract and matching repository receipt exist.

## Final join use

The final-scope purpose join may consume these receipts as evidence that human-readable README surfaces match ADRS-derived projection expectations.

A README projection failure should become a finding with `expected`, `actual`, `delta`, `likelyOwner`, and `nextAction`.

External observation rows are non-blocking unless a later accepted scope explicitly admits the observed repo and defines its required closure, assertion, receipt, and admission rows.
