// adrs typed-ladder record kinds (records/{raw,promoted,relations} in the
// adrs repo). The ladder does not live in this repo; these schemas are the
// policy declaration the gate applies whenever the corresponding files are
// present under the validated root (tools/records-gate.py treats them as
// optional bindings). Shapes follow the canonical ladder on
// adrs claude/adrs-typed-ladder-260611.
package policy

// records/raw/adr.v1.jsonl — intake. Heterogeneous legacy rows are retained
// append-only, so identity is "id or adrId"; kind admits the pre-typed
// legacy values. ("at least one of id/adrId" is not expressible as a
// vet-resolvable CUE disjunction — presence-discriminated disjuncts stay
// incomplete; specsless_readiness.py enforces it behaviorally.)
#AdrRaw: {
	kind:   "adr.raw.v1" | "proposal" | "observation"
	adrId?: string & !=""
	id?:    string & !=""
	...
}

// records/promoted/adr.v1.jsonl — promoted ADR ledger.
#AdrPromoted: {
	id:           string & !=""
	kind:         string & !=""
	status:       string & !=""
	promotedFrom: string & !=""
	title:        string & !=""
	...
}

// records/relations/adr-promotion.v1.jsonl — promotion relations.
// Three historical relation kinds are retained append-only.
#AdrPromotionRelation: {
	kind!: "adr.relation.v1"
	from!: {...}
	to!: {...}
	relation!: string & !=""
	...
} | {
	kind!:         "adr.promotion.relation.v1"
	rawAdrId!:     string & !=""
	promotedId!:   string & !=""
	promotedKind!: string & !=""
	...
} | {
	kind!:        "adr.promotionRelation.v1"
	sourceAdrId!: string & !=""
	targetId!:    string & !=""
	targetKind!:  string & !=""
	...
}
