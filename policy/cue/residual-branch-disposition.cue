// records/decisions/residual-branch-disposition.v1.jsonl — disposition ledger
// for branches removed from the active refs/heads namespace of SSOT bares.
// Bound via policy/interface.json: cue vet -d '#ResidualBranchDisposition'.
//
// Principle: what survives is not the branch but rehydratable evidence —
// every row must pin (a) the in-place git-native archive ref
// (refs/archive/..., outside refs/heads, so it never appears in branch
// listings yet keeps the objects gc-reachable in the bare) and (b) a
// verified git bundle stored in the evidence-archive repo (immutable blob;
// uri is swapped, not the row rewritten, if object storage arrives later).
//
// This def is deliberately CLOSED (no trailing `...`): unknown or
// misspelled fields fail vet instead of passing silently.
package policy

#ResidualBranchDisposition: {
	kind:          "governance.residualBranchDisposition.v1"
	schemaVersion: "v1"
	repo:          string & !=""
	branch:        string & !=""
	// full 40-hex head OID of the archived branch tip.
	head: =~"^[0-9a-f]{40}$"
	// keep-reference : content not folded; retained as consultable reference
	// accept-fold    : valuable subset folded into main before archiving
	// reject         : proposal declined on review
	// superseded     : content already succeeded by main lineage
	disposition: "keep-reference" | "accept-fold" | "reject" | "superseded"
	rationale:   string & !=""
	// what would allow the archive itself to be retired; null = permanent.
	supersedeCondition: string | null
	// in-place archive ref on the originating bare (non-branch namespace).
	archiveRef: =~"^refs/archive/"
	archive: {
		type: "git-bundle"
		// evidence-archive repo path now; object-storage uri later.
		uri:      string & !=""
		sha256:   =~"^[0-9a-f]{64}$"
		verified: true
		// ref->oid pairs as reported by `git bundle list-heads`; lets the
		// gate-side reader cross-check bundle vs archiveRef mechanically.
		listHeads: [{ref: string & !="", sha: =~"^[0-9a-f]{40}$"}, ...{ref: string & !="", sha: =~"^[0-9a-f]{40}$"}]
	}
	// executable restore steps; at least one command.
	rehydrate: [string & !="", ...string & !=""]
	recordedAt: string & !=""
}
