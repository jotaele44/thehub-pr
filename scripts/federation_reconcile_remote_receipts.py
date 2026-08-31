#!/usr/bin/env python3
from __future__ import annotations
import json, tempfile, urllib.request
from pathlib import Path
from federation_contract_guard import reconcile

def load(p): return json.loads(Path(p).read_text())

def main():
    refs=load('governance/producer_receipt_refs.json')
    matrix=load('governance/compatibility_matrix.json')
    receipts=[]; tmp=[]; errors=[]
    try:
        for repo_id,meta in refs['producers'].items():
            owner_repo=meta['repo']; sha=meta['sha']; path=refs['receipt_path']
            url=f'https://raw.githubusercontent.com/{owner_repo}/{sha}/{path}'
            try:
                with urllib.request.urlopen(url, timeout=20) as r: body=r.read().decode('utf-8')
                data=json.loads(body)
                if data.get('repo') != repo_id: errors.append(f'{repo_id}: remote receipt repo mismatch')
                fd=tempfile.NamedTemporaryFile('w',delete=False,suffix='.json'); fd.write(body); fd.close(); tmp.append(fd.name); receipts.append(fd.name)
            except Exception as exc: errors.append(f'{repo_id}: unable to fetch pinned receipt: {exc}')
        errors.extend(reconcile(matrix,receipts))
        print(json.dumps({'status':'PASS' if not errors else 'FAIL','errors':errors,'receipts_checked':len(receipts)},indent=2))
        return 0 if not errors else 1
    finally:
        for p in tmp:
            try: Path(p).unlink()
            except OSError: pass
if __name__=='__main__': raise SystemExit(main())
