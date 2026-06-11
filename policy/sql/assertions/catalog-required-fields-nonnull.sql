-- assertion: for catalog-membership target rows, the catalog projection input
-- source.rawDefinition must be a JSON object (make-spec-catalog.py hard-fails
-- otherwise) and the machine-enforced catalog source fields must be non-null.
--
-- Of the 28 emitted catalog fields: 1 is derived (package = packageId),
-- 6 carry declared defaults (implementationContract, migrationContract,
-- acceptanceContract, namingContract, riskMitigationContract -> null;
-- usesExtensions -> []), 21 are nominally required by the projection.
-- 18 of those 21 are enforced here; the remaining 3 (dependencyUse,
-- publicInterface, checkPackageContract) have known historical gaps in the
-- migrated data and are tracked NON-blocking as obligation debt
-- (records-gate --report, debtClass catalog-field-gap).
-- 0 rows = pass.
WITH members AS (
  SELECT json_extract_string(json, '$.packageId') AS packageId
  FROM read_json(getvariable('root') || '/records/specs/catalog-membership.v1.jsonl',
                 format = 'newline_delimited', records = false)
  WHERE json_extract_string(json, '$.inSpecPackages') = 'true'
), contracts AS (
  SELECT json_extract_string(json, '$.packageId') AS packageId,
         json_extract(json, '$.source.rawDefinition') AS rawDefinition
  FROM read_json(getvariable('root') || '/records/specs/package-contract.v1.jsonl',
                 format = 'newline_delimited', records = false)
), member_contracts AS (
  SELECT c.packageId, c.rawDefinition
  FROM contracts c JOIN members m USING (packageId)
), required_fields (field) AS (
  VALUES ('packageRole'), ('responsibility'), ('mission'), ('provides'),
         ('requires'), ('envNeeds'), ('releaseNeeds'), ('artifactContract'),
         ('runtimeRequirements'), ('preflightRequiredTools'),
         ('officialOutput'), ('packageContents'), ('forbiddenOutputs'),
         ('allowedCompatCommands'), ('requiredCommands'), ('blockedWhen'),
         ('outputReviewGate'), ('requiredCheckPackages')
)
SELECT 'membership-rawdefinition-not-object' AS rule,
       packageId,
       coalesce(json_type(rawDefinition), '<missing>') AS detail
FROM member_contracts
WHERE rawDefinition IS NULL OR json_type(rawDefinition) != 'OBJECT'
UNION ALL
SELECT 'catalog-required-field-null' AS rule,
       mc.packageId,
       rf.field AS detail
FROM member_contracts mc
CROSS JOIN required_fields rf
WHERE json_type(mc.rawDefinition) = 'OBJECT'
  AND json_extract(mc.rawDefinition, '$.' || rf.field) IS NULL;
