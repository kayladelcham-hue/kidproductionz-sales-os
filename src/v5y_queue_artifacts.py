import csv,json
from pathlib import Path
def write(queue,outdir):
 out=Path(outdir);out.mkdir(parents=True,exist_ok=True); sections={k:[] for k in ('daily_queue','deferred','research','ineligible')}
 for c in queue['candidates']: sections[{'DAILY_QUEUE':'daily_queue','DEFERRED':'deferred','RESEARCH':'research','INELIGIBLE':'ineligible'}[c['queue_status']]].append(c)
 assert sum(map(len,sections.values()))==len(queue['candidates'])
 doc={'artifact_version':'1.0','campaign_id':queue['campaign_id'],'queue_limit':queue['queue_limit'],'summary':queue['summary'],'route_summary':{},'priority_summary':{},'safety':queue['safety'],**sections}
 for c in queue['candidates']:
  doc['route_summary'][c.get('route','')]=doc['route_summary'].get(c.get('route',''),0)+1;doc['priority_summary'][c.get('priority','')]=doc['priority_summary'].get(c.get('priority',''),0)+1
 text=json.dumps(doc,indent=2,sort_keys=True)+'\n'; version=1
 while (out/f'daily_queue_v{version}.json').exists() and (out/f'daily_queue_v{version}.json').read_text(encoding='utf-8')!=text: version+=1
 jp=out/f'daily_queue_v{version}.json'
 if not jp.exists():jp.write_text(text,encoding='utf-8')
 cp=out/f'daily_queue_v{version}.csv'; fields=['queue_status','queue_position','fixture_id','lead_id','campaign_id','score','grade','route','route_reason','priority','phone','email','social','website']
 if not cp.exists():
  with cp.open('w',newline='',encoding='utf-8-sig') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows({k:c.get(k,'') for k in fields} for c in queue['candidates'])
 mp=out/f'daily_queue_v{version}.md'; lines=['# Daily Queue','',f"Campaign: {queue['campaign_id']}",f"Queue Limit: {queue['queue_limit']}",'']
 for sec,title in [('daily_queue','Today'),('deferred','Deferred'),('research','Research'),('ineligible','Ineligible')]:
  lines += [f'## {title}','','| ID | Score | Route | Priority | Status |','|---|---:|---|---|---|']+[f"| {c.get('fixture_id',c.get('lead_id',''))} | {c.get('score','')} | {c.get('route','')} | {c.get('priority','')} | {c.get('queue_status','')} |" for c in doc[sec]]+['']
 if not mp.exists():mp.write_text('\n'.join(lines),encoding='utf-8')
 return jp,cp,mp
