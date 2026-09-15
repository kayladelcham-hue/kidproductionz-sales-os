"""Saved-cohort validation only: no search provider imports."""
import json,uuid
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
from urllib.parse import urldefrag
from v4e_bounded import BoundedFetcher
from v4d_verification import check_candidate,FetchFailure
from discovery_identity import verify
from discovery_handoff import inspect_verified
from enrichment_pipeline import adapt
from outreach_routing import routing

class FragmentFetcher(BoundedFetcher):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.aliases=[];self.fragment_duplicates=0;self.failed_resources={};self.origins={}
    def fetch(self,url):
        resource=urldefrag(url)[0]
        self.aliases.append({'original_url':url,'network_url':resource})
        if resource in self.origins and url not in self.origins[resource] and (resource in self.pages or resource in self.failed_resources):self.fragment_duplicates+=1
        self.origins.setdefault(resource,set()).add(url)
        if resource in self.failed_resources:raise self.failed_resources[resource]
        try:return super().fetch(resource)
        except FetchFailure as e:self.failed_resources[resource]=e;raise

def run(base,root):
    items=json.loads((base/'v4b_candidate_input.json').read_text());candidates=json.loads((base/'discovery_candidates.json').read_text())
    if len(items)!=10 or len({i['lead_id'] for i in items})!=10:raise ValueError('Expected original ten-lead cohort')
    cfg=json.loads((root/'config/enrichment_config.json').read_text());rcfg=json.loads((root/'config/outreach_config.json').read_text())
    rid=uuid.uuid4().hex;f=FragmentFetcher(cfg,rid);table=[];details=[];verified=0
    before=Counter();after=Counter()
    for item in items:
        row=item['original_lead'];outcomes=[];checks=[]
        for c in candidates:
            if c['lead_id']!=item['lead_id']:continue
            check=check_candidate(c['candidate_url'],row.get('website',''),f)
            if check['status']=='FETCHED':
                effective=check['effective_url'];identity=verify(row,effective,{'html':f.fetch(effective)})
                check['identity']=identity
                if identity['candidate_status']=='VERIFIED':
                    verified+=1
                    handoff={'original_lead':row,'verified_candidates':[{'url':effective,'evidence':identity}]}
                    outcome=inspect_verified(handoff,f,cfg,rid,datetime.now(timezone.utc).isoformat())[0];outcomes.append(outcome)
            checks.append(check)
        usable=[o['v4b_result'] for o in outcomes if o.get('v4b_result',{}).get('enrichment_status')=='ENRICHED']
        emails={e['enriched_email'] for e in usable if e['enriched_email']};socials={e['enriched_social'] for e in usable if e['enriched_social']}
        chosen=None
        if len(emails)<=1 and len(socials)<=1 and usable:
            chosen=dict(usable[0])
            for field in ('email','social'):
                for e in usable:
                    if e['enriched_'+field]:
                        for k in ('enriched_'+field,field+'_confidence',field+'_source_url'):chosen[k]=e[k]
        statuses=[o.get('v4b_result',{}).get('enrichment_status',o.get('status','REVIEW')) for o in outcomes]
        status='ENRICHED' if chosen else 'REVIEW' if usable else 'ERROR' if 'ERROR' in statuses else 'REVIEW' if 'REVIEW' in statuses or not outcomes else 'NO_NEW_DATA'
        reasons=[o.get('v4b_result',{}).get('enrichment_reason',o.get('reason','')) for o in outcomes]
        if not outcomes:reasons=[c.get('identity',{}).get('identity_reason') or c.get('reason') or '; '.join(x['code'] for x in c.get('failures',[])) for c in checks]
        if usable and not chosen:reasons=['Conflicting independently enriched channels; no promotion']
        enriched=adapt(chosen) if chosen else row
        rb,_,cb=routing(row,rcfg);ra,_,ca=routing(enriched,rcfg)
        for field in ('email','social','website'):
            before[field]+=bool(cb[field]);after[field]+=bool(ca[field])
        entry=dict(lead_id=item['lead_id'],business=row['name'],source_status=dict(Counter(c.get('identity',{}).get('candidate_status',c['status']) for c in checks)),enrichment_status=status,new_email=chosen['enriched_email'] if chosen else '',new_social=chosen['enriched_social'] if chosen else '',website_contact_evidence=[c['effective_url'] for c in checks if c.get('identity',{}).get('candidate_status')=='VERIFIED'],route_before=rb,route_after=ra,review_reason='; '.join(dict.fromkeys(filter(None,reasons))) if status in ('REVIEW','ERROR') else '')
        table.append(entry);details.append({'lead_id':item['lead_id'],'checks':checks,'outcomes':outcomes})
    summary=dict(total_leads_processed=10,candidates_examined=len(candidates),public_page_requests=f.requests,duplicate_requests_avoided=f.fragment_duplicates,verified_sources=verified,enrichment_counts=dict(Counter(r['enrichment_status'] for r in table)),usable_before=dict(before),usable_after=dict(after),new_emails=sum(bool(r['new_email']) for r in table),new_socials=sum(bool(r['new_social']) for r in table),new_websites=0,verified_website_contact_evidence_count=sum(len(r['website_contact_evidence']) for r in table),other_approved_contact_data=[],routes_after=dict(Counter(r['route_after'] for r in table)),route_changes=sum(r['route_before']!=r['route_after'] for r in table),brave_searches=0,hubspot_writes=0,outbound_communications=0,per_lead=table)
    out=base/('v4f_'+rid);out.mkdir()
    for name,value in [('summary.json',summary),('details.json',details),('provenance.json',{'pages':f.provenance,'aliases':f.aliases,'failures':f.failures})]:(out/name).write_text(json.dumps(value,indent=2),encoding='utf-8')
    return {'output':str(out.resolve()),**summary}
if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    print(json.dumps(run(root/'discovery_outputs/bf5212e7dee74a9fb70a751afd08a0b3',root),indent=2))
