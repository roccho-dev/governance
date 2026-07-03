# required repo packet org join

## Purpose

Phase D adds the governance-side path from accepted required repo rows to packet-aware org join evidence.

The implementation is evidence/admission precursor only. It does not claim final-scope gate cutover, branch protection authority, downstream rollout, or all-package final admission.

## D1 required repo universe

Input rows use `govRequiredRepo.v1` or accepted equivalent.

Required fields:

| Field | Meaning |
|---|---|
| `repoId` | required repository identity |
| `repoClass` | accepted repository class |
| `requiredOutput` | output required from that repo, usually `govPackageOutput.v1` |
| `requiredProducer` | expected producer repo for the packet |
| `enforcementMode` | current enforcement mode |
| `effectiveFrom` | effective date or accepted marker |
| `owner` | owner routing value |

The reader fails closed or emits deterministic blocking findings for missing fields, duplicate `repoId`, malformed rows, or unknown `repoClass`.

## D2 packet registry and transport

Packet source rows use `govPackagePacketSource.v1` or accepted equivalent.

Required fields:

| Field | Meaning |
|---|---|
| `repoId` | required repo this packet belongs to |
| `sourceKind` | fixture, local path, flake output, CI artifact, or pinned repo artifact |
| `sourceRepo` | repository that owns the packet source |
| `sourceRev` | pinned source revision |
| `packetPath` | packet path or locator relative to packet root |
| `packetDigest` | pinned packet digest |
| `producerRev` | expected producer revision |
| `freshness` | freshness rule for stale detection |

Missing or unpinned sources are blocking findings.

## D3 packet findings

The checker emits deterministic actionable findings for:

- missing packet source
- missing packet path
- unavailable packet path
- malformed packet
- unsupported packet schema
- packet repo mismatch
- stale source revision
- packet digest mismatch
- missing producer provenance
- producer repo mismatch
- producer revision mismatch
- output digest mismatch

Findings include `repoId`, `expected`, `actual`, `delta`, `diagnosticClass`, `likelyOwner`, and `nextAction`.

## D4 org join

`tools/check-package-required-repo-org-join.py` combines:

```text
required repo universe
x packet registry
x packet findings
x producer provenance signals
```

A repo receives `organization-active` only when it is required, has a packet source, has a readable packet, passes packet/provenance checks, and has no blocking packet findings.

## Command

```text
python3 tools/check-package-required-repo-org-join.py check \
  --universe fixtures/required-repo-org-join/clean/universe.jsonl \
  --registry fixtures/required-repo-org-join/clean/registry.jsonl \
  --packet-root <packet-root> \
  --strict
```

Selftest:

```text
python3 tools/check-package-required-repo-org-join.py selftest
```
