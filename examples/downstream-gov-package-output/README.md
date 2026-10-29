# downstream gov-package-output example

This example shows how a repo can consume `roccho-dev/governance` as an input and call the reusable gov-package-output producer.

Boundary: example evidence only. No final gate or rollout claim.

## Reproducible example boundary and observation

The example flake now names exact Nixpkgs and governance source revisions rather than floating `nixos-unstable` and `proposals` inputs. This makes the declared source selection stable; a successful Nix evaluation or resolved lockfile is **not** established by the source edit alone. See the [operation trace](../../docs/contract-trace-20261029/contract-batch-32/downstream-gov-package-output/trace.jsonl) for source-backed Provided, declared checks, external dependencies, and unobserved outputs. Example checks and output packets are not final ADRS admission or deployment approval.
