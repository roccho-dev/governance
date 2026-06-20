# Frozen Migration Source

`records/` and `generated/` are retained in this proposal as frozen migration
source/evidence only. They are not active authority and must not receive new
writes during the governance-records cutover.

Active governance package/check surfaces read the ADRS projection through the
`adrsRecords` flake input. Physical deletion or archival of these directories is
a later phase after classification, zero inbound references, retention, rollback,
and merged-SHA proof all pass.
