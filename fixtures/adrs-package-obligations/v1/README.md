# ADRS package-obligation source fixture v1

This directory is a provider-neutral, non-authoritative fixture for the exact
`packageObligation.v1` JSONL source that an accepted ADRS release must eventually
provide to Governance.

It binds the current Ops package universe at the recorded commit and selects only
three packages for executable proof. Every other package is explicitly represented
as out of scope; omission is not used as a shortcut.

The fixture cannot accept ADRS meaning, publish a production release, grant merge
admission, or mint `organization-active` state.

## Exact source carrier

`source.jsonl.gz.b64` is a deterministic neutral-text carrier of the exact canonical
`packageObligation.v1` JSONL bytes. The manifest `source_sha256` binds the decoded
JSONL, not the carrier wrapping. The carrier is transport-only and cannot become
accepted meaning. Decoding must use strict Base64 and gzip; repair or partial decode
is forbidden.
