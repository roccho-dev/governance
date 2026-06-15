# Proposal: governance generated projection externalization

`records/` is the accepted JSONL record authority. `generated/` contains
projections derived from records and is explicitly not definition authority.

This proposal removes `generated/` from active source and adds it to `.gitignore`.
Projection outputs should be regenerated during checks or exported as build
artifacts/evidence, not reviewed as source.
