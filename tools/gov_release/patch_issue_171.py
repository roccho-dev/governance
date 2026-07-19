from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"replace-count:{path}:{count}:{old[:80]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


release = ROOT / ".github/workflows/gov-release.yml"
canary = ROOT / ".github/workflows/gov-canary.yml"
production = ROOT / "tools/check-package-final-ci-production.py"
roles = ROOT / "tools/check-package-ci-final-role-demotion.py"

replace_once(
    release,
    """      supersedes_release_digest:
        description: Earlier canonical release digest to supersede, or null
        required: true
        default: null
        type: string

permissions:
  contents: read
""",
    """      supersedes_release_digest:
        description: Earlier canonical release digest to supersede, or null
        required: true
        default: null
        type: string
      owner_authorization_comment_id:
        description: Exact owner authorization comment ID for bot-transported dispatch, empty for direct owner dispatch
        required: false
        default: ''
        type: string

permissions:
  contents: read
  issues: read
""",
)

replace_once(
    release,
    """      - name: Require owner-controlled dispatch on proposals
        env:
          ACTOR: ${{ github.actor }}
          OWNER: ${{ github.repository_owner }}
          REF: ${{ github.ref }}
        run: |
          set -euo pipefail
          test "$ACTOR" = "$OWNER"
          test "$REF" = refs/heads/proposals
      - name: Checkout the selected governance engine
""",
    """      - name: Require proposals release target
        env:
          REF: ${{ github.ref }}
        run: |
          set -euo pipefail
          test "$REF" = refs/heads/proposals
      - name: Checkout the selected governance engine
""",
)

replace_once(
    release,
    """      - name: Validate ADRS reader
        env:
          CLIENT_ID: ${{ vars['ADRS_READER_CLIENT_ID'] }}
""",
    """      - name: Validate exact owner authorization transport
        env:
          GH_TOKEN: ${{ github.token }}
          ACTOR: ${{ github.actor }}
          OWNER: ${{ github.repository_owner }}
          REPOSITORY: ${{ github.repository }}
          COMMENT_ID: ${{ inputs.owner_authorization_comment_id }}
          RELEASE_ID: ${{ inputs.release_id }}
          SEQUENCE: ${{ inputs.sequence }}
          PREVIOUS_RELEASE_DIGEST: ${{ inputs.previous_release_digest }}
          SUPERSEDES_RELEASE_DIGEST: ${{ inputs.supersedes_release_digest }}
          ENGINE_SHA: ${{ github.sha }}
          ACCEPTED_DECISION_DIGEST: ${{ steps.identity.outputs.accepted_decision_digest }}
        run: |
          set -euo pipefail
          common=(
            --owner "$OWNER"
            --actor "$ACTOR"
            --repository "$REPOSITORY"
            --release-id "$RELEASE_ID"
            --sequence "$SEQUENCE"
            --previous-release-digest "$PREVIOUS_RELEASE_DIGEST"
            --supersedes-release-digest "$SUPERSEDES_RELEASE_DIGEST"
            --engine-sha "$ENGINE_SHA"
            --accepted-decision-digest "$ACCEPTED_DECISION_DIGEST"
            --out gov-release-owner-authorization-transport.json
          )
          if test "$ACTOR" = "$OWNER"; then
            test -z "$COMMENT_ID"
            python3 tools/gov_release/owner_authorization.py direct "${common[@]}"
          else
            test "$ACTOR" = github-actions[bot]
            case "$COMMENT_ID" in ''|*[!0-9]*) echo invalid-owner-authorization-comment-id >&2; exit 1 ;; esac
            gh api "repos/$REPOSITORY/issues/comments/$COMMENT_ID" > owner-authorization-comment.json
            python3 tools/gov_release/owner_authorization.py comment "${common[@]}" --comment-json owner-authorization-comment.json
          fi
      - name: Validate ADRS reader
        env:
          CLIENT_ID: ${{ vars['ADRS_READER_CLIENT_ID'] }}
""",
)

replace_once(
    release,
    """            gov-release-identity.v1.json
            gov-release-contract-validation.json
""",
    """            gov-release-identity.v1.json
            gov-release-owner-authorization-transport.json
            gov-release-contract-validation.json
""",
)

replace_once(
    release,
    """          cp evidence/accepted-decision-validation.json accepted-decision-validation.json
      - uses: actions/upload-artifact@v4
""",
    """          cp evidence/accepted-decision-validation.json accepted-decision-validation.json
          cp evidence/gov-release-owner-authorization-transport.json gov-release-owner-authorization-transport.json
      - uses: actions/upload-artifact@v4
""",
)

replace_once(
    release,
    """            gov-release-identity.v1.json
            gov-release-manifest.json
""",
    """            gov-release-identity.v1.json
            gov-release-owner-authorization-transport.json
            gov-release-manifest.json
""",
)

replace_once(
    release,
    """          validation=load('gov-release-manifest-validation.json')
          assert validation['releaseDigest']==manifest_digest and validation['status']=='pass'
          PY
""",
    """          validation=load('gov-release-manifest-validation.json')
          assert validation['releaseDigest']==manifest_digest and validation['status']=='pass'
          authorization=load('gov-release-owner-authorization-transport.json')
          assert authorization['kind']=='govReleaseOwnerAuthorizationTransport.v1'
          assert authorization['status']=='pass' and authorization['ownerAuthorized'] is True
          assert authorization['meaningAuthority'] is False and authorization['adoptionRecord'] is False and authorization['authority'] is False
          command=authorization['command']
          assert command['releaseId']==manifest['releaseId']
          assert command['sequence']==manifest['sequence']
          assert command['previousReleaseDigest']==manifest['previousReleaseDigest']
          assert command['supersedesReleaseDigest']==manifest['supersedesReleaseDigest']
          assert command['engineSha']==engine['commitSha']
          assert command['acceptedDecisionDigest']==manifest['acceptedDecisionDigest']
          assert authorization['commandDigest']==digest(command)
          PY
""",
)

replace_once(
    release,
    """              for pattern in ['gov-release-manifest.json','gov-release-readback-receipt.json']:
""",
    """              for pattern in ['gov-release-manifest.json','gov-release-owner-authorization-transport.json','gov-release-readback-receipt.json']:
""",
)

replace_once(
    release,
    """              receipt=json.loads((directory/'gov-release-readback-receipt.json').read_text())
              release_digest=digest(manifest)
""",
    """              authorization=json.loads((directory/'gov-release-owner-authorization-transport.json').read_text())
              receipt=json.loads((directory/'gov-release-readback-receipt.json').read_text())
              release_digest=digest(manifest)
""",
)

replace_once(
    release,
    """              assert receipt['releaseDigest']==release_digest==receipt['observedManifestDigest']
              existing.append(manifest)
""",
    """              assert receipt['releaseDigest']==release_digest==receipt['observedManifestDigest']
              assert authorization['status']=='pass' and authorization['ownerAuthorized'] is True
              assert receipt['transport']['ownerAuthorizationTransportDigest']==digest(authorization)
              assert receipt['transport']['ownerAuthorizationMode']==authorization['mode']
              assert receipt['transport']['ownerAuthorizationCommentId']==authorization['commentId']
              existing.append(manifest)
""",
)

replace_once(
    release,
    """            release-bundle/gov-nix-output-descriptor.json
          mkdir draft-readback
""",
    """            release-bundle/gov-nix-output-descriptor.json \
            release-bundle/gov-release-owner-authorization-transport.json
          mkdir draft-readback
""",
)

replace_once(
    release,
    """          import json,os
          from pathlib import Path
          receipt={
""",
    """          import hashlib,json,os
          from pathlib import Path
          authorization=json.loads(Path('release-bundle/gov-release-owner-authorization-transport.json').read_text())
          canonical=lambda value: json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
          authorization_digest='sha256:'+hashlib.sha256(canonical(authorization)).hexdigest()
          receipt={
""",
)

replace_once(
    release,
    """            'transport':{'provider':'github-release','repository':os.environ['GITHUB_REPOSITORY'],'runId':int(os.environ['GITHUB_RUN_ID']),'actor':os.environ['GITHUB_ACTOR']},
""",
    """            'transport':{'provider':'github-release','repository':os.environ['GITHUB_REPOSITORY'],'runId':int(os.environ['GITHUB_RUN_ID']),'actor':os.environ['GITHUB_ACTOR'],'ownerAuthorizationMode':authorization['mode'],'ownerAuthorizationCommentId':authorization['commentId'],'ownerAuthorizationTransportDigest':authorization_digest},
""",
)

replace_once(
    release,
    """          gh release download "$RELEASE_TAG" --repo "$REPOSITORY" --pattern gov-release-readback-receipt.json --dir published-readback
          cmp release-bundle/gov-release-manifest.json published-readback/gov-release-manifest.json
          cmp gov-release-readback-receipt.json published-readback/gov-release-readback-receipt.json
""",
    """          gh release download "$RELEASE_TAG" --repo "$REPOSITORY" --pattern gov-release-owner-authorization-transport.json --dir published-readback
          gh release download "$RELEASE_TAG" --repo "$REPOSITORY" --pattern gov-release-readback-receipt.json --dir published-readback
          cmp release-bundle/gov-release-manifest.json published-readback/gov-release-manifest.json
          cmp release-bundle/gov-release-owner-authorization-transport.json published-readback/gov-release-owner-authorization-transport.json
          cmp gov-release-readback-receipt.json published-readback/gov-release-readback-receipt.json
""",
)

replace_once(
    release,
    """          manifest=json.loads(Path('published-readback/gov-release-manifest.json').read_text())
          receipt=json.loads(Path('published-readback/gov-release-readback-receipt.json').read_text())
""",
    """          manifest=json.loads(Path('published-readback/gov-release-manifest.json').read_text())
          authorization=json.loads(Path('published-readback/gov-release-owner-authorization-transport.json').read_text())
          receipt=json.loads(Path('published-readback/gov-release-readback-receipt.json').read_text())
""",
)

replace_once(
    release,
    """          assert receipt['status']=='pass' and receipt['adopted'] is True and receipt['authority'] is False
          PY
""",
    """          assert receipt['status']=='pass' and receipt['adopted'] is True and receipt['authority'] is False
          authorization_digest='sha256:'+hashlib.sha256(canonical(authorization)).hexdigest()
          assert receipt['transport']['ownerAuthorizationTransportDigest']==authorization_digest
          assert receipt['transport']['ownerAuthorizationMode']==authorization['mode']
          assert receipt['transport']['ownerAuthorizationCommentId']==authorization['commentId']
          PY
""",
)

replace_once(
    release,
    """            release-bundle/gov-release-identity.v1.json
            gov-release-readback-receipt.json
""",
    """            release-bundle/gov-release-identity.v1.json
            release-bundle/gov-release-owner-authorization-transport.json
            gov-release-readback-receipt.json
""",
)

replace_once(
    canary,
    """              for pattern in ['accepted-decision.json','gov-release-manifest.json','gov-engine-descriptor.json','gov-nix-output-descriptor.json','gov-release-readback-receipt.json']:
""",
    """              for pattern in ['accepted-decision.json','gov-release-manifest.json','gov-engine-descriptor.json','gov-nix-output-descriptor.json','gov-release-owner-authorization-transport.json','gov-release-readback-receipt.json']:
""",
)

replace_once(
    canary,
    """              nix=load(directory/'gov-nix-output-descriptor.json')
              receipt=load(directory/'gov-release-readback-receipt.json')
""",
    """              nix=load(directory/'gov-nix-output-descriptor.json')
              authorization=load(directory/'gov-release-owner-authorization-transport.json')
              receipt=load(directory/'gov-release-readback-receipt.json')
""",
)

replace_once(
    canary,
    """              assert receipt['adopted'] is True and receipt['authority'] is False
              assert manifest['sequence'] not in by_sequence and manifest['releaseId'] not in release_ids
""",
    """              assert receipt['adopted'] is True and receipt['authority'] is False
              assert authorization['kind']=='govReleaseOwnerAuthorizationTransport.v1' and authorization['status']=='pass' and authorization['ownerAuthorized'] is True
              command=authorization['command']
              assert command['releaseId']==manifest['releaseId'] and command['sequence']==manifest['sequence']
              assert command['previousReleaseDigest']==manifest['previousReleaseDigest'] and command['supersedesReleaseDigest']==manifest['supersedesReleaseDigest']
              assert command['engineSha']==engine['commitSha'] and command['acceptedDecisionDigest']==manifest['acceptedDecisionDigest']
              assert receipt['transport']['ownerAuthorizationTransportDigest']==digest(authorization)
              assert receipt['transport']['ownerAuthorizationMode']==authorization['mode']
              assert receipt['transport']['ownerAuthorizationCommentId']==authorization['commentId']
              assert manifest['sequence'] not in by_sequence and manifest['releaseId'] not in release_ids
""",
)

replace_once(
    production,
    """    need("gov-release-identity.v1.json" in gate_text + canary_text + release_text, "identity-projection-workflow")
    need("contents: write" in release_text, "release-write-boundary")
""",
    """    need("gov-release-identity.v1.json" in gate_text + canary_text + release_text, "identity-projection-workflow")
    need("owner_authorization_comment_id" in release_text, "release-owner-authorization-input")
    need("issues: read" in release_text, "release-owner-authorization-read")
    need("owner_authorization.py" in release_text, "release-owner-authorization-validator")
    need("gov-release-owner-authorization-transport.json" in release_text + canary_text, "release-owner-authorization-asset")
    need("contents: write" in release_text, "release-write-boundary")
""",
)

replace_once(
    roles,
    """    if "contents: write" not in release_text:
        findings.append({"code": "release-write-boundary"})
""",
    """    if "contents: write" not in release_text:
        findings.append({"code": "release-write-boundary"})
    if "issues: read" not in release_text or "owner_authorization_comment_id" not in release_text:
        findings.append({"code": "release-owner-authorization-input"})
    if "owner_authorization.py" not in release_text or "gov-release-owner-authorization-transport.json" not in release_text:
        findings.append({"code": "release-owner-authorization-validator"})
""",
)

for temporary in [
    ROOT / ".github/workflows/tmp-apply-issue-171.yml",
    ROOT / "tools/gov_release/patch_issue_171.py",
]:
    if temporary.exists():
        temporary.unlink()
