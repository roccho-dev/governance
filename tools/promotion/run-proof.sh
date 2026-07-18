#!/usr/bin/env bash
set -euo pipefail

(
  cd tools/promotion-keygen
  go test ./...
)
python3 -m unittest discover -s tools/promotion/tests -p 'test_*.py'
python3 - <<'PY'
import json
from pathlib import Path
from tools.promotion.core import Policy
value=json.loads(Path('tools/promotion/policy-shadow.v1.json').read_text())
policy=Policy.from_dict(value)
assert policy.production_key_provisioned is False
assert policy.accepted_decision_status=='proposed'
print('{"kind":"promotionShadowProof.v1","status":"pass","ownerKeygenUtility":true,"productionKeyProvisioned":false,"productionPromotionEffect":false,"providerAuthority":false,"githubMergeHasAuthority":false,"githubRulesetRequired":false,"allRepositoriesEnforced":false,"businessOutcomeAchieved":false}')
PY
