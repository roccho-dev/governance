#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('.')
text = ''
for path in sorted((root / 'adr' / 'src').glob('*.cue')):
    text += path.read_text(encoding='utf-8') + '\n'
required = [
    'infra://package/external-nix-build-contract',
    'externalNixPackageBuildContract.v1',
    'requiredPackageFacts',
    'requiredChecks',
    'duckdb',
    'grafeo',
    'jsonl-import',
]
missing = [item for item in required if item not in text]
if missing:
    raise SystemExit('missing contract tokens: ' + ', '.join(missing))
print('external-package-build-contract: PASS')
