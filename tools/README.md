# governance tools

## Package purpose

`tools/` contains reference projectors, compilers, checks, linters, report builders, and gate helpers used by the `governance` repository.

The package exists to turn accepted ADRS-derived inputs into deterministic diagnostics, receipts, reports, and gate-adapter outputs without becoming meaning authority.

## Responsibilities

- Compile accepted ADRS-derived inputs into governance-readable projections.
- Check package assertions, receipts, provider CI surfaces, and README projection surfaces.
- Produce deterministic findings with expected, actual, delta, likely owner, and nextAction.
- Emit evidence that can be consumed by final-scope joins.
- Keep selftests separate from final merge authority.
- Build and verify non-authority `govPackageOutput.v1` producer evidence packets.
- Join required repo universe, packet registry, packet findings, and producer provenance into org-level evidence rows.
- Provide the `gov-final-scope-purpose-join / gate` adapter surface without claiming provider cutover.
- Prove provider-neutral merge/write boundary decisions and audit receipts for exact target SHA checks.

## Public contract

Tools must be deterministic, side-effect-free, and explicit-input driven.

A tool may produce diagnostics, receipts, reports, or artifacts. A tool must not mint accepted meaning, mutate downstream repos, approve cutover, or treat artifact green as final merge authority.

## Required assertion

This package asserts:

```text
tools are non-authority governance projection/check surfaces
```

Each tool-level claim must remain traceable to an accepted ADRS-derived purpose, package obligation, or projection contract.

## Required receipt

Receipts must identify:

- tool name;
- input digest;
- output digest;
- status;
- checked contract or package id;
- whether the row is evidence, artifact, selftest, or final-join input.

## Entrypoints

- `tools/*.py`
- `tools/*.mjs`
- `tools/check-package-final-scope-purpose-join.py`
- `tools/check-merge-write-boundary-final-gate.py`
- `tools/check-package-gov-package-output-provenance.py`
- `tools/check-package-required-repo-org-join.py`
- Nix checks that invoke those tools
- future final-scope purpose join compiler and README projection checker surfaces

## Dependencies

Tools may depend on declared Nix inputs, repo-local fixtures, accepted ADRS-derived input bundles, and explicit provider CI metadata.

Tools must not depend on hidden local `records/` or `generated/` trees.

## Non-goals

- Do not accept or reject ADRS meaning.
- Do not mutate target repositories.
- Do not approve provider cutover.
- Do not hide residual work.
- Do not turn selftests into final merge authority.

## Residuals

If a tool cannot prove a row is active, it must return a residual or blocking finding instead of disappearing the gap.

## Final-scope purpose join gate adapter

`check-package-final-scope-purpose-join.py` provides the final check-name adapter:

```text
gov-final-scope-purpose-join / gate
```

The adapter currently runs strict gate regression selftests, provider-CI drift regression selftests, and merge/write boundary decision selftests. It is a merge-gate surface only after same-name green evidence and explicit provider cutover.

It emits non-authority evidence only. A green selftest is not selected real organization closure by itself.

## Merge/write boundary gate proof

`check-merge-write-boundary-final-gate.py` validates provider-neutral selected-ref update decisions:

```text
check
build
selftest
```

The tool allows only the exact target SHA accepted by `gov-final-scope-purpose-join / gate`, rejects stale or missing final-gate decisions, rejects old-CI-only evidence, and emits audit receipts.

The proof is provider-neutral and remains non-authority evidence until the selected enforcement provider is accepted.

## Gov-package-output producer/provenance tools

`check-package-gov-package-output-provenance.py` provides a narrow producer/verifier surface:

```text
build
verify
selftest
```

The tool emits non-authority evidence only. Its destructive fixture matrix is tool quality evidence, not final merge authority.

## Required repo packet org join tool

`check-package-required-repo-org-join.py` provides the Phase D evidence path:

```text
check
selftest
```

It reads required repo universe rows, packet registry rows, packet findings, and producer provenance signals. It emits `organization-active` only for clean required repo packet evidence and blocking findings for missing, stale, malformed, unavailable, unpinned, or invalid-provenance packet evidence.

This is org-join precursor evidence only. It is not branch protection authority and is not final-scope gate cutover.

## ADRS refs

- Accepted: `roccho-dev/adrs#105` governance final-scope purpose join, merged as `7a065ae987ddf766395b056f3678afcd371c08b3`.
- Accepted: `roccho-dev/adrs#106` README projection plane and gov package output plane, merged as `96b6fdcd02f4c8bee10a4b08a2c9a5d9dad91803`.

This README is an accepted ADRS projection surface for the `tools/` package. It remains non-authority evidence and must not be treated as an accepted decision record.
