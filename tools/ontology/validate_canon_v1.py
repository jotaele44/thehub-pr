#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path
V1=Path("federation/ontology/v1")
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--root",type=Path,default=Path(".")); ap.add_argument("--require-approvals",action="store_true"); ap.add_argument("--generated",type=Path); a=ap.parse_args(); root=a.root; v1=root/V1; errors=[]
    ver=json.loads((v1/"VERSION.json").read_text())
    if ver.get("ontology_version")!="1.0.0": errors.append("version")
    man=json.loads((v1/"adjudications/MANIFEST.json").read_text())
    if man.get("baseline_counts")!={"scale":21,"authority":3717,"homonym":8777,"synonym":9338}: errors.append("baseline_count_drift")
    if man.get("automatic_synonym_merges")!=0: errors.append("automatic_merge")
    if man.get("high_severity_unowned")!=0: errors.append("unowned_high_severity")
    terms=json.loads((v1/"terms/TERM_RECORDS.json").read_text())
    if terms.get("records")!=60 or len(terms.get("sha256",""))!=64: errors.append("term_records_manifest")
    if a.generated:
      expected=json.loads((v1/"adjudications/GENERATED_OUTPUTS.json").read_text())["outputs"]
      for name,meta in expected.items():
        p=a.generated/name
        if not p.exists(): errors.append(f"missing_generated:{name}"); continue
        if hashlib.sha256(p.read_bytes()).hexdigest()!=meta["sha256"]: errors.append(f"generated_digest:{name}")
        count=sum(1 for _ in p.open()) if name.endswith(".jsonl") else len(json.loads(p.read_text()))
        if count!=meta["records"]: errors.append(f"generated_count:{name}:{count}")
    if a.require_approvals:
      approvals=json.loads((v1/"APPROVALS.json").read_text()); req=set(approvals["required"]); approved={x["repository"] for x in approvals.get("approvals",[]) if x.get("decision")=="approved"}
      if approved!=req: errors.append(f"approval_gap:{sorted(req-approved)}")
    print(json.dumps({"ok":not errors,"errors":errors},indent=2)); return 0 if not errors else 2
if __name__=="__main__": sys.exit(main())
