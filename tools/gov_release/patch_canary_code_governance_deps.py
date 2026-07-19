from pathlib import Path

root=Path(__file__).resolve().parents[2]
canary=root/'.github/workflows/gov-canary.yml'
production=root/'tools/check-package-final-ci-production.py'

def replace_once(path,old,new):
    text=path.read_text()
    if text.count(old)!=1: raise SystemExit(f'replace-count:{path}:{text.count(old)}')
    path.write_text(text.replace(old,new,1))

replace_once(
    canary,
    '''      - name: Install CUE
        run: |
          go install cuelang.org/go/cmd/cue@v0.9.2
          echo "$HOME/go/bin" >> "$GITHUB_PATH"
      - name: Run live ADRS observation and exact gov release proof
''',
    '''      - name: Install pinned ADRS observer dependencies and CUE
        run: |
          python3 -m pip install --disable-pip-version-check -r tools/code-governance/requirements.txt
          go install cuelang.org/go/cmd/cue@v0.9.2
          echo "$HOME/go/bin" >> "$GITHUB_PATH"
      - name: Run live ADRS observation and exact gov release proof
''',
)
replace_once(
    production,
    '''    need("check-live-final-ci-control-plane.py check" in canary_text, "canary-control-plane")
    need("workflow_dispatch" in release_text, "release-dispatch")
''',
    '''    need("check-live-final-ci-control-plane.py check" in canary_text, "canary-control-plane")
    need("tools/code-governance/requirements.txt" in canary_text, "canary-code-governance-dependencies")
    need("workflow_dispatch" in release_text, "release-dispatch")
''',
)
for temporary in [root/'.github/workflows/tmp-apply-canary-code-governance-deps.yml',Path(__file__)]:
    if temporary.exists(): temporary.unlink()
