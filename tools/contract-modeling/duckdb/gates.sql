WITH failures AS (
  SELECT 'G001' AS gate_id, 'approved-raw-direct-query' AS reason
  WHERE EXISTS (
    SELECT 1
    FROM query_contracts AS query
    JOIN decisions AS decision USING (request_id)
    WHERE decision.approved AND query.raw_direct_sql_used
  )
  UNION ALL
  SELECT 'G002', 'equivalent-duplicate-new-model'
  WHERE EXISTS (SELECT 1 FROM decisions WHERE decision = 'create_new_model' AND equivalent_count > 0)
  UNION ALL
  SELECT 'G003', 'ambiguous-approved-model'
  WHERE EXISTS (SELECT 1 FROM decisions WHERE approved AND ambiguous)
  UNION ALL
  SELECT 'G004', 'breaking-without-destructive-and-migration-proof'
  WHERE EXISTS (
    SELECT 1 FROM decisions
    WHERE approved AND breaking AND (destructive_count = 0 OR NOT migration_lossless)
  )
  UNION ALL
  SELECT 'G005', 'projection-or-query-contract-incomplete'
  WHERE EXISTS (
    SELECT 1 FROM decisions
    WHERE approved AND (
      (decision = 'add_projection' AND NOT projection_present)
      OR (decision = 'add_query_contract' AND NOT query_present)
    )
  )
  UNION ALL
  SELECT 'G006', 'current-not-generated-by-promotion'
  WHERE EXISTS (SELECT 1 FROM current_state WHERE generated_by <> 'promotion-ledger')
  UNION ALL
  SELECT 'G007', 'shared-abi-proof-failed'
  WHERE (SELECT value_int FROM metrics WHERE key = 'shared_abi_ok') <> 1
  UNION ALL
  SELECT 'G008', 'replay-equality-failed'
  WHERE (SELECT value_int FROM metrics WHERE key = 'replay_equal') <> 1
  UNION ALL
  SELECT 'G009', 'active-abi-budget-exceeded'
  WHERE (SELECT value_int FROM metrics WHERE key = 'active_abi') >
        (SELECT value_int FROM metrics WHERE key = 'max_active_abi')
  UNION ALL
  SELECT 'G010', 'new-model-growth-budget-exceeded'
  WHERE (SELECT value_num FROM metrics WHERE key = 'new_model_ratio') >
        (SELECT value_num FROM metrics WHERE key = 'max_new_model_ratio')
  UNION ALL
  SELECT 'G011', 'missing-owner-reason-purpose-or-digest'
  WHERE EXISTS (
    SELECT 1 FROM decisions
    WHERE owner = '' OR reason = '' OR purpose_path_digest = '' OR policy_digest = ''
  )
  UNION ALL
  SELECT 'G012', 'unexplained-active-legacy-row'
  WHERE EXISTS (
    SELECT 1 FROM legacy_migration
    WHERE disposition NOT IN ('mapped', 'retired', 'quarantined') OR owner = '' OR reason = ''
  )
  UNION ALL
  SELECT 'G013', 'required-package-contract-incomplete-or-weaker'
  WHERE EXISTS (SELECT 1 FROM packages WHERE NOT complete OR weakens_policy)
  UNION ALL
  SELECT 'G014', 'candidate-or-receipt-sha-mismatch'
  WHERE EXISTS (SELECT 1 FROM packages WHERE candidate_sha <> receipt_sha)
  UNION ALL
  SELECT 'G015', 'effect-without-readback'
  WHERE EXISTS (SELECT 1 FROM effects WHERE effectful AND readback_digest = '')
  UNION ALL
  SELECT 'G016', 'legacy-consumer-remains-after-cutover'
  WHERE (SELECT value_int FROM metrics WHERE key = 'cutover_active') = 1
    AND (SELECT value_int FROM metrics WHERE key = 'legacy_active_consumers') <> 0
  UNION ALL
  SELECT 'G017', 'trusted-derived-field-present'
  WHERE (SELECT value_int FROM metrics WHERE key = 'forbidden_derived_fields') <> 0
  UNION ALL
  SELECT 'G018', 'accepted-decision-not-pinned'
  WHERE (SELECT value_int FROM metrics WHERE key = 'decision_pinned') <> 1
)
SELECT gate_id, reason FROM failures ORDER BY gate_id;
