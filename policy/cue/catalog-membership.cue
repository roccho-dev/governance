// records/specs/catalog-membership.v1.jsonl — SSOT marker for the
// spec.packages membership set (which packageIds the emitted catalog covers).
package policy

#CatalogMembership: {
	kind:            "specs.catalogMembership.v1"
	packageId:       =~"^[a-z0-9][a-z0-9_-]*$"
	inSpecPackages:  bool
	sourceAuthority: string & !=""
	migratedAt:      string & !=""
}
