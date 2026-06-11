// policy/cue/typed-ledger.cue — PERMISSIVE-INITIAL def for the adrs large
// legacy typed ledgers (adrs repo, records/promoted/):
//   destructive-case.v1.jsonl / destructive-case-resolution.v1.jsonl /
//   purpose-lineage.v1.jsonl / usecase.v1.jsonl / spec-definition.v1.jsonl /
//   proof-evidence.v1.jsonl / artifact-manifest.v1.jsonl /
//   canon-result.v1.jsonl
//
// These ledgers carry thousands of heterogeneous append-only legacy rows
// whose strict shapes are NOT yet established. #TypedLedgerRow is
// deliberately minimal — it requires only a non-empty `kind` discriminator
// string and admits anything else — so the adrs gate (C2) can bind these
// files without forging stricter shapes than the data supports. Tightening
// into per-kind defs is future work, ledger by ledger; do NOT treat this
// def as an endorsement of the row shapes it admits.
package policy

#TypedLedgerRow: {
	kind: string & !=""
	...
}
