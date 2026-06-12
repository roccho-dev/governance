// records/specs/catalog-membership.v1.jsonl — SSOT marker for the
// spec.packages membership set (which packageIds the emitted catalog covers).
package policy

#CatalogMembership: {
	kind:            "specs.catalogMembership.v1"
	packageId:       =~"^[a-z0-9][a-z0-9_-]*$"
	inSpecPackages:  bool
	sourceAuthority: string & !=""
	migratedAt:      string & !=""
	// membership change provenance (set when inSpecPackages is flipped after
	// the initial migration; ref points at the recording ADR).
	membershipChangedAt?: string & !=""
	membershipChangeRef?: string & !=""
}
