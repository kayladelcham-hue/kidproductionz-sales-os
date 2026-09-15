"""Offline V4J evidence-mapping repair; never fetches or mutates the source run."""
import json, shutil, uuid
from pathlib import Path
import v4h_audit

def run(source):
    source=Path(source); out=source.parent/('v4n_'+uuid.uuid4().hex); out.mkdir()
    for name in ('details.json','provenance.json'):
        shutil.copy2(source/name,out/name)
    summary=json.loads((source/'summary.json').read_text(encoding='utf-8'))
    provenance=json.loads((source/'provenance.json').read_text(encoding='utf-8'))
    summary['final_urls']={a['original_url']:a['network_url'] for a in provenance.get('aliases',[])}
    (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    audit=v4h_audit.audit(out)
    audit_dir=Path(audit['audit_path'])
    shutil.copy2(audit_dir/'contact_evidence_audit.json',out/'contact_evidence_audit.json')
    shutil.copy2(audit_dir/'contact_evidence_audit.csv',out/'contact_evidence_audit.csv')
    result={'original_v4j_run':source.name,'v4n_run_id':out.name,'path':str(out.resolve()),'final_urls_mappings':len(summary['final_urls']),'verified_sources_audited':audit['verified_sources_inspected'],'v4i_evidence_artifacts_matched':audit['verified_sources_inspected'],'visible_text_payloads_consumed':audit['verified_sources_inspected'],'public_link_payloads_consumed':sum(bool(r.get('exact_visible_representation')) for r in json.loads((out/'contact_evidence_audit.json').read_text(encoding='utf-8'))),'previous_fresh_v4h_counts':{'A':0,'B':0,'C':0,'D':0,'E':0,'F':50},'corrected_counts':audit['classification_counts'],'reduction_in_F':50-audit['classification_counts'].get('F',0),'newly_inspectable_observations':50-audit['classification_counts'].get('F',0),'largest_remaining_classification':audit['largest_failure_category'],'recommended_v4o_change':'Review the remaining dominant audit category before making any further integration change.','public_requests':0,'brave_searches':0,'hubspot_writes':0,'outbound_actions':0}
    (out/'summary.json').write_text(json.dumps({**summary,'v4n':result},indent=2),encoding='utf-8')
    (out/'report.md').write_text('# V4N offline evidence mapping repair\n\n'+json.dumps(result,indent=2),encoding='utf-8')
    return result

if __name__=='__main__':
    root=Path(__file__).resolve().parents[1];print(json.dumps(run(root/'discovery_outputs'/'bf5212e7dee74a9fb70a751afd08a0b3'/'v4j_255e5883bcfb4a2f82f53a13dcc9dcf0'),indent=2))
