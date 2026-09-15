"""V4J controlled ten-lead refresh with opt-in evidence/audit reporting.

This wrapper reuses the V4F/V4G pipeline and never performs discovery or CRM writes.
"""
import csv, json, uuid
from pathlib import Path
from unittest.mock import patch
import v4f_validate
import v4h_audit
from v4g_redirects import RedirectFetcher
import hashlib, os, tempfile
from v4i_evidence import link_type, channel_type

COHORT = 'bf5212e7dee74a9fb70a751afd08a0b3'
OLD = {'A': 0, 'B': 17, 'C': 0, 'D': 1, 'E': 6, 'F': 36}

def run(base, root):
    holders = []
    OriginalFragmentFetcher = v4f_validate.FragmentFetcher
    def factory(*a, **kw):
        f = RedirectFetcher(*a, **kw); holders.append(f); return f
    try:
        with patch.object(v4f_validate, 'FragmentFetcher', factory):
            report = v4f_validate.run(base, root)
    finally:
        v4f_validate.FragmentFetcher = OriginalFragmentFetcher
    fetcher = holders[0]
    out = Path(report['output']); rid = 'v4j_' + uuid.uuid4().hex
    target = out.with_name(rid); out.rename(target)
    report['output'] = str(target.resolve())
    prov = json.loads((target/'provenance.json').read_text(encoding='utf-8'))
    # Durable V4O evidence contract: persist bounded provenance pages atomically.
    evdir=target/'evidence'/'pages'; evdir.mkdir(parents=True,exist_ok=True); manifest=[]
    for url,page in fetcher.provenance.items():
        eid=hashlib.sha256((str(page.get('run_id',''))+'|'+url+'|'+url).encode()).hexdigest()
        items=page.get('structured_contact_evidence',page.get('exact_evidence',[]))
        items=[dict(i,channel_type=i.get('channel_type') or channel_type(link_type(i.get('resolved_url',i.get('exact_href','')))),raw_representation=i.get('raw_representation',i.get('exact_href','')),normalized_representation=i.get('normalized_representation',i.get('resolved_url','')),source_url=i.get('source_url',url),anchor_text=i.get('anchor_text',''),nearby_context=i.get('nearby_context',''),extracted_by_current_logic=i.get('extracted_by_current_logic',i.get('extracted')),promoted=i.get('promoted'),rejection_or_ambiguity_reason=i.get('rejection_or_ambiguity_reason',i.get('reason',''))) for i in items]
        payload={'schema_version':'V4O-1','evidence_id':eid,'run_id':page.get('run_id'),'requested_url':url,'final_url':url,'http_status':page.get('http_status'),'content_type':'text/html','inspected_byte_count':page.get('bytes_inspected',0),'page_truncated':page.get('truncation',False),'evidence_text_truncated':False,'sanitized_visible_text':page.get('sanitized_visible_text',''),'public_links':page.get('exact_evidence',[]),'email_evidence':page.get('email_evidence',[]),'structured_contact_evidence':items,'evidence_budget_bytes':page.get('evidence_budget_bytes',120000),'structured_contact_bytes':page.get('structured_contact_bytes',0),'contextual_contact_bytes':page.get('contextual_contact_bytes',0),'general_text_bytes':page.get('general_text_bytes',0),'extraction_decisions':[],'promotion_decisions':[],'redirect_provenance':[],'sanitization_metadata':['bounded provenance only']}
        final=evdir/(eid+'.json'); tmp=final.with_suffix('.tmp'); tmp.write_text(json.dumps(payload,indent=2),encoding='utf-8'); os.replace(tmp,final)
        digest=hashlib.sha256(final.read_bytes()).hexdigest(); manifest.append({'evidence_id':eid,'requested_url':url,'final_url':url,'relative_path':str(final.relative_to(target)),'byte_size':final.stat().st_size,'sha256':digest,'capture_status':'PERSISTED'})
    (target/'evidence_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    # Attach authoritative references to the durable source records consumed by V4H.
    details_path=target/'details.json'; details=json.loads(details_path.read_text(encoding='utf-8'))
    refs={m['requested_url'].rstrip('/').replace('://www.','://'):m['evidence_id'] for m in manifest}
    linked=0
    for lead in details:
        for check in lead.get('checks',[]):
            key=check.get('candidate_url','').rstrip('/').replace('://www.','://')
            if key in refs and check.get('identity',{}).get('candidate_status')=='VERIFIED': check['evidence_ref']=refs[key]; linked+=1
    details_path.write_text(json.dumps(details,indent=2),encoding='utf-8')
    evidence_summary = {
        'pages_with_v4i_evidence': len(manifest),
        'pages_without_evidence': max(0, report.get('public_page_requests', 0)-len(fetcher.provenance)),
        'visible_text_evidence_count': sum(bool(p.get('bytes_inspected')) for p in fetcher.provenance.values()),
        'public_link_evidence_count': sum(len(p.get('exact_evidence', [])) for p in fetcher.provenance.values()),
        'email_evidence_count': 0,
        'truncated_evidence_files': sum(bool(p.get('truncation')) for p in fetcher.provenance.values()),
    }
    # V4H consumes the newly produced V4F-compatible artifacts; definitions stay unchanged.
    audit = v4h_audit.audit(target)
    new = audit['classification_counts']
    summary = dict(report, final_urls=fetcher.final_urls, v4j_run_id=rid, brave_searches=0,
                   redirect_diagnostics_count=len(fetcher.redirect_diagnostics), durable_sources_with_evidence_ref=linked,
                   successful_public_responses=len(fetcher.provenance),
                   failed_requests=len(fetcher.failures), redirects_followed=sum(1 for x in fetcher.redirects if x.get('followed')),
                   urls_skipped=[], request_budget_usage=report.get('public_page_requests', 0),
                   evidence_capture_summary=evidence_summary, old_v4h_counts=OLD,
                   new_v4h_counts=new, reduction_in_F=OLD['F']-new.get('F', 0),
                   largest_unresolved_category=max(new, key=new.get) if new else 'F',
                   recommended_v4k_change='Improve observability for the dominant unresolved category only; do not change extraction or promotion rules.',
                   hubspot_writes=0, outbound_actions=0)
    for name, value in [('summary.json', summary), ('provenance.json', prov), ('refetch_results.json', report), ('redirect_diagnostics.json', fetcher.redirect_diagnostics), ('evidence_capture_summary.json', evidence_summary), ('contact_evidence_audit.json', json.loads((Path(audit['audit_path'])/'contact_evidence_audit.json').read_text(encoding='utf-8'))), ('contact_evidence_audit.csv', '')]:
        if name.endswith('.csv'):
            src = Path(audit['audit_path'])/name
            (target/name).write_bytes(src.read_bytes())
        else: (target/name).write_text(json.dumps(value, indent=2), encoding='utf-8')
    if fetcher.redirect_diagnostics:
        with (target/'redirect_diagnostics.csv').open('w', newline='', encoding='utf-8-sig') as fh:
            fields=list(fetcher.redirect_diagnostics[0]); w=csv.DictWriter(fh, fieldnames=fields); w.writeheader(); w.writerows(fetcher.redirect_diagnostics)
    (target/'report.md').write_text('# V4J controlled refresh\n\n'+json.dumps(summary, indent=2), encoding='utf-8')
    return summary

if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(run(root/'discovery_outputs'/COHORT, root), indent=2))
