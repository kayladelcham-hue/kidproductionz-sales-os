"""Stable V5 manifest snapshot normalization."""
import json
from v5m_snapshot_diff import diff
VOLATILE={'source_file','timestamp','run_id','id'}
def stable(manifest):
 return {k:manifest[k] for k in sorted(manifest) if k not in VOLATILE}
def compare(actual,path):
 expected=json.loads(path.read_text(encoding='utf-8')); return stable(actual)==expected
def assert_snapshot(actual,path,scenario):
 expected=json.loads(path.read_text(encoding='utf-8')); d=diff(expected,stable(actual))
 if d:
  lines=[f'Snapshot mismatch: {scenario} ({path.name})']
  for x in d: lines += ['',x['field_path'],f"type: {x['change_type']}",f"expected: {json.dumps(x['expected'],sort_keys=True)}",f"actual: {json.dumps(x['actual'],sort_keys=True)}"]
  raise AssertionError('\n'.join(lines))
