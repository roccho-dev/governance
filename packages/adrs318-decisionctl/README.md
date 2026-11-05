# ADRS decisionctl

Provider-neutral, fail-closed ADR lifecycle reducer for `governance#204` / `adrs#318`.

```text
GitHub adapter output
  -> adrs.lifecycleEvent.v1 JSONL
  -> explicit authority grants
  -> decisions.current.jsonl
  -> views/<type>/<status>.jsonl
  -> routes.logical.json
```

The existing ADRS `decisionEvent.v1` name is deliberately **not reused** because the closed PR #203 proof used that name for a different shape. GitHub identifiers and pagination metadata are transport evidence and never enter semantic digests.

```sh
python3 decisionctl.py run --events events.jsonl --grants grants.jsonl --out out
python3 decisionctl.py verify --out out
python3 -m unittest discover -s tests -v
```

No URL, object-storage binding, authentication credential, accepted-authority change, cutover, or legacy retirement is owned here.
