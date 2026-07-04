# SSOT publish gate acceptance packet

Parent: governance #125  
Phase issue: governance #115

## Selected provider

The selected provider for #115 is:

```text
bare repo SSOT + checked mirror publish gate
```

Provider id:

```text
bare-repo-ssot-checked-mirror-publish
```

This provider is acceptable only when `refs/heads/main` mirror publish attempts are refused unless `gov-final-scope-purpose-join / gate` accepts the exact target SHA.

## Acceptance packet

The acceptance packet lives at:

```text
docs/final-scope-purpose-join/ssot-publish-gate-acceptance.json
```

The packet must contain:

- selected ref: `refs/heads/main`;
- final gate name: `gov-final-scope-purpose-join / gate`;
- provider id;
- at least one exact target SHA allow receipt;
- at least one missing final gate reject receipt;
- at least one stale target SHA reject receipt;
- at least one digest or SHA mismatch reject receipt;
- rollback instructions;
- audit receipts with target SHA, gate identity, decision, actor, timestamp, and path.

## Verifier

Run:

```sh
python3 tools/check-package-ssot-publish-gate-acceptance.py selftest --json
```

The verifier checks packet shape and acceptance evidence requirements. It is run by the governance package selftest loop because its name starts with `check-package-`.

## Boundary

The checked-in packet is a fixture until populated from a real `refs/heads/main` provider execution log.

Do not close governance #115 merely because this verifier passes. Close #115 only after the packet or attached external evidence comes from active selected-ref enforcement.
