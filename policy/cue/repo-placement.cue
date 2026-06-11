// records/specs/repo-placement.v1.jsonl — authoritative placement attrs.
// Two row classes exist in the ledger, discriminated by status:
//   - projected rows (from package-contract; carry recordDigest + placement
//     attrs; status absent -> schema default "<projected>")
//   - planned rows (status="planned"; successor-repo declarations without a
//     projection digest yet)
package policy

#RepoPlacement: {
	kind:          "governance.repoPlacement.v1"
	packageId:     =~"^[a-z0-9][a-z0-9_-]*$"
	repoSourceUri: string & !=""
	status:        *"<projected>" | "planned"
	if status == "planned" {
		legacyRepoId!:    string & !=""
		successorRepoId!: string & !=""
	}
	if status != "planned" {
		recordDigest!: =~"^[0-9a-f]{64}$"
		// null repoCategory is admissible: make-spec-catalog.py applies the
		// fallback (fixed -> "spec", else "feat") at projection time.
		repoCategory!: null | (string & !="")
		repoId!:       string & !=""
		// one historical row carries a structured sibling-repository placement.
		repoPlacement!:   "fixed" | "ownRepo" | {...}
		sourceAuthority!: string & !=""
	}
	...
}
