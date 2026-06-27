#!/usr/bin/env python3
import argparse, json, sys
from pathlib import Path

def load(path):
    return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines() if x.strip()]

def good(row):
    purpose=row.get('purpose')
    reality=row.get('reality')
    if not isinstance(purpose,dict): return 'missing-purpose'
    if not isinstance(reality,dict): return 'missing-reality'
    if not purpose.get('selectedObjectiveId'): return 'missing-selected-objective'
    if not purpose.get('intentRefs'): return 'missing-intent-ref'
    if not reality.get('realityRefs'): return 'missing-reality-ref'
    return None

def main():
    p=argparse.ArgumentParser(); p.add_argument('--fixtures',type=Path,required=True); a=p.parse_args()
    findings=[]
    rows=load(a.fixtures)
    for row in rows:
        code=good(row)
        expected=row.get('expectedDiagnostic')
        if row.get('expected')=='pass' and code: findings.append({'case':row.get('case'),'diagnostic':code})
        if expected and expected != code: findings.append({'case':row.get('case'),'expected':expected,'actual':code})
    report={'kind':'governance.intentRealityProjectionGate.report.v1','status':'fail' if findings else 'pass','caseCount':len(rows),'findings':findings}
    print(json.dumps(report,sort_keys=True,separators=(',',':')))
    return 1 if findings else 0
if __name__=='__main__': sys.exit(main())
