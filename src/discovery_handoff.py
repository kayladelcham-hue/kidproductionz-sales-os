"""Separate adapter invokes unchanged V4B safeguards; no automatic cross-domain replacement."""
from enrichment_pipeline import enrich
from normalize import domain,url

def inspect_verified(item,public_provider,cfg,run,at):
    results=[]
    for candidate in item['verified_candidates']:
        if candidate['evidence'].get('candidate_status')!='VERIFIED':continue
        original=item['original_lead'];working=dict(original)
        source=candidate['url']
        if original.get('website') and domain(url(original['website']))!=domain(url(source)):
            results.append({'candidate_url':source,'status':'REVIEW','reason':'Different domain; original preserved'});continue
        working['website']=source
        results.append({'candidate_url':source,'original_lead':dict(original),'v4b_result':enrich(working,public_provider,cfg,run,at)})
    return results
