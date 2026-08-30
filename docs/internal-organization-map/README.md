# Internal organization map

This directory contains the deterministic non-authority current-world input for `roccho-dev/adrs#331`.

```text
source.jsonl
→ tools/build-internal-organization-map.py
→ six accepted current-state lanes
→ tools/build-control-surface-bundle.py
→ controlSurface.bundle.v1
```

The bounded V1 universe is the eight repositories named by the package-control loop in `roccho-dev/adrs#243`: ADRS, Governance, HQ, Ops, UI, edits, diagrams, and envs. Each repository is pinned to one exact Git revision. Every observed `packages/*` surface is present. Repositories without that inventory surface remain present with `inventoryState=unknown`.

`requiredPackageExpectations` preserves the target package names from `adrs#243` as proposed expectations. It is not implementation authority and does not turn name similarity into conformance. `observed`, `missing-or-unmatched`, and `unknown` remain distinct.

The generated JSON, HTML, URL, layout, screenshot, and receipt are never meaning authority. This bundle does not prove all-package conformance, deployment, production readiness, public release, or business outcome.
