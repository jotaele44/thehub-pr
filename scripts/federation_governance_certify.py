#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, re
from pathlib import Path

EXPECTED={'thehub-pr','moneysweep-pr','spiderweb-pr','aguayluz-pr','ovnis-pr','skywatcher-pr','centinelas-pr'}

def load(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def frozen_manifest():
    out={}
    for line in Path('schemas/FROZEN.sha256').read_text().splitlines():
        line=line.strip()
        if not line or line.startswith('#'): continue
        digest,name=line.split(None,1); out[name.strip()]=digest
    return out

def main():
    errors=[]
    base=load('governance/federation_baseline.json')
    if set(base.get('repos',{})) != EXPECTED: errors.append('baseline membership != 7 canonical repos')
    for repo,v in base.get('repos',{}).items():
        if not re.fullmatch(r'[0-9a-f]{40}',v.get('sha','')): errors.append(f'{repo}: invalid frozen SHA')

    frozen=frozen_manifest(); fp=load('governance/contract_fingerprints.json'); observed={}
    for c in fp.get('contracts',[]):
        p=Path(c['path']); rel=str(p.relative_to('schemas')) if str(p).startswith('schemas/') else str(p)
        if not p.exists(): errors.append(f'missing governed contract: {p}'); continue
        actual=sha(p); observed[str(p)]=actual
        if actual != c.get('sha256'): errors.append(f'{c.get("id")}: current bytes != pinned sha256')
        if frozen.get(rel) != c.get('sha256'): errors.append(f'{c.get("id")}: FROZEN.sha256 != governance fingerprint')
        if not re.fullmatch(r'\d+\.\d+\.\d+',c.get('version','')): errors.append(f'{c.get("id")}: invalid SemVer')

    arch=Path('ARCHITECTURE.md').read_text()
    for repo in EXPECTED-{'thehub-pr'}:
        if repo not in arch: errors.append(f'ARCHITECTURE.md missing {repo}')

    for p in ['governance/federation_dependencies.yaml','governance/compatibility_matrix.json','governance/contract_versions.json','scripts/federation_contract_guard.py','governance/merge_blocking_status.json']:
        if not Path(p).exists(): errors.append(f'missing governance artifact: {p}')

    result={'status':'PASS' if not errors else 'FAIL','errors':errors,'fingerprints':observed}
    print(json.dumps(result,indent=2,sort_keys=True)); return 0 if not errors else 1
if __name__=='__main__': raise SystemExit(main())
