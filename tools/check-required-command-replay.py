#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, pathlib, subprocess, sys


def read_jsonl(path: pathlib.Path):
    return [json.loads(l) for l in path.read_text(encoding='utf-8').splitlines() if l.strip()]


def fail(msg: str):
    raise SystemExit(f"required-command-replay:error:{msg}")


def main(argv=None):
    ap=argparse.ArgumentParser(description='Audit requiredCommands exact-root replay surface and non-claim dispositions.')
    ap.add_argument('--root', default='.')
    ap.add_argument('--execute-root-ci', action='store_true', help='execute exact bash ci/*.sh commands that do not require missing external runtime')
    ap.add_argument('--json', action='store_true')
    args=ap.parse_args(argv)
    root=pathlib.Path(args.root).resolve()
    packages=read_jsonl(root/'governance-records-main/records/specs/package-contract.v1.jsonl')
    dispositions=read_jsonl(root/'governance-records-main/records/migration/required-command-replay-disposition.v1.jsonl')
    expected=[]
    stale=[]
    for p in packages:
        for i,cmd in enumerate(p['definition'].get('requiredCommands') or [], 1):
            expected.append((p['packageId'],i,cmd))
            if 'policy-master' in cmd or 'governance-records-main/generated/feat-inputs' in cmd:
                stale.append((p['packageId'],i,cmd))
    if stale:
        fail('stale command surface: '+json.dumps(stale[:10], ensure_ascii=False))
    got={(r['packageId'],r['commandIndex'],r['command']) for r in dispositions}
    missing=[x for x in expected if x not in got]
    if missing:
        fail('missing command disposition rows: '+json.dumps(missing[:10], ensure_ascii=False))
    exact=[r for r in dispositions if r.get('disposition')=='exact-root-replay-command']
    executed=[]
    if args.execute_root_ci:
        seen=set()
        for r in exact:
            if r['command'] in seen:
                continue
            seen.add(r['command'])
            # DuckDB command is exact replay but may return explicit external-tool-missing rc 78.
            proc=subprocess.run(r['command'], shell=True, cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
            ok=(proc.returncode==0) or ('duckdb' in r['command'] and proc.returncode==78)
            if not ok:
                fail(f"exact command failed rc={proc.returncode}: {r['command']}\n{proc.stdout[-2000:]}")
            executed.append({'command':r['command'], 'rc':proc.returncode})
    result={
        'status':'pass',
        'requiredCommandCount':len(expected),
        'dispositionRows':len(dispositions),
        'exactRootReplayCommands':len(exact),
        'executed':executed,
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True) if args.json else 'required-command-replay:'+json.dumps(result, ensure_ascii=False, sort_keys=True))

if __name__ == '__main__':
    main()
