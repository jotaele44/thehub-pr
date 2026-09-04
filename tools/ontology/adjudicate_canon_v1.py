#!/usr/bin/env python3
from __future__ import annotations
import argparse, collections, json, re, sys
from pathlib import Path

SEMANTIC_KINDS={"schema_property","schema_definition","schema_title","model_field","python_class","python_dataclass","python_enum","enum_member","record_field","manifest_field","class_attribute","constant","javascript_type"}
LITERAL_RE=re.compile(r"^(?:\d+(?:_\d+)*|v?\d+(?:_\d+)+|[0-9a-f]{8,}|true|false|null|none)$",re.I)
SCALE_DECISIONS={
"cluster_coherence_score":{"decision":"canonical_local_scale","canonical_terms":["spiderweb:ClusterCoherenceScore"],"native_scales":["0..100"],"adapter":"normalized_ratio = native_value / 100","notes":"Direct SpiderWeb schema evidence is 0..100; 0..1 hits are contextual extraction."},
"confidence":{"decision":"value_object_required","canonical_terms":["prii:ConfidenceAssessment"],"native_scales":["0..1","0..100"],"adapter":"0..1 => identity; 0..100 => divide by 100 only for same assessmentTarget and compatible method","notes":"Preserve native value/scale; incompatible targets are not comparable."},
"dest_lon":{"decision":"coordinate_domain","canonical_terms":["prii:Longitude"],"native_scales":["-180..180"],"adapter":"identity decimal degrees","notes":"-90..90 is neighboring latitude context."},
"evidence_tier":{"decision":"false_positive_nonnumeric","canonical_terms":["prii:EvidenceTier"],"native_scales":[],"adapter":None,"notes":"Categorical evidence classification."},
"geometry":{"decision":"false_positive_nonnumeric","canonical_terms":[],"native_scales":[],"adapter":None,"notes":"Structural/spatial content, not scalar."},
"geometry_status":{"decision":"false_positive_nonnumeric","canonical_terms":["skywatcher:GeometryStatus"],"native_scales":[],"adapter":None,"notes":"Categorical status."},
"ilap_score":{"decision":"split_non_equivalent","canonical_terms":["aguayluz:HydroIlapScore","spiderweb:PrDemPrioritizationScore"],"native_scales":["0..5","0..100"],"adapter":None,"notes":"Different targets; MUST NOT normalize to one score."},
"label":{"decision":"false_positive_nonnumeric","canonical_terms":[],"native_scales":[],"adapter":None,"notes":"Generic label not admitted to core."},
"lat":{"decision":"coordinate_domain","canonical_terms":["prii:Latitude"],"native_scales":["-90..90"],"adapter":"identity decimal degrees","notes":"Regional bounds are deployment constraints."},
"latitude":{"decision":"coordinate_domain","canonical_terms":["prii:Latitude"],"native_scales":["-90..90"],"adapter":"identity decimal degrees","notes":"Regional bounds are deployment constraints."},
"lon":{"decision":"coordinate_domain","canonical_terms":["prii:Longitude"],"native_scales":["-180..180"],"adapter":"identity decimal degrees","notes":"Regional bounds are deployment constraints."},
"longitude":{"decision":"coordinate_domain","canonical_terms":["prii:Longitude"],"native_scales":["-180..180"],"adapter":"identity decimal degrees","notes":"Regional bounds are deployment constraints."},
"municipality":{"decision":"false_positive_nonnumeric","canonical_terms":["prii:MunicipalityReference"],"native_scales":[],"adapter":None,"notes":"Geographic reference."},
"observed_at":{"decision":"false_positive_nonnumeric","canonical_terms":["prii:observedAt"],"native_scales":[],"adapter":None,"notes":"Temporal property."},
"origin_lon":{"decision":"coordinate_domain","canonical_terms":["prii:Longitude"],"native_scales":["-180..180"],"adapter":"identity decimal degrees","notes":"-90..90 is neighboring latitude context."},
"properties":{"decision":"false_positive_structural","canonical_terms":[],"native_scales":[],"adapter":None,"notes":"Schema/container keyword."},
"row_index":{"decision":"split_non_equivalent","canonical_terms":["prii:SourceRowIndex","prii:GridRowIndex"],"native_scales":[">=0","0..255"],"adapter":None,"notes":"Source row and grid row are different identity domains."},
"severity":{"decision":"scoped_alert_scale","canonical_terms":["prii:AlertSeverity"],"native_scales":["0..5"],"adapter":"identity only when target=operational_alert_severity","notes":"Other local severity fields are not automatically comparable."},
"source":{"decision":"false_positive_nonnumeric","canonical_terms":["prii:SourceRecord","prii:MonitoredSource","prii:SourceReference"],"native_scales":[],"adapter":None,"notes":"Identity/provenance semantics."},
"timestamp":{"decision":"false_positive_nonnumeric","canonical_terms":["prii:createdAt","prii:extractedAt","prii:observedAt"],"native_scales":[],"adapter":None,"notes":"Temporal property."},
"family:confidence":{"decision":"aggregate_family_resolution","canonical_terms":["prii:ConfidenceAssessment"],"native_scales":["0..1","0..100"],"adapter":"same as confidence","notes":"Analyzer aggregate governed by confidence."}
}
PRIORITY_RULES={
"source":("thehub-pr",["producer repositories"],"split","SourceRecord is provenance; MonitoredSource is producer configuration; SourceReference is a reference."),
"observation":("thehub-pr",["producer repositories"],"split","RawObservation is producer intake; CanonicalObservation is federation-admitted."),
"relationship":("thehub-pr",["producer repositories"],"split","AssertedRelationship is producer assertion; DerivedRelationship/Correlation are Hub derivations."),
"evidence":("thehub-pr",["producer repositories"],"split","EvidenceItem supports records; ValidationEvidence supports gates; Attestation records validation/governance assertions."),
"alert":("thehub-pr",["producer repositories"],"scoped_split","AlertEvent, CanonicalAlertRecord and UI projection remain distinct."),
"confidence":("thehub-pr",["all producers"],"replace_bare_number","Cross-repo confidence requires ConfidenceAssessment with value, scale, target, method and assessor."),
"status":("thehub-pr",["all producers"],"prohibit_universal_enum","Status stays within an owned state machine."),
"public_matter":("centinelas-pr",["moneysweep-pr","thehub-pr"],"shared_lifecycle_object","Centinelas owns pre-officialization; MoneySweep owns officialized/execution stages; Hub resolves identity.")
}
def norm(s):
    s=re.sub(r"(?<=[a-z0-9])(?=[A-Z])"," ",s.strip()).replace("::"," ").replace("."," ").replace("-","_")
    return re.sub(r"[^a-z0-9]+","_",s.lower()).strip("_")
def toks(s): return [t for t in norm(s).split("_") if t]
def dateish(s):
    n=norm(s); return bool(re.fullmatch(r"(?:\d{1,4}_){1,3}\d{1,4}",n) or re.fullmatch(r"\d+",n))
def dims(obs):
    return {"owners":sorted({o.get("owner") for o in obs if o.get("owner")}),"artifact_kinds":sorted({o.get("artifact_kind") for o in obs if o.get("artifact_kind")}),"term_kinds":sorted({o.get("term_kind") for o in obs if o.get("term_kind")}),"data_types":sorted({str(o.get("data_type")) for o in obs if o.get("data_type") is not None}),"cardinalities":sorted({str(o.get("cardinality")) for o in obs if o.get("cardinality") is not None}),"scales":sorted({str(o.get("scale")) for o in obs if o.get("scale") is not None}),"lifecycle_signatures":sorted([list(x) for x in {tuple(o.get("lifecycle_values") or []) for o in obs if o.get("lifecycle_values")}])}
def dump_jsonl(path,items): path.write_text("\n".join(json.dumps(x,sort_keys=True,separators=(",",":")) for x in items)+"\n",encoding="utf-8")
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--reports",type=Path,required=True); ap.add_argument("--out",type=Path,required=True); args=ap.parse_args(); args.out.mkdir(parents=True,exist_ok=True)
    hom=json.loads((args.reports/"homonym-conflicts.json").read_text()); syn=json.loads((args.reports/"synonym-candidates.json").read_text()); auth=json.loads((args.reports/"authority-conflicts.json").read_text()); scale=json.loads((args.reports/"scale-conflicts.json").read_text()); ledger=args.reports/"raw-term-ledger.jsonl"
    ho=[]
    for g in hom:
      d=dims(g["observations"]); label=g["normalized_label"]; owners=d["owners"]; has_sem=bool(set(d["term_kinds"]) & SEMANTIC_KINDS)
      if g.get("priority_family"): cls,action,conf="true_cross_repo_conflict","apply_priority_family_resolution",1.0
      elif LITERAL_RE.match(label) or len(label)<=1: cls,action,conf="implementation_literal_reuse","exclude_from_canon",0.99
      elif len(owners)==1 and g.get("semantic_signature_count",1)==1: cls,action,conf="expected_local_reuse","retain_owner_scoped",0.98
      elif len(owners)==1 and has_sem: cls,action,conf="true_local_semantic_conflict","split_or_qualify_within_owner_namespace",0.90
      elif len(owners)>1 and has_sem: cls,action,conf="expected_bounded_context_reuse","retain_repo_scoped_unless_explicit_contract_mapping_exists",0.88
      else: cls,action,conf="implementation_only_reuse","exclude_from_federation_core",0.96
      ho.append({"normalized_label":label,"classification":cls,"canon_action":action,"confidence":conf,"severity":g.get("severity"),"priority_family":g.get("priority_family"),"semantic_signature_count":g.get("semantic_signature_count"),"dimensions":d,"observation_count":len(g["observations"]),"representative_evidence":[{k:o.get(k) for k in ("observation_id","repository","path","line","term_kind","artifact_kind","owner","data_type","cardinality","scale")} for o in g["observations"][:5]]})
    dump_jsonl(args.out/"homonym-adjudications.jsonl",ho)
    sy=[]
    for c in syn:
      l,r=c["left"],c["right"]; nl,nr=norm(l),norm(r); lt,rt=set(toks(l)),set(toks(r)); lo=set(c.get("owners",{}).get("left",[])); ro=set(c.get("owners",{}).get("right",[])); overlap=bool(lo&ro); sim=c.get("similarity",{}); seq=float(sim.get("sequence",0)); jac=float(sim.get("token_jaccard",0)); direction=None
      if nl==nr: m,rat,conf="exact_match","same normalized lexical identity; canonical merge still requires owner approval",0.98
      elif dateish(l) or dateish(r): m,rat,conf="non_equivalent","date/numeric-like implementation labels are not semantic synonyms",0.99
      elif sim.get("singular_match") and overlap: m,rat,conf="close_match","singular/plural lexical variant within a shared owner",0.94
      elif overlap and lt and rt and (lt<rt or rt<lt):
        m,rat,conf="broad_match","owner-overlapping token containment indicates broader/narrower phrasing",0.86; direction={"broader":l,"narrower":r} if len(lt)<len(rt) else {"broader":r,"narrower":l}
      elif overlap and seq>=.90: m,rat,conf="close_match","high lexical similarity with shared owner but not identity",0.85
      elif jac>=.75: m,rat,conf="related_match","strong token overlap without sufficient identity evidence",0.78
      elif overlap and seq>=.75: m,rat,conf="related_match","moderate lexical similarity within shared owner",0.72
      else: m,rat,conf="non_equivalent","insufficient semantic evidence; conservative no-merge disposition",0.90
      sy.append({"left":l,"right":r,"mapping":m,"direction":direction,"confidence":conf,"owners":c.get("owners",{}),"similarity":sim,"rationale":rat,"automatic_merge":False})
    dump_jsonl(args.out/"synonym-mappings.jsonl",sy)
    au=[]
    for g in auth:
      pf=g.get("priority_family")
      if pf in PRIORITY_RULES: owner,co,action,definition=PRIORITY_RULES[pf]; decision="priority_rule_applies"
      else: owner=None; action="do_not_promote_generic_label; retain repository authority unless explicit contract mapping is approved"; decision="bounded_context_owner_scoped"
      au.append({"normalized_label":g["normalized_label"],"decision":decision,"canonical_owner":owner,"canon_action":action,"owners":g.get("owners",[]),"priority_family":pf,"severity":g.get("severity"),"observation_count":len(g.get("observations",[])),"representative_observation_ids":[o["observation_id"] for o in g.get("observations",[])[:5]]})
    dump_jsonl(args.out/"authority-adjudications.jsonl",au)
    sc=[]
    for g in scale:
      d=SCALE_DECISIONS[g["normalized_label"]]; seen=set(); reps=[]
      for o in g["observations"]:
        if o.get("scale") not in seen: seen.add(o.get("scale")); reps.append({k:o.get(k) for k in ("observation_id","repository","path","line","term_kind","scale","owner")})
      sc.append({"normalized_label":g["normalized_label"],"observation_count":len(g["observations"]),**d,"representative_evidence":reps[:8]})
    (args.out/"scale-adjudications.json").write_text(json.dumps(sc,indent=2,sort_keys=True)+"\n")
    evidence=collections.defaultdict(list)
    with ledger.open() as f:
      for line in f:
        r=json.loads(line); lab=r.get("normalized_label",""); fam=None
        for p in PRIORITY_RULES:
          if lab==p or lab.startswith(p+"_") or lab.endswith("_"+p) or (p=="public_matter" and "public_matter" in lab): fam=p; break
        if fam and len(evidence[fam])<60: evidence[fam].append(r)
    pr=[]
    for fam,(owner,co,action,definition) in PRIORITY_RULES.items():
      reps=[]; seen=set()
      for r in evidence[fam]:
        if r["program_id"] not in seen or len(reps)<4: reps.append({k:r.get(k) for k in ("observation_id","repository","commit","path","line","term","term_kind","artifact_kind","owner","context_hash")}); seen.add(r["program_id"])
        if len(reps)>=10: break
      pr.append({"family":fam,"semantic_owner":owner,"co_owners":co,"decision":action,"definition":definition,"severity":"high","status":"approved","representative_evidence":reps})
    (args.out/"priority-authority-resolutions.json").write_text(json.dumps(pr,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"homonym":len(ho),"synonym":len(sy),"authority":len(au),"scale":len(sc),"priority":len(pr)},sort_keys=True)); return 0
if __name__=="__main__": sys.exit(main())
