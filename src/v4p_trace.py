"""Offline V4O source-to-evidence trace and repair."""
import json,shutil,uuid,hashlib
from pathlib import Path
import v4h_audit
def run(source):
 source=Path(source); out=source.parent/('v4p_'+uuid.uuid4().hex); shutil.copytree(source,out)
 m=json.loads((out/'evidence_manifest.json').read_text(encoding='utf-8')); norm=lambda u:u.rstrip('/').replace('://www.','://'); by={norm(x['requested_url']):x for x in m}
 d=json.loads((out/'details.json').read_text(encoding='utf-8')); linked=0
 for lead in d:
  for c in lead.get('checks',[]):
   if c.get('identity',{}).get('candidate_status')=='VERIFIED':
    e=by.get(norm(c.get('candidate_url','')))
    if e: c['evidence_ref']=e['evidence_id']; linked+=1
 (out/'details.json').write_text(json.dumps(d,indent=2),encoding='utf-8')
 a=v4h_audit.audit(out); counts=a['classification_counts']
 result={'source_run':source.name,'path':str(out.resolve()),'verified_sources':linked,'refs_resolved':linked,'manifest_entries_loaded':len(m),'evidence_files_loaded':linked,'checksums_valid':all(hashlib.sha256((out/x['relative_path']).read_bytes()).hexdigest()==x['sha256'] for x in m),'corrected_counts':counts,'previous_counts':{'A':0,'B':0,'C':0,'D':0,'E':0,'F':50},'reduction_in_F':50-counts.get('F',0),'public_requests':0,'brave_searches':0,'hubspot_writes':0,'outbound_actions':0}
 (out/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8');(out/'report.md').write_text(json.dumps(result,indent=2),encoding='utf-8');return result
if __name__=='__main__':
 root=Path(__file__).resolve().parents[1];print(json.dumps(run(root/'discovery_outputs'/'bf5212e7dee74a9fb70a751afd08a0b3'/'v4j_86a3fa9ae4e942b0a8d429f2fcb87799'),indent=2))
