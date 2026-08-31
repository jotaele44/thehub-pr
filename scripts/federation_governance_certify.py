#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, re, sys
from pathlib import Path

EXPECTED={'thehub-pr','moneysweep-pr','spiderweb-pr','aguayluz-pr','ovnis-pr','skywatcher-pr','centinelas-pr'}
ALLOWED={'UNAFFECTED','COMPATIBLE','UPDATED'}

def load(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    errors=[]
    base=load('governance/federation_baseline.json')
    if set(base.get('repos',{})) != EXPECTED: errors.append('baseline membership != 7 canonical repos')
    for repo,v in base.get('repos',{}).items():
        if not re.fullmatch(r'[0-9a-f]{40}',v.get('sha','')): errors.append(f'{repo}: invalid frozen SHA')
    fp=load('governance/contract_fingerprints.json')
    paths=[]
    for c in fp.get('contracts',[]):
        p=Path(c['path']);
        if not p.exists(): errors.append(f'missing governed contract: {p}')
        else: paths.append(str(p))
        if not re.fullmatch(r'\d+\.\d+\.\d+',c.get('version','')): errors.append(f"{c.get('id')}: invalid SemVer")
    # Documentation membership gate.
    arch=Path('ARCHITECTURE.md').read_text()
    for repo in EXPECTED-{'thehub-pr'}:
        if repo not in arch: errors.append(f'ARCHITECTURE.md missing {repo}')
    # Presence of core governance artifacts.
    for p in ['governance/dependency_graph.json','governance/compatibility_matrix.json','scripts/federation_contract_guard.py']:
        if not Path(p).exists(): errors.append(f'missing governance artifact: {p}')
    result={'status':'PASS' if not errors else 'FAIL','errors':errors,'fingerprints':{p:sha(p) for p in paths}}
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0 if not errors else 1
if __name__=='__main__': raise SystemExit(main())
