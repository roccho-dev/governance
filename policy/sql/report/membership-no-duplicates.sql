-- assertion: the catalog-membership ledger has no duplicate packageId
-- (the 126-member set is a set). 0 rows = pass.
SELECT 'membership-duplicate-packageid' AS rule,
       json_extract_string(json, '$.packageId') AS packageId,
       'count=' || count(*) AS detail
FROM read_json(getvariable('root') || '/records/specs/catalog-membership.v1.jsonl',
               format = 'newline_delimited', records = false)
GROUP BY 2
HAVING count(*) > 1;
