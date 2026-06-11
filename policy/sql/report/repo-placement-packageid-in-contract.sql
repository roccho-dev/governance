-- assertion: every repo-placement row references an existing package-contract
-- packageId. 0 rows = pass.
WITH contracts AS (
  SELECT json_extract_string(json, '$.packageId') AS packageId
  FROM read_json(getvariable('root') || '/records/specs/package-contract.v1.jsonl',
                 format = 'newline_delimited', records = false)
), placements AS (
  SELECT json_extract_string(json, '$.packageId') AS packageId
  FROM read_json(getvariable('root') || '/records/specs/repo-placement.v1.jsonl',
                 format = 'newline_delimited', records = false)
)
SELECT 'repo-placement-packageid-not-in-contract' AS rule,
       p.packageId,
       '<missing-contract>' AS detail
FROM placements p
LEFT JOIN contracts c USING (packageId)
WHERE c.packageId IS NULL;
