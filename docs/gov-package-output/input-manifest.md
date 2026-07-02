# gov-package-output input manifest

`input-manifest.jsonl` records the exact source closure used to build a `govPackageOutput.v1` packet.

The file is non-authority evidence. It does not make governance a decision source and it does not make a packet final-join active.

## Row shape

Each row is a `govPackageInputSource.v1` object.

| Field | Meaning |
|---|---|
| `kind` | Always `govPackageInputSource.v1`. |
| `role` | Why this source can affect the packet, such as `packages`, `assertions`, `receipts`, `providerCi`, `producerConfig`, or a caller supplied source role. |
| `sourceClass` | `path`, `inline`, `derived-config`, or accepted equivalent. |
| `path` | Source path or stable inline/derived marker. |
| `digest` | `sha256:<hex>` digest of the normalized input text. |
| `required` | Whether missing input must fail closed. |

## Digest rules

`inputLockDigest` is the `sha256:<hex>` digest of canonical JSONL rows sorted by canonical row JSON. The producer writes this digest into both `manifest.json` and `producer-provenance.json`.

`outputDigest` is the digest of sorted packet file name/content pairs, excluding `producer-provenance.json` to avoid self-reference. The verifier recomputes it from actual packet bytes.

## Required closure roles

| Role | Packet surface |
|---|---|
| repo metadata | `manifest.json` / `repo.json` |
| package inventory | `packages.jsonl` |
| package assertions | `assertions.jsonl` |
| package receipts | `receipts.jsonl` |
| README projection receipts | `readmeProjectionReceipt.jsonl` |
| provider CI intent/state | `provider-ci.jsonl` |
| findings | `findings.jsonl` |
| admission | `admission.jsonl` |
| producer configuration | `input-manifest.jsonl` provenance row |

Missing declared inputs, changed source input digests, and hand-edited packet outputs are verifier failures.
