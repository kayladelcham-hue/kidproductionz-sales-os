"""Offline contact-evidence audit. No fetch, search, or production mutations."""
import json,csv,uuid,hashlib
from pathlib import Path
from collections import Counter
from urllib.parse import urlsplit
CHANNELS=('mailto','plain_text_email','instagram','facebook','tiktok','linkedin','contact_link','about_link','booking_link','other_contact')
AUDIT_FIELDS=('lead_id','business_name','verified_url','final_url','source_type','contact_channel_type','exact_visible_representation','extractor_result','enrichment_result','final_promoted_value','classification','exact_reason','safeguard','truncated')

def matches(channel,value):
    p=urlsplit(value);h=(p.hostname or '').removeprefix('www.')
    if channel=='mailto':return value.lower().startswith('mailto:')
    if channel in ('instagram','facebook','tiktok','linkedin'):return h==channel+'.com'
    if channel=='contact_link':return p.path.rstrip('/').lower() in ('/contact','/contact-us')
    if channel=='about_link':return p.path.rstrip('/').lower() in ('/about','/about-us')
    if channel=='booking_link':return h in ('booksy.com','vagaro.com','fresha.com','styleseat.com','salonlofts.com')
    if channel=='other_contact':return value.lower().startswith('tel:')
    return False

def classify(channel,visible,extracted,promoted,reason):
    if not visible:return 'F','Saved artifacts contain selected link evidence, not complete visible HTML/text; absence cannot be established.'
    if promoted:return 'B','Explicit source evidence was extracted and promoted.'
    if extracted and channel in ('instagram','facebook','tiktok','linkedin') and reason=='Multiple plausible social findings':return 'E',reason
    if extracted and channel=='mailto':return 'D',reason or 'Extracted contact not present in promoted fields.'
    return 'B','Explicit link retained in extraction provenance; supporting evidence, not a new promoted lead field.'

def audit(base):
    paths=[base/n for n in ('summary.json','details.json','provenance.json')]
    summary,details,provenance=[json.loads(p.read_text(encoding='utf-8')) for p in paths]
    manifest={x['evidence_id']:x for x in json.loads((base/'evidence_manifest.json').read_text(encoding='utf-8'))} if (base/'evidence_manifest.json').exists() else {}
    names={r['lead_id']:r['business'] for r in summary['per_lead']}
    rows=[];sources=0
    for lead in details:
        for outcome in lead['outcomes']:
            e=outcome.get('v4b_result')
            if not e:continue
            source=outcome['candidate_url']
            if not any(c.get('effective_url')==source and c.get('identity',{}).get('candidate_status')=='VERIFIED' for c in lead['checks']):continue
            sources+=1;final=summary.get('final_urls',{}).get(source,source)
            ref=next((c.get('evidence_ref') for c in lead.get('checks',[]) if c.get('candidate_url')==source and c.get('evidence_ref')),None)
            page={}
            if ref in manifest:
                fp=base/manifest[ref]['relative_path']
                if fp.exists():
                    ev=json.loads(fp.read_text(encoding='utf-8')); links=ev.get('public_links',[]) or ev.get('structured_contact_evidence',[]); page={'exact_evidence':links,'truncation':ev.get('page_truncated'),'visible_text':ev.get('sanitized_visible_text','')}
            if not page: page=provenance['pages'].get(final,{})
            evidence=json.loads(e.get('enrichment_evidence') or '[]')
            for channel in CHANNELS:
                visible=sorted({x['exact_href'] for x in page.get('exact_evidence',[]) if matches(channel,x.get('resolved_url',''))})
                field='email' if channel in ('mailto','plain_text_email') else 'social'
                extracted=sorted({x['value'] for x in evidence if x['source_url']==source and x['field']==field and (channel=='mailto' or matches(channel,x['value']))})
                value=e.get('enriched_'+field,'')
                promoted=value if (channel=='mailto' or matches(channel,value)) else ''
                category,reason=classify(channel,visible,extracted,promoted,e['enrichment_reason'])
                rows.append(dict(lead_id=lead['lead_id'],business_name=names[lead['lead_id']],verified_url=source,final_url=final,source_type='OFFICIAL_WEBSITE',contact_channel_type=channel,exact_visible_representation=visible,extractor_result=extracted or visible,enrichment_result=e['enrichment_status'],final_promoted_value=promoted,classification=category,exact_reason=reason,safeguard=e['enrichment_reason'] if category in ('D','E') else '',truncated=page.get('truncation')))
    counts={k:sum(r['classification']==k for r in rows) for k in 'ABCDEF'}
    recommendation='V4I: persist a bounded, sanitized visible-text and complete public-anchor audit sidecar from each already-fetched page, including final URL, byte count, truncation and extraction decisions. Do not increase fetch limits or change promotion rules.'
    result=dict(verified_sources_inspected=sources,contact_channels_inspected=len(rows),classification_counts=counts,largest_failure_category=max('ACDEF',key=lambda k:counts[k]),recommended_v4i_change=recommendation,brave_searches=0,public_requests=0,hubspot_writes=0,outbound_actions=0,limitations='Selected provenance cannot prove NOT_PRESENT or a missed extraction; F is intentional. Counts are per source/channel, not unique leads.')
    rid=uuid.uuid4().hex;out=base.parent/('v4h_'+rid);out.mkdir()
    result.update(audit_run_id=rid,audit_path=str(out.resolve()))
    prov=dict(inputs=[{'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths],method='V4G_ARTIFACTS_ONLY',prior_refetch_audit_used=False)
    for name,value in [('summary.json',result),('provenance.json',prov),('contact_evidence_audit.json',rows)]: (out/name).write_text(json.dumps(value,indent=2),encoding='utf-8')
    with (out/'contact_evidence_audit.csv').open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else list(AUDIT_FIELDS));w.writeheader()
        for row in rows:w.writerow({k:json.dumps(v) if isinstance(v,list) else v for k,v in row.items()})
    lines=['# V4H artifact-only audit','',json.dumps(counts),'',recommendation,'',result['limitations'],'','## Per-lead summary','']
    for lid in dict.fromkeys(r['lead_id'] for r in rows):
        group=[r for r in rows if r['lead_id']==lid]
        lines.append('- '+lid+' '+group[0]['business_name']+': captured '+str(sorted({r['contact_channel_type'] for r in group if r['exact_visible_representation']}))+'; withheld '+str(sorted({r['contact_channel_type'] for r in group if r['classification']=='D'}))+'; ambiguous '+str(sorted({r['contact_channel_type'] for r in group if r['classification']=='E'})))
    lines+=['','## Per-source/channel audit','','| Lead | Source | Channel | Evidence | Extracted | Enrichment | Promoted | Class | Reason |','|---|---|---|---|---|---|---|---|---|']
    for r in rows:lines.append('| '+' | '.join(str(v).replace('|','/').replace('\n',' ') for v in [r['lead_id'],r['verified_url'],r['contact_channel_type'],r['exact_visible_representation'],r['extractor_result'],r['enrichment_result'],r['final_promoted_value'],r['classification'],r['exact_reason']])+' |')
    (out/'report.md').write_text('\n'.join(lines),encoding='utf-8')
    return result
if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    print(json.dumps(audit(root/'discovery_outputs/bf5212e7dee74a9fb70a751afd08a0b3/v4g_0710b5ed12164a48806d347d1f00824a'),indent=2))
