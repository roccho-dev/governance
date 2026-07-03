# gov-package-output provenance fixtures

These fixtures exercise producer provenance and source closure checks.

They are tool selftest evidence only.

## Matrix

| Case | Expected class |
|---|---|
| clean | pass |
| shape-only-no-provenance | missingProducerProvenance |
| fake-matching-provenance | staleProducerRev |
| stale-producer-rev | staleProducerRev |
| wrong-producer-digest | producerDigestMismatch |
| missing-input-path | missingSourceInput |
| wrong-input-lock-digest | inputLockDigestMismatch |
| wrong-output-digest | outputDigestMismatch |
| undeclared-source-input | undeclaredOutputFile |
