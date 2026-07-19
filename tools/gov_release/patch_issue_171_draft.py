from pathlib import Path

root=Path(__file__).resolve().parents[2]
release=root/'.github/workflows/gov-release.yml'
production=root/'tools/check-package-final-ci-production.py'
roles=root/'tools/check-package-ci-final-role-demotion.py'

def replace_once(path,old,new):
    text=path.read_text()
    if text.count(old)!=1: raise SystemExit(f'replace-count:{path}:{text.count(old)}')
    path.write_text(text.replace(old,new,1))

replace_once(
    release,
    '''          printf 'RELEASE_ID=%s\\nRELEASE_DIGEST=%s\\nRELEASE_TAG=%s\\n' "$release_id" "$release_digest" "$tag" >> "$GITHUB_ENV"
          gh release create "$tag" \\
''',
    '''          printf 'RELEASE_ID=%s\\nRELEASE_DIGEST=%s\\nRELEASE_TAG=%s\\n' "$release_id" "$release_digest" "$tag" >> "$GITHUB_ENV"
          export RELEASE_ID="$release_id" RELEASE_DIGEST="$release_digest" RELEASE_TAG="$tag"
          gh release create "$tag" \\
''',
)
replace_once(
    release,
    '''            release-bundle/gov-engine-descriptor.json \\
            release-bundle/gov-nix-output-descriptor.json             release-bundle/gov-release-owner-authorization-transport.json
''',
    '''            release-bundle/gov-engine-descriptor.json \\
            release-bundle/gov-nix-output-descriptor.json \\
            release-bundle/gov-release-owner-authorization-transport.json
''',
)
replace_once(
    release,
    '''          gh release upload "$tag" --repo "$REPOSITORY" gov-release-readback-receipt.json
      - name: Publish and perform post-publication byte readback
''',
    '''          gh release upload "$tag" --repo "$REPOSITORY" gov-release-readback-receipt.json
      - name: Remove incomplete draft on failure
        if: failure()
        env:
          GH_TOKEN: ${{ github.token }}
          REPOSITORY: ${{ github.repository }}
        run: |
          set -euo pipefail
          if test -n "${RELEASE_TAG:-}" && gh release view "$RELEASE_TAG" --repo "$REPOSITORY" >/dev/null 2>&1; then
            draft=$(gh api "repos/$REPOSITORY/releases/tags/$RELEASE_TAG" --jq .draft)
            if test "$draft" = true; then
              gh release delete "$RELEASE_TAG" --repo "$REPOSITORY" --yes --cleanup-tag
            fi
          fi
      - name: Publish and perform post-publication byte readback
''',
)
replace_once(
    production,
    '''    need("gov-release-owner-authorization-transport.json" in release_text + canary_text, "release-owner-authorization-asset")
    need("contents: write" in release_text, "release-write-boundary")
''',
    '''    need("gov-release-owner-authorization-transport.json" in release_text + canary_text, "release-owner-authorization-asset")
    need("export RELEASE_ID=\"$release_id\" RELEASE_DIGEST=\"$release_digest\" RELEASE_TAG=\"$tag\"" in release_text, "release-same-step-environment")
    need("Remove incomplete draft on failure" in release_text and "gh release delete" in release_text, "release-draft-cleanup")
    need("contents: write" in release_text, "release-write-boundary")
''',
)
replace_once(
    roles,
    '''    if "owner_authorization.py" not in release_text or "gov-release-owner-authorization-transport.json" not in release_text:
        findings.append({"code": "release-owner-authorization-validator"})
''',
    '''    if "owner_authorization.py" not in release_text or "gov-release-owner-authorization-transport.json" not in release_text:
        findings.append({"code": "release-owner-authorization-validator"})
    if 'export RELEASE_ID="$release_id" RELEASE_DIGEST="$release_digest" RELEASE_TAG="$tag"' not in release_text:
        findings.append({"code": "release-same-step-environment"})
    if "Remove incomplete draft on failure" not in release_text or "gh release delete" not in release_text:
        findings.append({"code": "release-draft-cleanup"})
''',
)
for temporary in [root/'.github/workflows/tmp-apply-issue-171-draft.yml',Path(__file__)]:
    if temporary.exists(): temporary.unlink()
