# Removed Local Governance Records

`records/` and `generated/` are removed from the active governance tree in this proposal.

They were previously retained as frozen migration source, but the final `gov*` boundary is stricter: `governance` must not carry local accepted-definition records or local generated cache as active tree content.

Historical access remains through Git history, the pre-removal commit, and ADR-derived projection bundles. Any future consumer must read digest-pinned ADR-derived governance bundles, not `governance/records` or `governance/generated`.

This file is evidence of the deletion boundary only. It is not approval for policy retirement, consumer cutover, repository deletion, or runtime implementation.
