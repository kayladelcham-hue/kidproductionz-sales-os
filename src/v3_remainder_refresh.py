"""Prepare final remainder using GET-only V2 reads; never execute an import."""
import argparse
import copy
from v2_audit import load_run
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


def refresh(summary_path, cfg, match_cfg, reader, root):
    if cfg['enabled'] is not False:
        raise ValueError('V3 must remain disabled')
    cfg = copy.deepcopy(cfg)
    summary, groups = load_run(summary_path)
    if str(match_cfg['portal_id']) != str(summary['portal_id']):
        raise ValueError('Configured account differs from V2 run')
    if (root / 'v3_imports' / 'execution.lock').exists():
        raise ValueError('Import execution lock present; preparation blocked')
    journal = root / 'v3_imports' / 'import_journal.jsonl'
    journal_bytes = journal.read_bytes()
    events = [json.loads(line) for line in journal_bytes.decode('utf-8-sig').splitlines() if line.strip()]
    blocked, last, created_ids = set(), {}, set()
    for event in events:
        status = event.get('status')
        if status in ('ATTEMPT', 'CREATED', 'CREATE_FAILED_OR_UNKNOWN', 'SKIP_PREVIOUS_ATTEMPT'):
            key = event['source_key']
            blocked.add(key)
            if status != 'SKIP_PREVIOUS_ATTEMPT':
                last[key] = status
            if status == 'CREATED':
                created_ids.add(str(event['hubspot_company_id']))
    if any(status != 'CREATED' for status in last.values()):
        raise ValueError('Unresolved prior write outcome; reconcile before preparing final remainder')
    candidates = sorted(groups['NEW'], key=lambda row: row['lead_id'])
    excluded = [r['lead_id'] for r in candidates if digest([summary['input_sha256'],r['lead_id']]) in blocked]
    selected = [r['lead_id'] for r in candidates if r['lead_id'] not in excluded]
    cfg['pilot_limit'] = max(1, len(candidates))
    if not candidates:
        raise ValueError('Original V2 NEW population is empty')
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
    original = build_plan(summary_path, cfg, schema, [r['lead_id'] for r in candidates])
    checks, kept = [], []
    for item in original['items']:
        if item['lead_id'] not in selected:
            continue
        result = classify(identity(item['source'], match_cfg), index, match_cfg)
        if str(result.get('hubspot_id', '')) in created_ids and result['crm_status'] == 'NEW':
            raise ValueError('Unexpected NEW classification for prior created ID')
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
    plan['batch_refresh'] = {'original_plan_sha256':original['plan_sha256'],
        'snapshot_id':snapshot['snapshot_id'], 'checks':checks, 'metadata_coverage':coverage}
    plan['warnings'] = ['Read-only remainder refresh; any future create still requires a fresh per-write duplicate check.',
                        'Skipped remainder leads are not replaced. No import is approved.']
    plan.pop('plan_sha256')
    plan['plan_sha256'] = digest(plan)
    validate_plan(plan, cfg)
    if journal.read_bytes() != journal_bytes or (root/'v3_imports'/'execution.lock').exists():
        raise ValueError('Import history changed during preparation; rerun')
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '_' + uuid.uuid4().hex[:8]
    parent = root / 'v3_imports' / 'remainder_refreshes'
    parent.mkdir(parents=True, exist_ok=True)
    staging = parent / (run_id + '.incomplete')
    final = parent / run_id
    staging.mkdir()
    def write(name, value):
        with (staging/name).open('x',encoding='utf-8') as f: json.dump(value,f,indent=2)
    write('snapshot.json', snapshot)
    write('schema.json', response)
    write('batch_config.json', cfg)
    saved = save_plan(plan, staging)
    # Report final paths; directory is finalized only after every artifact is saved.
    paths = {k:str(final/Path(v).relative_to(staging)) for k,v in saved.items() if k in ('plan','approval_template')}
    report = {**paths,'batch_config':str(final/'batch_config.json'),'snapshot':str(final/'snapshot.json'),'schema':str(final/'schema.json'),
        'report':str(final/'report.json'),'checked':len(selected),'proposed':len(kept),'skipped':len(selected)-len(kept), 'excluded_prior_lead_ids':excluded, 'original_v2_new_count':len(candidates), 'total_previously_attempted_lead_ids':len(excluded), 'journal_attempted_source_count':len(blocked),
        'snapshot_company_count':len(snapshot['records']),'checks':checks,'metadata_coverage':coverage,
        'proposed_company_names':[i['request']['properties']['name'] for i in plan['items']],
        'v3_enabled':False,'writes':0,'approved':False,
        'plan_sha256':plan['plan_sha256'], 'errors':[],
        'existing_skipped':sum(c['recheck']['crm_status']=='EXISTING' for c in checks),
        'review_skipped':sum(c['recheck']['crm_status']=='REVIEW' for c in checks),
        'other_skipped':sum(c['recheck']['crm_status'] not in ('NEW','EXISTING','REVIEW') for c in checks),
        'other_skip_reasons':[c for c in checks if c['recheck']['crm_status'] not in ('NEW','EXISTING','REVIEW')],
        'warnings':snapshot.get('missing_optional_properties',[])}
    write('report.json',report)
    staging.rename(final)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--summary',type=Path,required=True)
    args=parser.parse_args()
    cfg=load_import_config(ROOT/'config/hubspot_import.json')
    match=load_config(ROOT/'config/hubspot_matching.json')
    if match['token_env'] != 'HUBSPOT_READONLY_TOKEN':
        raise ValueError('Requires HUBSPOT_READONLY_TOKEN')
    summary, _ = load_run(args.summary)
    if summary['run_id'] != '20260913T011707975314Z_e2fbb18e':
        raise ValueError('This helper requires the approved original V2 run')
    reader=HubSpotReader.from_environment(match)
    print(json.dumps(refresh(args.summary,cfg,match,reader,ROOT),indent=2))

if __name__=='__main__': main()
