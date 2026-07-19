from pathlib import Path

root=Path(__file__).resolve().parents[2]
path=root/'.github/workflows/gov-release.yml'
text=path.read_text()
old='          out_path=$(nix build --no-link --print-out-paths .#gov-package-output)\n'
new='''          out_path=$(nix build --no-link --print-out-paths \\
            --override-input adrsRecords "path:$PWD/evidence/accepted-adrs" \\
            --override-input uiLib "github:roccho-dev/ui/362f72d2a5be33dd8fcd96d6e1db1cfbe51d4579" \\
            .#gov-package-output)\n'''
if text.count(old)!=1: raise SystemExit('nix-build-count')
path.write_text(text.replace(old,new,1))
for temporary in [root/'.github/workflows/tmp-apply-issue-171-nix.yml',Path(__file__)]:
    if temporary.exists(): temporary.unlink()
