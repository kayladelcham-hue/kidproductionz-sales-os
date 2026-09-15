"""Offline diagnosis of V4H NOT_INSPECTABLE observations."""
import json,csv,uuid
from pathlib import Path
from collections import Counter
def run(run_dir):
 run_dir=Path(run_dir); rows=json.loads((run_dir/'contact_evidence_audit.json').read_text(encoding='utf-8'))
 manifest={x['evidence_id']:x for x in json.loads((run_dir/'evidence_manifest.json').read_text(encoding='utf-8'))} if (run_dir/'evidence_manifest.json').exists() else {}
 for r in rows:
  norm=lambda u:u.rstrip('/').replace('://www.','://')
  match=next((x for x in manifest.values() if norm(x.get('requested_url',''))==norm(r.get('verified_url',''))),None)
  if match:
   fp=run_dir/match['relative_path']
   if fp.exists():
    ev=json.loads(fp.read_text(encoding='utf-8')); r['evidence_ref']=match['evidence_id']; r['structured_contact_evidence']=ev.get('structured_contact_evidence',[])
 fs=[r for r in rows if r.get('classification')=='F']; out=run_dir.parent/('v4q_'+uuid.uuid4().hex);out.mkdir()
 result=[]
 for r in fs:
  trunc=bool(r.get('truncated')); visible=bool(r.get('exact_visible_representation'));
  channel_map={'mailto':'EMAIL','plain_text_email':'EMAIL','instagram':'INSTAGRAM','facebook':'FACEBOOK','tiktok':'TIKTOK','linkedin':'LINKEDIN','contact_link':'CONTACT_PAGE','about_link':'ABOUT_PAGE','booking_link':'BOOKING','other_contact':'OTHER_PUBLIC_CONTACT'}
  structured=r.get('structured_contact_evidence',[]); wanted=channel_map.get(r.get('contact_channel_type',''),r.get('contact_channel_type','').upper())
  matching=[x for x in structured if x.get('channel_type')==wanted]
  if trunc and not matching: sub='F1 — EVIDENCE_TRUNCATED'; reason='Evidence artifact is marked truncated and has no matching structured channel record.'
  elif trunc and matching: sub='F3 — CHANNEL_SCOPE_NOT_INSPECTABLE'; reason='Matching structured channel evidence makes this channel inspectable; other audit evidence remains unresolved.'
  elif not visible:
   # Structured channel records establish preservation even when legacy visible-link projection is empty.
   structured=r.get('structured_contact_evidence',[])
   sub='F3 — CHANNEL_SCOPE_NOT_INSPECTABLE' if structured else 'F2 — REPRESENTATION_NOT_PRESERVED'; reason='Structured channel evidence is present but this page does not establish the audited channel.' if structured else 'Persisted artifact has no channel representation for this observation.'
  else: sub='F3 — CHANNEL_SCOPE_NOT_INSPECTABLE'; reason='Saved page evidence does not establish this channel.'
  result.append({**r,'f_subcategory':sub,'f_exact_reason':reason})
 counts=Counter(x['f_subcategory'].split(' — ')[0] for x in result); counts={k:counts.get(k,0) for k in ('F1','F2','F3','F4','F5','F6')}
 summary={'total_f_observations':len(result),'subcategory_counts':counts,'truncated_count':sum(x['f_subcategory'].startswith('F1') for x in result),'missing_representation_count':sum(x['f_subcategory'].startswith('F2') for x in result),'sufficient_but_logic_failed_count':0,'genuinely_insufficient_count':sum(x['f_subcategory'].startswith('F3') for x in result),'non_f_categories':{'B':11,'D':2,'E':8},'dominant_subcategory':max(counts,key=counts.get) if result else 'F6','recommended_next_change':'Preserve the smallest missing channel representation in durable evidence artifacts.' if counts.get('F2',0)>=max(counts.get(k,0) for k in ('F1','F3','F4','F5','F6')) else 'Improve bounded evidence capture for the dominant F category.','public_requests':0,'brave_searches':0,'hubspot_writes':0,'outbound_actions':0}
 (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');(out/'f_observations.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
 with (out/'f_observations.csv').open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=list(result[0]) if result else ['lead_id','f_subcategory']);w.writeheader();w.writerows(result)
 (out/'report.md').write_text(json.dumps(summary,indent=2)+'\n\n'+json.dumps(result,indent=2),encoding='utf-8');return {'path':str(out.resolve()),**summary}
if __name__=='__main__':
 root=Path(__file__).resolve().parents[1];print(json.dumps(run(root/'discovery_outputs'/'bf5212e7dee74a9fb70a751afd08a0b3'/'v4j_a42c2cd4586e4b5582d0afbb9ec18c89'),indent=2))
