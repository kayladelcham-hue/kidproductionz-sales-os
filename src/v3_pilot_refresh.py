"""Refresh original pilot using GET-only V2 reads; never execute an import."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import uuid
from check_hubspot import load_config
from hubspot_client import HubSpotReader
from hubspot_snapshot import retrieve, validate, digest
from crm_normalize import identity
from crm_match import CompanyIndex, classify
from v3_plan import load_import_config, validate_plan, build_plan, save_plan

ROOT = Path(__file__).resolve().parents[1]
METADATA = { 'kidproductionz_' + suffix: expected for suffix, expected in [
    ('source_run_id', ('string','text')), ('lead_score', ('number','number')),
    ('lead_grade', ('string','text')), ('category', ('string','text')),
    ('score_explanation', ('string','textarea')), ('lead_id', ('string','text')),
    ('v2_run_id', ('string','text'))]}


def refresh(original, cfg, match_cfg, reader, root):
    if cfg['enabled'] is not False or cfg['pilot_limit'] != 10:
        raise ValueError('Requires disabled V3 and pilot limit exactly 10')
    validate_plan(original, cfg)
    if original['count'] != 10:
        raise ValueError('Supply the original ten-company pilot plan')
    if str(match_cfg['portal_id']) != original['portal_id']:
        raise ValueError('Configured account differs from original plan')
    response = reader.get('/crm/v3/properties/companies')
    definitions = response.get('results')
    if not isinstance(definitions, list) or response.get('paging'):
        raise ValueError('Incomplete property schema')
    schema = {p['name']:p for p in definitions}
    if len(schema) != len(definitions):
        raise ValueError('Duplicate property definitions')
    for name, expected in METADATA.items():
        p = schema.get(name, {})
        if (p.get('type'),p.get('fieldType')) != expected or p.get('archived') or p.get('modificationMetadata',{}).get('readOnlyValue'):
            raise ValueError('Missing/incompatible/unwritable metadata: ' + name)
    snapshot = retrieve(reader, match_cfg)
    validate(snapshot, match_cfg)
    index = CompanyIndex(snapshot['records'], match_cfg)
    checks, kept = [], []
    for item in original['items']:
        result = classify(identity(item['source'], match_cfg), index, match_cfg)
        checks.append({'lead_id':item['lead_id'], 'name':item['request']['properties']['name'],
                       'action':'KEEP' if result['crm_status']=='NEW' else 'SKIP', 'recheck':result})
        if result['crm_status'] == 'NEW': kept.append(item['lead_id'])
    # Build from original source rows, then retain only the original survivors.
    plan = build_plan(Path(original['summary_path']), cfg, schema,
                      [i['lead_id'] for i in original['items']])
    plan['items'] = [i for i in plan['items'] if i['lead_id'] in kept]
    plan['count'] = len(plan['items'])
    coverage = {}
    for item in plan['items']:
        props = item['request']['properties']
        absent = [name for name in METADATA if name not in props]
        if absent:
            raise ValueError('Pilot metadata absent for ' + item['lead_id'] + ': ' + ', '.join(absent))
        coverage[item['lead_id']] = list(METADATA)
    plan['pilot_refresh'] = {'original_plan_sha256':original['plan_sha256'],
        'snapshot_id':snapshot['snapshot_id'], 'checks':checks, 'metadata_coverage':coverage}
    plan['warnings'] = ['Read-only pilot refresh; any future create still requires a fresh per-write duplicate check.',
                        'Skipped original pilot leads are not replaced. No import is approved.']
    plan.pop('plan_sha256')
    plan['plan_sha256'] = digest(plan)
    validate_plan(plan, cfg)
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '_' + uuid.uuid4().hex[:8]
    parent = root / 'v3_imports' / 'pilot_refreshes'
    parent.mkdir(parents=True, exist_ok=True)
    staging = parent / (run_id + '.incomplete')
    final = parent / run_id
    staging.mkdir()
    def write(name, value):
        with (staging/name).open('x',encoding='utf-8') as f: json.dump(value,f,indent=2)
    write('snapshot.json', snapshot)
    write('schema.json', response)
    saved = save_plan(plan, staging)
    # Report final paths; directory is finalized only after every artifact is saved.
    paths = {k:str(final/Path(v).relative_to(staging)) for k,v in saved.items() if k in ('plan','approval_template')}
    report = {**paths,'snapshot':str(final/'snapshot.json'),'schema':str(final/'schema.json'),
        'report':str(final/'report.json'),'checked':10,'proposed':len(kept),'skipped':10-len(kept),
        'snapshot_company_count':len(snapshot['records']),'checks':checks,'metadata_coverage':coverage,
        'proposed_company_names':[i['request']['properties']['name'] for i in plan['items']],
        'v3_enabled':False,'writes':0,'approved':False,
        'warnings':snapshot.get('missing_optional_properties',[])}
    write('report.json',report)
    staging.rename(final)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original-plan',type=Path,required=True)
    args=parser.parse_args()
    cfg=load_import_config(ROOT/'config/hubspot_import.json')
    match=load_config(ROOT/'config/hubspot_matching.json')
    if match['token_env'] != 'HUBSPOT_READONLY_TOKEN':
        raise ValueError('Requires HUBSPOT_READONLY_TOKEN')
    original=json.loads(args.original_plan.read_text(encoding='utf-8-sig'))
    reader=HubSpotReader.from_environment(match)
    print(json.dumps(refresh(original,cfg,match,reader,ROOT),indent=2))

if __name__=='__main__': main()
