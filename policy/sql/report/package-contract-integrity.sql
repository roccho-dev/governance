-- assertion: package-contract packageId is unique and recordDigest is a
-- non-empty sha256 hex. 0 rows = pass.
WITH contracts AS (
  SELECT json_extract_string(json, '$.packageId')    AS packageId,
         json_extract_string(json, '$.recordDigest') AS recordDigest
  FROM read_json(getvariable('root') || '/records/specs/package-contract.v1.jsonl',
                 format = 'newline_delimited', records = false)
)
SELECT 'package-contract-duplicate-packageid' AS rule,
       packageId,
       'count=' || count(*) AS detail
FROM contracts
GROUP BY packageId
HAVING count(*) > 1
UNION ALL
SELECT 'package-contract-bad-record-digest' AS rule,
       packageId,
       coalesce(recordDigest, '<null>') AS detail
FROM contracts
WHERE recordDigest IS NULL
   OR NOT regexp_full_match(recordDigest, '[0-9a-f]{64}');
