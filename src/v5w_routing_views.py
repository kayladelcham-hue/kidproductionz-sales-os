import csv,json
from pathlib import Path
def render(doc):
 s=doc['summary']; status=s.get('overall_routing_equivalence_status',s.get('overall_status','EQUIVALENT')); lines=['# Canonical Routing Report v1','',f"Overall: **{status}**",f"Fixtures: {s.get('total_fixtures',s.get('fixture_count',0))}",'', '## Route Summary','']
 for k,v in s['route_counts'].items(): lines.append(f'- {k}: {v}')
 lines += ['', '| Fixture | Campaign | Score | Grade | Route | Reason | Equivalent |','|---|---|---:|---|---|---|---|']
 rows=[]
 for f in doc['fixtures']:
  score=f.get('scoring_summary',{}).get('score','');grade=f.get('scoring_summary',{}).get('grade','');route=f.get('route','');reason=f.get('route_reason','');eq='YES' if f.get('equivalent') else 'NO';lines.append(f"| {f['fixture_id']} | {f['campaign_id']} | {score} | {grade} | {route} | {reason.replace('|','/')} | {eq} |");rows.append({'fixture_id':f['fixture_id'],'campaign_id':f['campaign_id'],'score':score,'grade':grade,'route':route,'route_reason':reason,'equivalent':eq})
 return '\n'.join(lines)+'\n',rows
def write(source,outdir):
 doc=json.loads(Path(source).read_text(encoding='utf-8'));md,rows=render(doc);out=Path(outdir);out.mkdir(parents=True,exist_ok=True);mp=out/'canonical_routing_v1.md';cp=out/'canonical_routing_v1.csv'
 if mp.exists() and mp.read_text(encoding='utf-8')!=md: raise ValueError('EXISTING_ARTIFACT_DIFFERS')
 if not mp.exists(): mp.write_text(md,encoding='utf-8')
 if not cp.exists():
  with cp.open('w',newline='',encoding='utf-8-sig') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 return mp,cp,len(rows)
