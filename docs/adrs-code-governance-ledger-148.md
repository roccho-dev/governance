# ADRS code-governance ledger integration for #148

## Purpose

Integrate the provider-detached proof with the live, non-authority ledger in
`roccho-dev/adrs#231` without creating a second editable rule source.

## Owned here

- Issue and file ledger adapters;
- local and Git source-tree adapters;
- canonical ledger sealing;
- closed schema and explicit-supersession reducer;
- purpose closure;
- Go AST facts and bounded architecture rules;
- provider-neutral semantic packet;
- offline Nix materialization;
- read-only CI receipt and destructive tests.

## Not owned here

- accepted ADR authority;
- production merge or ref mutation;
- branch protection or rulesets;
- all-repository rollout;
- non-Go language enforcement;
- causal or business-outcome claims.

## Live fixture

- source: `roccho-dev/adrs#231`;
- writer: `roccho-dev` for this non-authority fixture only;
- source comments: 9;
- rows: 52;
- expected canonical ledger SHA-256:
  `723ac930fbd5e1a85de8fc552e49d8477568c8da1c7acd58e0db34b29490338b`.

The Issue body and later discussion comments are transport UI only and do not
enter semantic artifacts.

## Closure

The implementation PR closes governance#148 only after the live workflow reads
all fixture comments, reproduces the expected ledger and semantic packet,
passes all destructive tests, materializes byte-identically with Nix, and
publishes a non-authority receipt.
