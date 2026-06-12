# 260612 A2UI stream-as-source v3 gates

This proposal delta makes v3 enforceable without moving authority to HTML or
WebMCP.

## Gate records

`records/proposals/a2ui-board-view-v3-gate.v1.jsonl` defines the blocking rules
for:

- source retention
- reducer byte equivalence
- no raw design bucket
- diagnostics blocking
- digest parity across query and HTML
- renderer projection-only input
- single host / mirror-only 8087

The CUE shape is `#A2uiBoardViewV3Gate` in `policy/cue/a2ui-board-view.cue`.
