"""Evidence isolation and additive enrichment; fixtures and public provider share one interface."""
import json
from urllib.parse import urljoin
from normalize import url
from enrichment_identity import identity
from enrichment_email import emails,email_type
from enrichment_social import socials
from enrichment_website import Page,contact_page
from enrichment_sources import SourceUnavailable

FIELDS='enrichment_run_id enrichment_status enrichment_reason enrichment_confidence original_email enriched_email email_type email_confidence email_source_url original_social enriched_social social_platform social_handle social_confidence social_source_url original_website enriched_website website_confidence website_source_url contact_name contact_title contact_confidence contact_source_url enrichment_evidence enrichment_flags enriched_at'.split()

def enrich(row,provider,cfg,run,at):
    if set(FIELDS)&set(row):raise ValueError('Input already contains enrichment fields; use original source')
    out={**row,**{k:'' for k in FIELDS}}
    out.update(enrichment_run_id=run,enriched_at=at,enrichment_status='NO_NEW_DATA')
    for field in ('email','social','website'):out['original_'+field]=row.get(field,'')
    evidence=[]
    def finish(status,reason):
        out.update(enrichment_status=status,enrichment_reason=reason,enrichment_evidence=json.dumps(evidence),enrichment_flags=reason if status in ('REVIEW','ERROR') else '')
        return out
    base=url(row.get('website',''))
    if not base:return finish('NO_NEW_DATA','No usable supplied website; external discovery not configured')
    if any(t in str(row.get('flags','')) for t in ('SHARED_PHONE','UNCERTAIN_DUPLICATE','IDENTITY_CONFLICT')):
        return finish('REVIEW','Shared or conflicting identity signals')
    try:
        pages=[(base,Page(provider.fetch(base)))]
        good,why=identity(row,base,' '.join(pages[0][1].text),cfg)
        if not good:return finish('REVIEW',why)
        contact=contact_page(base,pages[0][1].links)
        if contact and contact!=base:pages.append((contact,Page(provider.fetch(contact))))
        findings={'email':{},'social':{}}
        for source,page in pages:
            good,why=identity(row,source,' '.join(page.text),cfg)
            links=[urljoin(source,l) if not l.startswith('mailto:') else l for l in page.links]
            for field,values in [('email',emails(links)),('social',socials(links,cfg))]:
                for value in values:
                    ev=dict(field=field,value=value,source_url=source,source_type='OFFICIAL_WEBSITE' if source==base else 'OFFICIAL_CONTACT_PAGE',evidence_description=why+'; exact published link',retrieval_method='PUBLIC_GET_OR_CACHE',confidence='HIGH' if good else 'LOW',run_id=run,timestamp=at)
                    evidence.append(ev)
                    if good:findings[field][value]=ev
                    else:return finish('REVIEW','Contact page identity not independently corroborated')
        if any(email_type(v)=='OTHER' for v in findings['email']):
            return finish('REVIEW','Named/other email requires manual business-role verification')
        for field,values in findings.items():
            if len(values)>1:return finish('REVIEW','Multiple plausible '+field+' findings')
            if values and row.get(field) and row[field] not in values:return finish('REVIEW','Conflicting original '+field+'; original preserved')
        for field,values in findings.items():
            if values and not row.get(field):
                value=next(iter(values));ev=values[value]
                out['enriched_'+field]=value;out[field+'_confidence']='HIGH';out[field+'_source_url']=ev['source_url']
        if out['enriched_email']:out['email_type']=email_type(out['enriched_email'])
        if out['enriched_social']:
            s=socials([out['enriched_social']],cfg)[out['enriched_social']]
            out.update(social_platform=s['platform'],social_handle=s['handle'])
        out['enrichment_confidence']='HIGH' if any(out['enriched_'+f] for f in ('email','social')) else ''
        return finish('ENRICHED' if out['enrichment_confidence'] else 'NO_NEW_DATA','Exact public contact links with corroborated identity' if out['enrichment_confidence'] else 'No new supported channels')
    except SourceUnavailable as exc:return finish('REVIEW',str(exc))
    except Exception:return finish('ERROR','Technical record processing failure')

def adapt(row):
    out=dict(row)
    # Original values remain in original_* and in the authoritative enriched dataset.
    if row['enrichment_status']=='ENRICHED':
        for field in ('email','social','website'):
            if not out.get(field) and row[field+'_confidence']=='HIGH':out[field]=row['enriched_'+field]
    return out
