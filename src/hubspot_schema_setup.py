"""One-time company schema setup. Preview by default; no CRM record endpoints."""
import argparse
import hashlib
import json
import os
import re
import sys
from urllib.error import HTTPError
from urllib.request import Request, build_opener
from hubspot_client import NoRedirect, redact

PROPERTIES = '/crm/v3/properties/companies'
GROUPS = PROPERTIES + '/groups'
GROUP = dict(name='kidproductionz', label='KidProductionz', displayOrder=-1)
DEFINITIONS = [dict(name='kidproductionz_' + suffix, label='KidProductionz ' + label,
                    type=typ, fieldType=field, groupName='kidproductionz',
                    hidden=False, formField=False, hasUniqueValue=False)
    for suffix, label, typ, field in [
        ('source_run_id', 'Source Run ID', 'string', 'text'),
        ('lead_score', 'Lead Score', 'number', 'number'),
        ('lead_grade', 'Lead Grade', 'string', 'text'),
        ('category', 'Category', 'string', 'text'),
        ('score_explanation', 'Score Explanation', 'string', 'textarea'),
        ('lead_id', 'Lead ID', 'string', 'text'),
        ('v2_run_id', 'V2 Check Run ID', 'string', 'text')]]

class SchemaError(RuntimeError):
    pass

class SchemaClient:
    def __init__(self, apply=False):
        self.token = os.environ.get('HUBSPOT_SCHEMA_TOKEN', '').strip()
        if not self.token:
            raise SchemaError('HUBSPOT_SCHEMA_TOKEN is missing or blank; no request sent.')
        if not re.fullmatch(r'[A-Za-z0-9._~+/-]+=*', self.token):
            raise SchemaError('Malformed schema credential; no request sent.')
        self.apply = apply
        self.opener = build_opener(NoRedirect())

    def request(self, method, path, body=None):
        if path not in (PROPERTIES, GROUPS) or method not in ('GET', 'POST'):
            raise SchemaError('Operation is not allowlisted.')
        if method == 'GET' and body is not None:
            raise SchemaError('GET cannot have a body.')
        if method == 'POST':
            if not self.apply:
                raise SchemaError('Preview cannot write.')
            allowed = [GROUP] if path == GROUPS else DEFINITIONS
            if body not in allowed:
                raise SchemaError('Unapproved definition.')
        req = Request('https://api.hubapi.com' + path, method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json', 'Accept': 'application/json'})
        try:
            with self.opener.open(req, timeout=30) as response:
                return json.load(response)
        except HTTPError as exc:
            try:
                raw = exc.read().decode('utf-8', errors='replace')
                correlation = exc.headers.get('X-HubSpot-Correlation-Id') if exc.headers else None
            finally:
                exc.close()
            raise SchemaError(json.dumps(redact(dict(method=method, endpoint=path,
                status=exc.code, body=raw, correlation_id=correlation), self.token))) from None
        except Exception:
            raise SchemaError('Network or invalid-response failure; stopped without retry. Re-run preview before any further apply.') from None


def inventory(client, path):
    result = client.request('GET', path)
    if not isinstance(result, dict) or not isinstance(result.get('results'), list) or result.get('paging'):
        raise SchemaError('Incomplete schema response; stopped.')
    rows = result['results']
    if any(not isinstance(p, dict) or not isinstance(p.get('name'), str) for p in rows):
        raise SchemaError('Malformed schema response.')
    if len({p['name'] for p in rows}) != len(rows):
        raise SchemaError('Duplicate schema names in response.')
    return {p['name']: p for p in rows}


def plan(client):
    props = inventory(client, PROPERTIES)
    groups = inventory(client, GROUPS)
    operations = []
    group = groups.get(GROUP['name'])
    if group:
        if group.get('label') != GROUP['label'] or group.get('archived', False):
            raise SchemaError('Incompatible existing KidProductionz group; stopped.')
    else:
        operations.append(dict(method='POST', endpoint=GROUPS, body=GROUP))
    for wanted in DEFINITIONS:
        current = props.get(wanted['name'])
        if current is None:
            operations.append(dict(method='POST', endpoint=PROPERTIES, body=wanted))
            continue
        mismatch = [k for k, v in wanted.items() if current.get(k) != v]
        if current.get('archived', False) or current.get('modificationMetadata', {}).get('readOnlyValue', False):
            mismatch.append('active/writable')
        if mismatch:
            raise SchemaError('Incompatible property ' + wanted['name'] + ': ' + ', '.join(mismatch))
    digest = hashlib.sha256(json.dumps(operations, sort_keys=True).encode()).hexdigest()
    return operations, digest


def run(client, apply=False, approval=None):
    operations, digest = plan(client)
    print(json.dumps(dict(mode='APPLY' if apply else 'PREVIEW', approval_hash=digest,
                         operations=operations), indent=2))
    if not apply:
        return
    if not approval or approval != digest:
        raise SchemaError('Approval hash missing or changed; no writes made. Review a fresh preview.')
    for op in operations:
        client.request(op['method'], op['endpoint'], op['body'])
        print('CREATED ' + op['body']['name'])
    remaining, _ = plan(client)
    if remaining:
        raise SchemaError('Verification failed: definitions still missing. Do not proceed to import.')
    for prop in DEFINITIONS:
        print('PASS ' + prop['name'])
    print('Verified all seven properties. V3 was not enabled; no companies imported.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--approve-hash')
    args = parser.parse_args(argv)
    if args.approve_hash and not args.apply:
        parser.error('--approve-hash requires --apply')
    if args.apply and not args.approve_hash:
        parser.error('--apply requires --approve-hash from a reviewed preview')
    try:
        run(SchemaClient(apply=args.apply), args.apply, args.approve_hash)
        return 0
    except SchemaError as exc:
        print('SCHEMA SETUP STOPPED: ' + str(exc), file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())
