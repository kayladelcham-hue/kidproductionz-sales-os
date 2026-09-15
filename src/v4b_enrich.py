"""Ten-record public-web enrichment pilot; no CRM or messaging capabilities."""
import argparse,csv,json,uuid
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from enrichment_pipeline import enrich,adapt,FIELDS
from enrichment_sources import PublicProvider
from normalize import url,phone
from enrichment_email import emails
from enrichment_social import socials
ROOT=Path(__file__).resolve().parents[1]

def run(source,cfg,provider,output,limit=10):
    if not 1<=limit<=min(10,cfg['max_records']):raise ValueError('Pilot supports at most ten records')
    with source.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f);fields=reader.fieldnames or [];rows=[r for r in reader if r.get('queue')=='qualified'][:limit]
    if set(fields)&set(FIELDS):raise ValueError('Use original, unenriched input')
    ids=[r.get('lead_id') for r in rows]
    if any(not i for i in ids) or len(set(ids))!=len(ids):raise ValueError('Missing or duplicate lead IDs')
    at=datetime.now(timezone.utc).isoformat();rid=uuid.uuid4().hex
    enriched=[enrich(r,provider,cfg,rid,at) for r in rows];downstream=[adapt(r) for r in enriched]
    count=Counter(r['enrichment_status'] for r in enriched)
    summary=dict(total_input=len(rows),enriched=count['ENRICHED'],no_new_data=count['NO_NEW_DATA'],review=count['REVIEW'],errors=count['ERROR'],hubspot_writes=0,outbound_communications=0,enrichment_run_id=rid)
    for field in ('email','social','website'):
        usable=lambda value: bool(emails(['mailto:'+value])) if field=='email' else bool(socials([value],cfg)) if field=='social' else bool(url(value))
        summary['new_'+field+'_count']=sum(bool(r['enriched_'+field]) for r in enriched)
        summary['usable_'+field+'_before']=sum(usable(r.get(field,'')) for r in rows)
        summary['usable_'+field+'_after']=sum(usable(r.get(field,'')) for r in downstream)
    summary.update(new_contact_name_count=0,usable_phone_count=sum(bool(phone(r.get('phone',''))) for r in rows),confidence_counts=dict(Counter(e['confidence'] for r in enriched for e in json.loads(r['enrichment_evidence'] or '[]'))),source_type_counts=dict(Counter(e['source_type'] for r in enriched for e in json.loads(r['enrichment_evidence'] or '[]'))),review_reason_counts=dict(Counter(r['enrichment_reason'] for r in enriched if r['enrichment_status']=='REVIEW')))
    output.mkdir(parents=True,exist_ok=True);stage=output/(rid+'.incomplete');stage.mkdir()
    def write_csv(name,data):
        with (stage/name).open('x',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields+FIELDS);w.writeheader()
            for row in data:w.writerow({k:("'"+v if k in FIELDS and isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')) and not v.startswith("'") else v) for k,v in row.items()})
    write_csv('enriched_qualified_leads.csv',enriched);write_csv('enrichment_review.csv',[r for r in enriched if r['enrichment_status'] in ('REVIEW','ERROR')]);write_csv('v4a_input.csv',downstream)
    (stage/'enriched_qualified_leads.json').write_text(json.dumps(enriched,indent=2))
    (stage/'enrichment_summary.json').write_text(json.dumps(summary,indent=2))
    final=output/rid;stage.rename(final)
    return {'output_directory':str(final.resolve()),**summary}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True);p.add_argument('--limit',type=int,default=10);p.add_argument('--live-read-only',action='store_true');args=p.parse_args()
    if not args.live_read_only:p.error('Explicit --live-read-only required for public website GETs')
    cfg=json.loads((ROOT/'config/enrichment_config.json').read_text())
    print(json.dumps(run(args.input,cfg,PublicProvider(cfg,ROOT/'enrichment_cache'),ROOT/'enrichment_outputs',args.limit),indent=2))
if __name__=='__main__':main()
