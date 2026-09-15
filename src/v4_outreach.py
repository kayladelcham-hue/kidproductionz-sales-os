"""Local CSV outreach decision support. No external reads or writes."""
import argparse
from collections import Counter
import csv
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import uuid
from outreach_routing import routing, ROUTES
from outreach_priority import priority
from outreach_messaging import messaging, follow_up
from outreach_queue import queue

ROOT=Path(__file__).resolve().parents[1]

def generate(source,cfg,start,output):
    with source.open(encoding='utf-8-sig',newline='') as f: inputs=list(csv.DictReader(f))
    eligible=[r for r in inputs if r.get('queue')=='qualified']
    ids=[r.get('lead_id') for r in eligible]
    if any(not i for i in ids) or len(ids)!=len(set(ids)):
        raise ValueError('Missing or repeated lead IDs: resolve source identity before queue generation')
    routed=[]
    for r in eligible:
        route,reason,channels=routing(r,cfg)
        tier,why=priority(r,route,channels,cfg)
        item=dict(lead_id=r['lead_id'],company_name=r.get('name',''),category=r.get('normalized_category') or r.get('category',''),city=r.get('city',''),state=r.get('state',''),lead_score=r.get('score',''),lead_grade=r.get('grade',''),outreach_priority=tier,outreach_route=route,outreach_reason=reason,priority_reason=why,**channels,**messaging(r,route),follow_up_date='' if route=='RESEARCH' else follow_up(start,cfg['follow_up_business_days']),outreach_status='NOT_CONTACTED',source_run_id=r.get('source_run_id') or source.stem.removeprefix('qualified_leads_'),v2_run_id=r.get('v2_run_id',''),source_file=r.get('source_file',''),source_row=r.get('source_row',''),queue_date=start.isoformat())
        routed.append(item)
    selected=queue(routed,cfg)
    summary=dict(total_eligible=len(eligible),total_routed=len(routed),route_counts=dict(Counter(r['outreach_route'] for r in routed)),priority_counts=dict(Counter(r['outreach_priority'] for r in routed)),selected=len(selected),remaining=len(routed)-len(selected),channel_availability={k:sum(bool(r[k]) for r in routed) for k in ('phone','email','social','website')},hubspot_writes=0,outbound_communications=0,source=str(source.resolve()),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),config=cfg,queue_date=start.isoformat(),warnings=['Drafts only. Follow-up assumes initial outreach on queue date; recalculate after actual contact. Business days exclude weekends, not holidays.','This local queue does not know prior outreach, opt-outs, or subsequent CRM changes; review before contact.'])
    for route in ROUTES: summary['route_counts'].setdefault(route,0)
    for tier in ('P1','P2','P3','RESEARCH'): summary['priority_counts'].setdefault(tier,0)
    output.mkdir(parents=True,exist_ok=True)
    run=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'_'+uuid.uuid4().hex[:8]
    stage=output/(run+'.incomplete'); stage.mkdir()
    for name,value in [('daily_outreach_queue.json',selected),('all_routed_prospects.json',routed),('outreach_summary.json',summary)]:
        with (stage/name).open('x',encoding='utf-8') as f: json.dump(value,f,indent=2)
    with (stage/'daily_outreach_queue.csv').open('x',encoding='utf-8-sig',newline='') as f:
        fields=list(routed[0]) if routed else ['lead_id','outreach_route','outreach_status']
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for r in selected:
            writer.writerow({k:("'"+v if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')) else v) for k,v in r.items()})
    final=output/run; stage.rename(final)
    return {'output_directory':str(final.resolve()),**summary}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--as-of',type=date.fromisoformat,required=True,help='Planned initial outreach date YYYY-MM-DD')
    p.add_argument('--config',type=Path,default=ROOT/'config/outreach_config.json')
    p.add_argument('--output',type=Path,default=ROOT/'outreach_outputs')
    args=p.parse_args()
    cfg=json.loads(args.config.read_text(encoding='utf-8-sig'))
    print(json.dumps(generate(args.input,cfg,args.as_of,args.output),indent=2))
if __name__=='__main__':main()
