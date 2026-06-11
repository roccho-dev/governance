-- assertion: dependency-edge endpoints resolve to existing package-contract
-- packageIds (fromPackageId and every member of toPackageIds). 0 rows = pass.
WITH contracts AS (
  SELECT json_extract_string(json, '$.packageId') AS packageId
  FROM read_json(getvariable('root') || '/records/specs/package-contract.v1.jsonl',
                 format = 'newline_delimited', records = false)
), edges AS (
  SELECT json_extract_string(json, '$.fromPackageId') AS fromPackageId,
         json_extract_string(json, '$.requires')      AS requires,
         CAST(json_extract(json, '$.toPackageIds') AS VARCHAR[]) AS toPackageIds
  FROM read_json(getvariable('root') || '/records/specs/dependency-edge.v1.jsonl',
                 format = 'newline_delimited', records = false)
)
SELECT 'dependency-edge-from-not-in-contract' AS rule,
       e.fromPackageId AS packageId,
       'requires=' || e.requires AS detail
FROM edges e
LEFT JOIN contracts c ON c.packageId = e.fromPackageId
WHERE c.packageId IS NULL
UNION ALL
SELECT 'dependency-edge-to-not-in-contract' AS rule,
       t.toPackageId AS packageId,
       'from=' || e.fromPackageId AS detail
FROM edges e, unnest(e.toPackageIds) AS t (toPackageId)
LEFT JOIN contracts c ON c.packageId = t.toPackageId
WHERE c.packageId IS NULL;
