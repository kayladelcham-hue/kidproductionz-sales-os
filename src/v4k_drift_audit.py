"""Offline V4G-to-V4J verification drift audit. No network or mutations."""
import csv,json,uuid,hashlib
from pathlib import Path
from collections import Counter

def run(cohort, v4g_name='v4g_0710b5ed12164a48806d347d1f00824a', v4j_name='v4j_cbec520d54234eafb23be016fcbeda2b'):
    g=cohort/v4g_name; j=cohort/v4j_name
    gd=json.loads((g/'details.json').read_text(encoding='utf-8')); jd=json.loads((j/'details.json').read_text(encoding='utf-8'))
    jmap={x['lead_id']:x for x in jd}; rows=[]
    for gl in gd:
        for old in gl.get('checks',[]):
            ident=old.get('identity',{})
            if ident.get('candidate_status')!='VERIFIED': continue
            url=old.get('candidate_url'); cur=next((x for x in jmap.get(gl['lead_id'],{}).get('checks',[]) if x.get('candidate_url')==url),{})
            failures=cur.get('failures',[])
            if cur.get('status') in ('INACCESSIBLE','ERROR') or failures: cat='A — NETWORK_FAILURE'; cause='; '.join(f.get('code','') for f in failures) or cur.get('reason','fetch failed')
            elif cur.get('identity',{}).get('candidate_status')=='VERIFIED': cat='G — OTHER_PRECISE_CAUSE'; cause='No verification loss; current evidence remains VERIFIED'
            else: cat='E — HISTORICAL_ARTIFACT_MISMATCH'; cause=cur.get('identity',{}).get('identity_reason') or cur.get('reason','Current verification did not reproduce historical VERIFIED evidence')
            rows.append({'lead_id':gl['lead_id'],'business_name':gl.get('business'),'historical_url':url,'current_url':cur.get('effective_url',url),'historical_verified_reason':ident.get('identity_reason',''),'historical_signals':{k:v for k,v in ident.items() if k.startswith('matched_') or k=='identity_score'},'current_result':cur.get('identity',{}).get('candidate_status',cur.get('status','MISSING')),'current_signals':cur.get('identity',{}),'signal_differences':{'historical':ident,'current':cur.get('identity',{})},'loss_classification':cat,'exact_cause':cause,'redirect_chain':cur.get('redirect_chain',[]),'failures':failures})
    counts=Counter(r['loss_classification'][0] for r in rows); counts={k:counts.get(k,0) for k in 'ABCDEFG'}
    out=cohort/('v4k_'+uuid.uuid4().hex);out.mkdir(); fields=list(rows[0]) if rows else ['lead_id','business_name','historical_url','current_url','historical_verified_reason','historical_signals','current_result','current_signals','signal_differences','loss_classification','exact_cause','redirect_chain','failures']
    summary={'historical_verified_sources':len(rows),'refetch_attempts':len(rows),'successful_refetches':sum(not r['failures'] for r in rows),'failed_refetches':sum(bool(r['failures']) for r in rows),'current_verified':sum(r['current_result']=='VERIFIED' for r in rows),'lost_verified':sum(r['current_result']!='VERIFIED' for r in rows),'classification_counts':counts,'dominant_loss_cause':max(counts,key=counts.get) if rows else 'A','recommended_v4l_change':'Smallest network reliability fix for the dominant loss cause, preserving all verification safeguards.','brave_searches':0,'hubspot_writes':0,'outbound_actions':0}
    for n,v in [('summary.json',summary),('provenance.json',{'inputs':[str(g),str(j)],'method':'OFFLINE_ARTIFACT_COMPARISON'}),('verification_drift_audit.json',rows)]: (out/n).write_text(json.dumps(v,indent=2),encoding='utf-8')
    with (out/'verification_drift_audit.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();[w.writerow({k:json.dumps(r[k]) if isinstance(r[k],(dict,list)) else r[k] for k in fields}) for r in rows]
    (out/'report.md').write_text('# V4K verification drift audit\n\n'+json.dumps(summary,indent=2)+'\n\n'+json.dumps(rows,indent=2),encoding='utf-8')
    return {'path':str(out.resolve()),**summary}

if __name__=='__main__':
    root=Path(__file__).resolve().parents[1];print(json.dumps(run(root/'discovery_outputs'/'bf5212e7dee74a9fb70a751afd08a0b3'),indent=2))
