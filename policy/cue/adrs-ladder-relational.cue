// policy/cue/adrs-ladder-relational.cue — adrs-internal relational
// constraints (#AdrsLadder) over the typed promotion ladder
// (records/{raw,promoted,relations} in the adrs repo).
//
// Vetted via the declaration-driven plumbing (adrs interface.json): the
// grouped ladder jsonl files are bundled into one labeled JSON
// {raw, promoted, relations} and vetted with
//   cue vet policy/cue/*.cue all.json -d '#AdrsLadder'
//
// Constraints:
//   (a) every promoted row's promotedFrom (when present) names an existing
//       raw intake row (raw identity is "id or adrId"; see #AdrRaw note).
//   (b) every promoted row carrying promotedFrom is admitted by a matching
//       relation row (any of the three historical relation kinds; see
//       #AdrPromotionRelation) linking promotedFrom -> promoted id.
package policy

import "list"

#AdrsLadder: {
	raw: [...{...}] // records/raw/adr.v1.jsonl
	promoted: [...{...}] // records/promoted/adr.v1.jsonl
	relations: [...{...}] // records/relations/adr-promotion.v1.jsonl

	// raw identity set: union of `id` and `adrId` values (legacy rows carry
	// either or both).
	_rawIds: [for r in raw for k, v in r if k == "id" || k == "adrId" {v}]

	// "rawId::promotedId" admit keys across the three relation kinds.
	_relationAdmits: [
		for r in relations if r.kind == "adr.relation.v1" {"\(r.from.id)::\(r.to.id)"},
		for r in relations if r.kind == "adr.promotion.relation.v1" {"\(r.rawAdrId)::\(r.promotedId)"},
		for r in relations if r.kind == "adr.promotionRelation.v1" {"\(r.sourceAdrId)::\(r.targetId)"},
	]

	// every named violation list must be empty for the gate to pass.
	violations: [string]: list.MaxItems(0)

	// NOTE: the guards below are sequential comprehension clauses (if ... let
	// ... if ...), NOT `&&` — CUE `&&` does not short-circuit, so an
	// interpolation of pf in the second operand would error on rows without
	// promotedFrom instead of being skipped.

	// (a) promotedFrom resolves to an existing raw row.
	violations: "promoted-promotedfrom-not-in-raw": [
		for p in promoted
		let pf = *(p.promotedFrom & string) | null
		if pf != null
		if !list.Contains(_rawIds, pf) {
			{rule: "promoted-promotedfrom-not-in-raw", promotedId: p.id, detail: "promotedFrom=\(pf)"}
		},
	]

	// (b) promotedFrom-carrying promoted rows have a matching relation row.
	violations: "promoted-promotion-relation-missing": [
		for p in promoted
		let pf = *(p.promotedFrom & string) | null
		if pf != null
		let key = "\(pf)::\(p.id)"
		if !list.Contains(_relationAdmits, key) {
			{rule: "promoted-promotion-relation-missing", promotedId: p.id, detail: "promotedFrom=\(pf)"}
		},
	]
}
