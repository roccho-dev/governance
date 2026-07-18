# Contract-modeling proof corpus

`generate.py` deterministically materializes the non-authority claim ledger and
legacy migration ledger used by the compiler tests. The generated JSONL files are
ignored by Git because their source is this checked generator and the pinned
accepted-candidate policy.

The proof corpus intentionally exercises all eight admission outcomes, two
unrelated real governance packages, a recursive graph deeper than package level,
36 legacy responsibilities, exact-SHA receipts, effect readback, and the bounded
model-only package.

Proof-corpus sizes are fixture assertions. They are not organization policy.
