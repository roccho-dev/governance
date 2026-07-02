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
- Nix checks that invoke those tools
- future final-scope purpose join compiler and README projection checker surfaces

## Dependencies

Tools may depend on declared Nix inputs, repo-local fixtures, accepted ADRS-derived input bundles, and explicit provider CI metadata.

Tools must not depend on hidden local `records/` or `generated/` trees.

## Non-goals

- Do not accept or reject ADRS meaning.
- Do not mutate target repositories.
- Do not approve branch protection or provider cutover.
- Do not hide residual work.
- Do not turn selftests into final merge authority.

## Residuals

If a tool cannot prove a row is active, it must return a residual or blocking finding instead of disappearing the gap.

## ADRS refs

- Accepted: `roccho-dev/adrs#105` governance final-scope purpose join, merged as `7a065ae987ddf766395b056f3678afcd371c08b3`.
- Accepted: `roccho-dev/adrs#106` README projection plane and gov package output plane, merged as `96b6fdcd02f4c8bee10a4b08a2c9a5d9dad91803`.

This README is an accepted ADRS projection surface for the `tools/` package. It remains non-authority evidence and must not be treated as an accepted decision record.
