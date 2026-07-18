CREATE OR REPLACE VIEW v_package_contract_abi_v1 AS
SELECT
  package_id,
  version,
  input_schema,
  output_schema,
  COALESCE(lifecycle_state, 'active') AS lifecycle_state,
  COALESCE(risk_tier, 'unknown') AS risk_tier
FROM package_versions;
