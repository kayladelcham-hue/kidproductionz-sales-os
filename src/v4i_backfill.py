"""Existing cohort artifacts only. Zero network dependencies/calls."""
import json,uuid,hashlib
from pathlib import Path
from collections import Counter
from v4i_evidence import capture
ROOT=Path(__file__).resolve().parents[1]
def main():
    cohort=ROOT/'discovery_outputs/bf5212e7dee74a9fb70a751afd08a0b3'
    g=cohort/'v4g_0710b5ed12164a48806d347d1f00824a'
    h=cohort/'v4h_f093064bef2744ebb2317f8ccf538b35'
    observations=json.loads((h/'contact_evidence_audit.json').read_text());old=json.loads((h/'summary.json').read_text())
    details=json.loads((g/'details.json').read_text());run=uuid.uuid4().hex;out=cohort/('v4i_'+run);out.mkdir()
    caches={}
    for p in (ROOT/'discovery_cache/public').glob('*.json'):
        d=json.loads(p.read_text())
        if isinstance(d.get('html'),str):caches[d.get('url')]=(p,d)
    inventory=[];new=json.loads(json.dumps(observations));email_count=0
    for source in dict.fromkeys(r['verified_url'] for r in observations):
        row=next(r for r in observations if r['verified_url']==source);found=caches.get(source) or caches.get(row['final_url'])
        if not found:
            inventory.append({'source':source,'status':'UNABLE_TO_BACKFILL','reason':'No saved fetched HTML body; selected link evidence is insufficient'});continue
        p,d=found;raw=d['html'].encode('utf-8')
        if len(raw)>500000:
            inventory.append({'source':source,'status':'UNABLE_TO_BACKFILL','reason':'Cached representation exceeds evidence input bound'});continue
        e=next(o['v4b_result'] for lead in details for o in lead['outcomes'] if o['candidate_url']==source)
        path,evidence=capture(out/'pages',row['lead_id'],source,d['url'],raw,dict(http_status=None,truncation=False,run_id=run,source_verification_status='VERIFIED_IN_V4G_NOT_REVERIFIED',source_fetch_artifact=str(p)),dict(extracted=json.loads(e['enrichment_evidence']),promoted=[e['enriched_email'],e['enriched_social']],reason=e['enrichment_reason']))
        evidence['historical_cache_timestamp']=d['at'];evidence['historical_version_warning']='Earlier V4C cache, not the V4G response. Cache stores decoded HTML; original wire byte count/status unavailable.'
        path.write_text(json.dumps(evidence,indent=2),encoding='utf-8');email_count+=len(evidence['emails'])
        inventory.append({'source':source,'status':'CAPTURED_HISTORICAL_VERSION','evidence_path':str(path),'cache_sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
        # Do not use different-version cache to prove absence in the V4G observation.
        # Positive plain-text email evidence is inspectable only for the cache version.
    counts=dict(Counter(r['classification'] for r in new));counts={k:counts.get(k,0) for k in 'ABCDEF'}
    summary=dict(run_id=run,path=str(out),fetched_pages_examined=len(inventory),new_evidence_files=sum(i['status']=='CAPTURED_HISTORICAL_VERSION' for i in inventory),unable_to_backfill=sum(i['status']=='UNABLE_TO_BACKFILL' for i in inventory),visible_text_files_generated=sum(i['status']=='CAPTURED_HISTORICAL_VERSION' for i in inventory),public_link_files_generated=sum(i['status']=='CAPTURED_HISTORICAL_VERSION' for i in inventory),email_evidence_records=email_count,old_counts=old['classification_counts'],new_counts=counts,reduction_in_F=old['classification_counts']['F']-counts['F'],audit_reason='V4G classifications retained: recoverable HTML is an earlier version, so absence or extraction behavior cannot be attributed to the V4G response.',recommendation='One controlled evidence-capture refetch validation on the same ten leads; no changes to extraction or promotion.',brave_searches=0,new_public_requests=0,hubspot_writes=0,outbound_actions=0)
    for name,value in [('summary.json',summary),('evidence_capture_summary.json',inventory),('provenance.json',{'inputs':[str(g),str(h)],'method':'OFFLINE_CACHE_BACKFILL','no_refetch':True}),('v4h_reaudit.json',new)]: (out/name).write_text(json.dumps(value,indent=2),encoding='utf-8')
    (out/'report.md').write_text('# V4I evidence capture\n\n'+json.dumps(summary,indent=2)+'\n\n'+json.dumps(inventory,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
