# gov-package-output provenance verification

## Purpose

This document records the Phase C producer/provenance boundary for `govPackageOutput.v1` packets.

The verifier treats packet provenance as a claim to recompute, not as proof by itself.

## Verifier entrypoint

```text
python3 tools/check-package-gov-package-output-provenance.py verify --packet <packet> --source-root <source-root> --require-pass
```

The same script also exposes:

```text
python3 tools/check-package-gov-package-output-provenance.py build --config <config.json> --out <packet>
python3 tools/check-package-gov-package-output-provenance.py selftest
```

## Checked claims

| Claim | Verification |
|---|---|
| `producerRepo` | must equal the accepted governance producer repo or an explicit verifier argument |
| `producerRev` | must match the caller supplied expected producer revision when supplied |
| `producerDigest` | must match the caller supplied expected producer digest when supplied |
| `inputLockDigest` | recomputed from `input-manifest.jsonl` |
| `outputDigest` | recomputed from packet files, excluding `producer-provenance.json` |
| `packetFiles` | actual files must be declared by the manifest |
| source inputs | declared path inputs must still exist and match their digests |

## Diagnostic contract

Failure rows are machine-readable and include:

```text
diagnosticClass / expected / actual / delta / likelyOwner / nextAction
```

## Boundary

This verifier is producer/provenance quality evidence only. It does not claim branch protection, downstream rollout, accepted ADRS meaning, or final-scope active admission.
