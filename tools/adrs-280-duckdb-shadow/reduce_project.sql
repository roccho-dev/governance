-- ADRS #280 shadow reducer/projector.
-- Inputs are TEMP VIEWs created by verify.py:
--   raw_events, authorization_results, fixture_meta
-- This SQL owns lifecycle reduction and gov projection semantics.

CREATE OR REPLACE TEMP TABLE _events AS
SELECT
  schema::VARCHAR AS schema_name,
  "eventId"::VARCHAR AS event_id,
  "eventDigest"::VARCHAR AS event_digest,
  "adrId"::VARCHAR AS adr_id,
  kind::VARCHAR AS kind,
  "predecessorDigest"::VARCHAR AS predecessor_digest,
  "candidateDigest"::VARCHAR AS candidate_digest,
  "targetStateDigest"::VARCHAR AS target_state_digest,
  "supersedesStateDigest"::VARCHAR AS supersedes_state_digest,
  payload.purpose::VARCHAR AS purpose,
  payload.policy::VARCHAR AS policy,
  payload.scope::VARCHAR AS scope
FROM raw_events;

CREATE OR REPLACE TEMP TABLE _auth AS
SELECT
  schema::VARCHAR AS schema_name,
  "eventDigest"::VARCHAR AS event_digest,
  authorized::BOOLEAN AS authorized,
  "authorityPolicyDigest"::VARCHAR AS authority_policy_digest
FROM authorization_results;

CREATE OR REPLACE TEMP TABLE _meta AS
SELECT
  schema::VARCHAR AS schema_name,
  "sourceDigest"::VARCHAR AS source_digest,
  "authorityPolicyDigest"::VARCHAR AS authority_policy_digest,
  "reducerVersion"::VARCHAR AS reducer_version,
  "projectionAuthority"::BOOLEAN AS projection_authority,
  "rawSha256"::VARCHAR AS raw_sha256,
  "authorizationSha256"::VARCHAR AS authorization_sha256
FROM fixture_meta;

-- Closed input surfaces. Provider fields belong to transport evidence, not raw.jsonl.
SELECT error('raw.jsonl has unexpected top-level column: ' || name)
FROM pragma_table_info('raw_events')
WHERE name NOT IN (
  'schema','eventId','eventDigest','adrId','kind','predecessorDigest',
  'candidateDigest','targetStateDigest','supersedesStateDigest','payload'
)
LIMIT 1;
SELECT error('raw.jsonl is missing required top-level column: ' || required.name)
FROM (VALUES
  ('schema'),('eventId'),('eventDigest'),('adrId'),('kind'),('predecessorDigest'),
  ('candidateDigest'),('targetStateDigest'),('supersedesStateDigest'),('payload')
) AS required(name)
LEFT JOIN pragma_table_info('raw_events') actual ON actual.name = required.name
WHERE actual.name IS NULL
LIMIT 1;
SELECT error('authorization-results.jsonl has unexpected column: ' || name)
FROM pragma_table_info('authorization_results')
WHERE name NOT IN ('schema','eventDigest','authorized','authorityPolicyDigest')
LIMIT 1;
SELECT error('fixture-meta.json has unexpected column: ' || name)
FROM pragma_table_info('fixture_meta')
WHERE name NOT IN ('schema','sourceDigest','authorityPolicyDigest','reducerVersion','projectionAuthority','rawSha256','authorizationSha256')
LIMIT 1;

SELECT error('raw.jsonl payload must contain exactly purpose, policy, scope')
FROM raw_events
WHERE payload IS NULL
   OR array_length(json_keys(to_json(payload))) <> 3
   OR NOT list_contains(json_keys(to_json(payload)), 'purpose')
   OR NOT list_contains(json_keys(to_json(payload)), 'policy')
   OR NOT list_contains(json_keys(to_json(payload)), 'scope')
LIMIT 1;

SELECT error('fixture-meta must contain exactly one row')
FROM (SELECT count(*) AS n FROM _meta) q WHERE n <> 1;
SELECT error('fixture-meta schema mismatch') FROM _meta WHERE schema_name <> 'adrs280.materializedFixture.v1' LIMIT 1;
SELECT error('projection must remain non-authority') FROM _meta WHERE projection_authority IS DISTINCT FROM FALSE LIMIT 1;
SELECT error('fixture sourceDigest must equal rawSha256') FROM _meta WHERE source_digest <> raw_sha256 LIMIT 1;
SELECT error('event schema mismatch: ' || event_id)
FROM _events WHERE schema_name <> 'decisionEvent.v1' LIMIT 1;
SELECT error('unknown event kind: ' || kind)
FROM _events
WHERE kind NOT IN ('propose','amend','accept','reject','revoke','supersede')
LIMIT 1;
SELECT error('authorization schema mismatch')
FROM _auth WHERE schema_name <> 'decisionAuthorization.v1' LIMIT 1;
SELECT error('empty event identity')
FROM _events
WHERE event_id IS NULL OR event_id = '' OR event_digest IS NULL OR event_digest = '' OR adr_id IS NULL OR adr_id = ''
LIMIT 1;
SELECT error('duplicate eventId: ' || event_id)
FROM (SELECT event_id FROM _events GROUP BY event_id HAVING count(*) <> 1) q LIMIT 1;
SELECT error('duplicate eventDigest: ' || event_digest)
FROM (SELECT event_digest FROM _events GROUP BY event_digest HAVING count(*) <> 1) q LIMIT 1;
SELECT error('duplicate authorization result: ' || event_digest)
FROM (SELECT event_digest FROM _auth GROUP BY event_digest HAVING count(*) <> 1) q LIMIT 1;
SELECT error('missing authorization result: ' || e.event_id)
FROM _events e LEFT JOIN _auth a USING (event_digest)
WHERE a.event_digest IS NULL LIMIT 1;
SELECT error('orphan authorization result: ' || a.event_digest)
FROM _auth a LEFT JOIN _events e USING (event_digest)
WHERE e.event_digest IS NULL LIMIT 1;
SELECT error('authority policy digest mismatch: ' || e.event_id)
FROM _events e
JOIN _auth a USING (event_digest)
CROSS JOIN _meta m
WHERE a.authority_policy_digest <> m.authority_policy_digest
LIMIT 1;

SELECT error('missing predecessor for event: ' || e.event_id)
FROM _events e
LEFT JOIN _events p ON p.event_digest = e.predecessor_digest
WHERE e.predecessor_digest IS NOT NULL AND p.event_digest IS NULL
LIMIT 1;
SELECT error('cross-ADR predecessor for event: ' || e.event_id)
FROM _events e
JOIN _events p ON p.event_digest = e.predecessor_digest
WHERE p.adr_id <> e.adr_id
LIMIT 1;
SELECT error('each ADR must have exactly one root: ' || adr_id)
FROM (
  SELECT adr_id, count(*) FILTER (WHERE predecessor_digest IS NULL) AS roots
  FROM _events GROUP BY adr_id
) q
WHERE roots <> 1
LIMIT 1;

CREATE OR REPLACE TEMP TABLE _ordered AS
WITH RECURSIVE chain AS (
  SELECT e.*, 0::BIGINT AS depth
  FROM _events e
  WHERE predecessor_digest IS NULL
  UNION ALL
  SELECT e.*, c.depth + 1 AS depth
  FROM _events e
  JOIN chain c
    ON e.adr_id = c.adr_id
   AND e.predecessor_digest = c.event_digest
)
SELECT c.*, a.authorized, a.authority_policy_digest
FROM chain c
JOIN _auth a USING (event_digest);

SELECT error('cycle or disconnected event chain: ' || counts.adr_id)
FROM (
  SELECT e.adr_id, count(*) AS total, count(o.event_id) AS reached
  FROM _events e
  LEFT JOIN _ordered o ON o.event_id = e.event_id
  GROUP BY e.adr_id
) counts
WHERE total <> reached
LIMIT 1;

CREATE OR REPLACE TEMP TABLE _graph_flags AS
SELECT
  adr_id,
  coalesce(bool_or(children > 1), FALSE) AS conflict
FROM (
  SELECT p.adr_id, p.event_digest, count(c.event_id) AS children
  FROM _events p
  LEFT JOIN _events c
    ON c.adr_id = p.adr_id
   AND c.predecessor_digest = p.event_digest
  GROUP BY p.adr_id, p.event_digest
) q
GROUP BY adr_id;

-- State before each event is derived from the explicit predecessor depth only.
-- Input physical order and provider timestamps are intentionally irrelevant.
CREATE OR REPLACE TEMP TABLE _context AS
SELECT
  o.*,
  nullif((
    SELECT arg_max(
      CASE
        WHEN p.kind IN ('propose','amend') THEN p.candidate_digest
        WHEN p.kind IN ('reject','revoke') THEN '__NONE__'
      END,
      p.depth
    )
    FROM _ordered p
    WHERE p.adr_id = o.adr_id
      AND p.depth < o.depth
      AND p.authorized
      AND p.kind IN ('propose','amend','reject','revoke')
  ), '__NONE__') AS prior_candidate_digest,
  nullif((
    SELECT arg_max(
      CASE
        WHEN p.kind IN ('accept','supersede') THEN p.target_state_digest
        WHEN p.kind = 'revoke' THEN '__NONE__'
      END,
      p.depth
    )
    FROM _ordered p
    WHERE p.adr_id = o.adr_id
      AND p.depth < o.depth
      AND p.authorized
      AND p.kind IN ('accept','supersede','revoke')
  ), '__NONE__') AS prior_accepted_digest
FROM _ordered o;

-- Branches are represented as conflict and never reduced by an arbitrary winner.
CREATE OR REPLACE TEMP VIEW _linear_context AS
SELECT c.*
FROM _context c
JOIN _graph_flags g USING (adr_id)
WHERE NOT g.conflict;

SELECT error('candidate digest must be unique within ADR: ' || adr_id)
FROM (
  SELECT adr_id, candidate_digest
  FROM _events
  WHERE candidate_digest IS NOT NULL
  GROUP BY adr_id, candidate_digest
  HAVING count(*) > 1
) q LIMIT 1;

SELECT error('invalid propose transition: ' || event_id)
FROM _linear_context
WHERE authorized AND kind = 'propose'
  AND (prior_candidate_digest IS NOT NULL OR candidate_digest IS NULL OR target_state_digest IS NOT NULL OR supersedes_state_digest IS NOT NULL)
LIMIT 1;
SELECT error('invalid amend transition: ' || event_id)
FROM _linear_context
WHERE authorized AND kind = 'amend'
  AND (prior_candidate_digest IS NULL OR candidate_digest IS NULL OR target_state_digest IS DISTINCT FROM prior_candidate_digest OR supersedes_state_digest IS NOT NULL)
LIMIT 1;
SELECT error('invalid accept transition: ' || event_id)
FROM _linear_context
WHERE authorized AND kind = 'accept'
  AND (prior_candidate_digest IS NULL OR target_state_digest IS DISTINCT FROM prior_candidate_digest OR candidate_digest IS NOT NULL OR supersedes_state_digest IS NOT NULL)
LIMIT 1;
SELECT error('invalid reject transition: ' || event_id)
FROM _linear_context
WHERE authorized AND kind = 'reject'
  AND (prior_candidate_digest IS NULL OR target_state_digest IS DISTINCT FROM prior_candidate_digest OR candidate_digest IS NOT NULL OR supersedes_state_digest IS NOT NULL)
LIMIT 1;
SELECT error('invalid revoke transition: ' || event_id)
FROM _linear_context
WHERE authorized AND kind = 'revoke'
  AND (prior_accepted_digest IS NULL OR target_state_digest IS DISTINCT FROM prior_accepted_digest OR candidate_digest IS NOT NULL OR supersedes_state_digest IS NOT NULL)
LIMIT 1;
SELECT error('invalid supersede transition: ' || event_id)
FROM _linear_context
WHERE authorized AND kind = 'supersede'
  AND (
    prior_candidate_digest IS NULL OR prior_accepted_digest IS NULL
    OR target_state_digest IS DISTINCT FROM prior_candidate_digest
    OR supersedes_state_digest IS DISTINCT FROM prior_accepted_digest
    OR candidate_digest IS NOT NULL
  )
LIMIT 1;

SELECT error('candidate events require complete payload: ' || event_id)
FROM _linear_context
WHERE authorized AND kind IN ('propose','amend')
  AND (purpose IS NULL OR policy IS NULL OR scope IS NULL)
LIMIT 1;
SELECT error('transition-only events must not carry semantic payload: ' || event_id)
FROM _linear_context
WHERE authorized AND kind IN ('accept','reject','revoke','supersede')
  AND (purpose IS NOT NULL OR policy IS NOT NULL OR scope IS NOT NULL)
LIMIT 1;

CREATE OR REPLACE TEMP TABLE _state_values AS
SELECT
  o.adr_id,
  g.conflict,
  nullif(arg_max(
    CASE
      WHEN o.kind IN ('propose','amend') THEN o.candidate_digest
      WHEN o.kind IN ('reject','revoke') THEN '__NONE__'
    END,
    o.depth
  ) FILTER (WHERE o.authorized AND o.kind IN ('propose','amend','reject','revoke')), '__NONE__') AS candidate_head_digest,
  nullif(arg_max(
    CASE
      WHEN o.kind IN ('accept','supersede') THEN o.target_state_digest
      WHEN o.kind = 'revoke' THEN '__NONE__'
    END,
    o.depth
  ) FILTER (WHERE o.authorized AND o.kind IN ('accept','supersede','revoke')), '__NONE__') AS active_accepted_digest,
  arg_max(o.kind, o.depth) FILTER (WHERE o.authorized AND o.kind IN ('propose','amend','accept','reject','revoke','supersede')) AS last_authorized_kind
FROM _ordered o
JOIN _graph_flags g USING (adr_id)
GROUP BY o.adr_id, g.conflict;

CREATE OR REPLACE TEMP TABLE _adr_state AS
SELECT
  s.adr_id,
  CASE WHEN s.conflict THEN NULL ELSE s.candidate_head_digest END AS candidate_head_digest,
  CASE WHEN s.conflict THEN NULL ELSE s.active_accepted_digest END AS active_accepted_digest,
  CASE
    WHEN s.conflict THEN 'conflict'
    WHEN s.active_accepted_digest IS NOT NULL AND s.candidate_head_digest IS NOT NULL AND s.active_accepted_digest <> s.candidate_head_digest THEN 'accepted-with-pending-amendment'
    WHEN s.active_accepted_digest IS NOT NULL THEN 'accepted'
    WHEN s.candidate_head_digest IS NOT NULL THEN 'proposed'
    WHEN s.last_authorized_kind = 'reject' THEN 'rejected'
    WHEN s.last_authorized_kind = 'revoke' THEN 'revoked'
    ELSE 'invalid'
  END AS lifecycle
FROM _state_values s;

CREATE OR REPLACE TEMP TABLE _accepted_payload AS
SELECT
  s.adr_id,
  s.active_accepted_digest,
  e.purpose,
  e.policy,
  e.scope
FROM _adr_state s
LEFT JOIN _events e
  ON e.adr_id = s.adr_id
 AND e.candidate_digest = s.active_accepted_digest
 AND e.kind IN ('propose','amend');

CREATE OR REPLACE TEMP VIEW adr_current_export AS
SELECT
  s.adr_id AS sort_key,
  to_json(struct_pack(
    schema := 'adr.current.v1',
    adrId := s.adr_id,
    lifecycle := s.lifecycle,
    candidateHeadDigest := s.candidate_head_digest,
    activeAcceptedDigest := s.active_accepted_digest,
    sourceDigest := m.source_digest,
    authorityPolicyDigest := m.authority_policy_digest,
    reducerVersion := m.reducer_version,
    projectionAuthority := FALSE
  )) AS json_line
FROM _adr_state s CROSS JOIN _meta m;

CREATE OR REPLACE TEMP VIEW accepted_decision_current_export AS
SELECT
  s.adr_id AS sort_key,
  to_json(struct_pack(
    schema := 'acceptedDecision.current.v1',
    adrId := s.adr_id,
    acceptedStateDigest := s.active_accepted_digest,
    purpose := p.purpose,
    policy := p.policy,
    scope := p.scope,
    sourceDigest := m.source_digest,
    authorityPolicyDigest := m.authority_policy_digest,
    reducerVersion := m.reducer_version,
    projectionAuthority := FALSE
  )) AS json_line
FROM _adr_state s
JOIN _accepted_payload p USING (adr_id)
CROSS JOIN _meta m
WHERE s.active_accepted_digest IS NOT NULL
  AND s.lifecycle <> 'conflict';

CREATE OR REPLACE TEMP VIEW gov_input_export AS
SELECT
  s.adr_id AS sort_key,
  to_json(struct_pack(
    schema := 'gov-input.v1',
    adrId := s.adr_id,
    lifecycle := s.lifecycle,
    acceptedStateDigest := s.active_accepted_digest,
    candidateHeadDigest := s.candidate_head_digest,
    purpose := p.purpose,
    policy := p.policy,
    scope := p.scope,
    admissionAllowed := s.lifecycle IN ('accepted','accepted-with-pending-amendment'),
    sourceDigest := m.source_digest,
    authorityPolicyDigest := m.authority_policy_digest,
    reducerVersion := m.reducer_version,
    projectionAuthority := FALSE
  )) AS json_line
FROM _adr_state s
LEFT JOIN _accepted_payload p USING (adr_id)
CROSS JOIN _meta m;
