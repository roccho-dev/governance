-- assertion: every catalog-membership member (inSpecPackages=true) references
-- an existing package-contract row with an admissible status.
-- Admissible statuses mirror the enforced invariant (make-spec-catalog.py
-- requires existence; specsless_readiness.py admits {'accepted','planned'}).
-- The stricter accepted-only target state is tracked NON-blocking as
-- obligation debt (records-gate --report, debtClass membership-member-not-accepted).
-- 0 rows = pass.
WITH contracts AS (
  SELECT json_extract_string(json, '$.packageId') AS packageId,
         json_extract_string(json, '$.status')    AS status
  FROM read_json(getvariable('root') || '/records/specs/package-contract.v1.jsonl',
                 format = 'newline_delimited', records = false)
), members AS (
  SELECT json_extract_string(json, '$.packageId') AS packageId
  FROM read_json(getvariable('root') || '/records/specs/catalog-membership.v1.jsonl',
                 format = 'newline_delimited', records = false)
  WHERE json_extract_string(json, '$.inSpecPackages') = 'true'
)
SELECT 'membership-packageid-in-contract' AS rule,
       m.packageId                        AS packageId,
       coalesce(c.status, '<missing-contract>') AS detail
FROM members m
LEFT JOIN contracts c USING (packageId)
WHERE c.packageId IS NULL OR c.status NOT IN ('accepted', 'planned');
