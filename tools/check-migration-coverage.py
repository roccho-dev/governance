#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, pathlib, sys


def read_jsonl(path: pathlib.Path):
    rows=[]
    for i,line in enumerate(path.read_text(encoding='utf-8').splitlines(),1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception as e:
            raise SystemExit(f"JSONL parse failed {path}:{i}: {e}")
    return rows


def fail(msg: str):
    raise SystemExit(f"migration-coverage:error:{msg}")


def main(argv=None):
    ap=argparse.ArgumentParser(description='Check final non-destructive migration coverage closure.')
    ap.add_argument('--root', default='.')
    ap.add_argument('--json', action='store_true')
    args=ap.parse_args(argv)
    root=pathlib.Path(args.root).resolve()
    coverage=read_jsonl(root/'governance-records-main/records/migration/non-destructive-migration-coverage.v1.jsonl')
    unresolved=[r for r in coverage if r.get('status') != 'resolved']
    if unresolved:
        fail('unresolved coverage rows: '+', '.join(f"{r.get('coverageId')}={r.get('status')}" for r in unresolved))
    required=[
        'official-output-disposition.v1.jsonl',
        'required-command-replay-disposition.v1.jsonl',
        'spec-record-family-disposition.v1.jsonl',
        'legacy-issue-disposition.v1.jsonl',
    ]
    missing=[name for name in required if not (root/'governance-records-main/records/migration'/name).is_file()]
    if missing:
        fail('missing successor disposition ledgers: '+', '.join(missing))
    evidence=root/'evidence-archive-main/artifacts/specs-main-evidence-disposition.v1.jsonl'
    if not evidence.is_file():
        fail(f'missing evidence disposition ledger: {evidence}')
    manifest=json.loads((root/'governance-records-main/records/migration/final-state-manifest.v1.json').read_text(encoding='utf-8'))
    if manifest.get('finalState',{}).get('activeSpecsRepoPresent') is not False:
        fail('finalState.activeSpecsRepoPresent must be false')
    if manifest.get('proposalMode',{}).get('activeSpecsRepoPresent') is not False:
        fail('proposalMode must be retired/false in all-up final package')
    # Guard against stale current-authority generated feat artifact references in current migration records.
    current_text='\n'.join((root/'governance-records-main/records/migration'/name).read_text(encoding='utf-8') for name in required if (root/'governance-records-main/records/migration'/name).is_file())
    if 'governance-records-main/generated/feat-inputs' in current_text or 'governance/generated/feat-inputs' in current_text:
        fail('stale generated feat input authority reference found in current migration records')
    result={
        'status':'pass',
        'coverageRows':len(coverage),
        'resolvedRows':len(coverage),
        'openRows':0,
        'partialRows':0,
        'dispositionLedgers':required,
        'evidenceDisposition':str(evidence.relative_to(root)),
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True) if args.json else 'migration-coverage:'+json.dumps(result, ensure_ascii=False, sort_keys=True))

if __name__ == '__main__':
    main()
