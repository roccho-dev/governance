-- assertion (promotion-policy stub, policy/promotion-policy.md): every
-- package-contract row that declares a BREAKING change
-- (lifecycle.changeClass = 'breaking') must be admitted by a matching
-- governance.breakingChangeEvidence.v1 row (same packageId, newRecordDigest =
-- the contract recordDigest, passing feat gate enforced by CUE shape).
-- No current contract row declares changeClass=breaking, so this passes with
-- 0 violations on current data; it becomes load-bearing the first time a
-- breaking revision is recorded. 0 rows = pass.
WITH breaking AS (
  SELECT json_extract_string(json, '$.packageId')    AS packageId,
         json_extract_string(json, '$.recordDigest') AS recordDigest
  FROM read_json(getvariable('root') || '/records/specs/package-contract.v1.jsonl',
                 format = 'newline_delimited', records = false)
  WHERE json_extract_string(json, '$.lifecycle.changeClass') = 'breaking'
), evidence AS (
  SELECT json_extract_string(json, '$.packageId')       AS packageId,
         json_extract_string(json, '$.newRecordDigest') AS newRecordDigest
  FROM read_json(getvariable('root') || '/records/feat/breaking-change-evidence.v1.jsonl',
                 format = 'newline_delimited', records = false)
  WHERE json_extract_string(json, '$.schemaEstablishment') IS DISTINCT FROM 'true'
)
SELECT 'breaking-change-without-feat-evidence' AS rule,
       b.packageId,
       'recordDigest=' || b.recordDigest AS detail
FROM breaking b
LEFT JOIN evidence e
  ON e.packageId = b.packageId AND e.newRecordDigest = b.recordDigest
WHERE e.packageId IS NULL;
