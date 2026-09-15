import json,csv,uuid
from datetime import datetime,timezone
from collections import Counter
from urllib.parse import urljoin,urlsplit
from discovery_queries import queries
from discovery_candidates import canonical,kind
from discovery_identity import verify
from discovery_providers import ProviderError
from enrichment_website import Page

def discover(rows,provider,cfg,output):
    if len(rows)>cfg['pilot_lead_limit'] or len(rows)>10:raise ValueError('Pilot limited to ten')
    ids=[r.get('lead_id') for r in rows]
    if any(not i for i in ids) or len(set(ids))!=len(ids):raise ValueError('Missing/duplicate lead IDs')
    run=uuid.uuid4().hex;at=datetime.now(timezone.utc).isoformat();all_candidates=[];handoff=[];errors=[];resolved=0;received=0
    for row in rows:
        seen={};links={};verified=[]
        for query in queries(row)[:min(3,cfg['max_queries_per_lead'])]:
            try:results=provider.search_business(query,cfg['max_results_per_query'])
            except ProviderError as e:errors.append({'lead_id':row['lead_id'],'reason':str(e)});break
            received+=len(results)
            for result in results:
                url=canonical(result['url'])
                if not url:continue
                provenance={k:result.get(k,'') for k in ('query','provider','rank','title','snippet')}
                if url in seen:seen[url]['discovery_evidence'].append(provenance);continue
                candidate=dict(lead_id=row['lead_id'],discovery_run_id=run,candidate_url=url,candidate_domain=urlsplit(url).hostname,candidate_source_type=kind(url),candidate_platform=kind(url) if kind(url) in ('INSTAGRAM','FACEBOOK','TIKTOK') else '',candidate_title=result.get('title',''),discovery_query=query,discovery_provider=result.get('provider',''),discovered_at=at,discovery_evidence=[provenance])
                try:
                    page=provider.fetch_public_page(url)
                    candidate.update(verify(row,url,page,links.get(url,'')))
                    if candidate['candidate_status']=='VERIFIED':
                        if candidate['candidate_source_type']=='OTHER_PUBLIC_SOURCE':candidate['candidate_source_type']='OFFICIAL_WEBSITE'
                        verified.append(candidate)
                        for link in Page(page.get('html','')).links:
                            target=canonical(urljoin(url,link))
                            if target:links[target]=url
                except Exception:candidate.update(candidate_status='INACCESSIBLE',candidate_confidence='LOW',identity_score=0,identity_reason='Source could not be safely fetched',conflict_flags='INACCESSIBLE')
                seen[url]=candidate
            if verified:resolved+=1;break
        all_candidates.extend(seen.values())
        handoff.append({'lead_id':row['lead_id'],'original_lead':dict(row),'verified_candidates':[{'url':c['candidate_url'],'source_type':c['candidate_source_type'],'evidence':c} for c in verified], 'instruction':'V4B must independently verify; source conflicts must not overwrite original website'})
    counts=Counter(c['candidate_status'] for c in all_candidates)
    summary=dict(total_input=len(rows),leads_with_candidates=len({c['lead_id'] for c in all_candidates}),leads_without_candidates=len(rows)-len({c['lead_id'] for c in all_candidates}),queries_executed=provider.queries_executed,cache_hits=provider.cache_hits,api_requests=getattr(provider.provider,'api_requests',0),network_requests=getattr(provider.provider,'api_requests',0)+getattr(getattr(provider.provider,'public',None),'requests',0),leads_resolved_before_query_limit=resolved,results_received=received,hubspot_writes=0,outbound_communications=0,errors=errors,monthly_budget_awareness='Per-run cap only; check Brave dashboard for account-wide monthly usage',candidate_count_by_source_type=dict(Counter(c['candidate_source_type'] for c in all_candidates)),candidate_count_by_platform=dict(Counter(c['candidate_platform'] for c in all_candidates)),identity_confidence_counts=dict(Counter(c['candidate_confidence'] for c in all_candidates)),review_reason_counts=dict(Counter(c['identity_reason'] for c in all_candidates if c['candidate_status'] in ('LIKELY','REVIEW','INACCESSIBLE'))))
    for status in ('VERIFIED','LIKELY','REVIEW','REJECTED','INACCESSIBLE'):summary[status.lower()+'_candidate_count']=counts[status]
    output.mkdir(parents=True,exist_ok=True);stage=output/(run+'.incomplete');stage.mkdir()
    for name,value in [('discovery_candidates.json',all_candidates),('discovery_summary.json',summary),('v4b_candidate_input.json',handoff)]:
        (stage/name).write_text(json.dumps(value,indent=2),encoding='utf-8')
    fields=sorted({k for c in all_candidates for k in c}) or ['lead_id','candidate_url','candidate_status']
    for name,data in [('discovery_candidates.csv',all_candidates),('discovery_review.csv',[c for c in all_candidates if c['candidate_status'] in ('LIKELY','REVIEW','INACCESSIBLE')])]:
        with (stage/name).open('x',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
            for c in data:
                values={k:json.dumps(v) if isinstance(v,(dict,list)) else str(v) for k,v in c.items()}
                w.writerow({k:"'"+v if v.lstrip().startswith(('=','+','-','@')) else v for k,v in values.items()})
    final=output/run;stage.rename(final)
    return {'output_directory':str(final.resolve()),**summary}
