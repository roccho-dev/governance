from pathlib import Path

root=Path(__file__).resolve().parents[2]
path=root/'.github/workflows/gov-release.yml'
text=path.read_text()
old="""          python3 accepted-adrs/tools/check-gov-release-v1.py contract --out gov-release-contract-validation.json
          python3 accepted-adrs/tools/check-gov-release-v1.py decision --out accepted-decision-validation.json
          python3 accepted-adrs/tools/check-gov-release-v1.py selftest --out accepted-decision-selftest.json
          bash accepted-adrs/ci/check-gov-release-v1-static.sh
"""
new="""          (
            cd accepted-adrs
            python3 tools/check-gov-release-v1.py contract --out ../gov-release-contract-validation.json
            python3 tools/check-gov-release-v1.py decision --out ../accepted-decision-validation.json
            python3 tools/check-gov-release-v1.py selftest --out ../accepted-decision-selftest.json
            bash ci/check-gov-release-v1-static.sh
          )
"""
if text.count(old)!=1: raise SystemExit('capture-block-count')
path.write_text(text.replace(old,new,1))
for temporary in [root/'.github/workflows/tmp-apply-issue-171-cwd.yml',Path(__file__)]:
    if temporary.exists(): temporary.unlink()
