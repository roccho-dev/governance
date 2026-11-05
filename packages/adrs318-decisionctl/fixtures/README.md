# Fixtures

- `events.valid.jsonl` + `grants.valid.jsonl`: accepted architecture decision.
- `events.unauthorized.jsonl`: protected event by an actor without a matching grant; current state remains proposed.

All records use `adrs.lifecycleEvent.v1`, deliberately distinct from historical incompatible `decisionEvent.v1` shapes.
