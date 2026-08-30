# Canon TDD final-only result

The P1 canonical result has one positive vocabulary value: `GREEN`.

No phase, partial, local, candidate, merge-only, test-only, or readback-missing result is a completion state. Those conditions produce diagnostics outside the canonical result file and a nonzero exit. The canonical file is created atomically only after the complete selected P1 target is established against exact final identities.

`tools/check-canon-tdd-final.py` is a pure final join. It does not accept rules, run providers, mutate repositories, publish releases, or authorize production. It verifies final evidence produced by the accepted ADRS, Governance projection, Ops enforcement, Git effect/readback, real toolchain/NAR, immutable publication, and fresh replay boundaries.
