import copy
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import hubspot_schema_setup as s

class Fake:
    def __init__(self):
        self.props = []
        self.groups = []
        self.writes = []
        self.ignore = False
    def request(self, method, path, body=None):
        rows = self.props if path == s.PROPERTIES else self.groups
        if method == 'GET':
            return {'results': copy.deepcopy(rows)}
        self.writes.append((path, body))
        if not self.ignore:
            rows.append(copy.deepcopy(body))
        return body

class SchemaTests(unittest.TestCase):
    def setUp(self):
        self.fake = Fake()
        self.output = patch('sys.stdout', new_callable=io.StringIO)
        self.output.start()
        self.addCleanup(self.output.stop)
    def test_preview_zero_writes(self):
        s.run(self.fake)
        self.assertEqual(self.fake.writes, [])
        self.assertEqual(len(s.plan(self.fake)[0]), 8)
    def test_exact_types(self):
        self.assertEqual(len(s.DEFINITIONS), 7)
        self.assertEqual([(p['type'], p['fieldType']) for p in s.DEFINITIONS], [('string','text'),('number','number'),('string','text'),('string','text'),('string','textarea'),('string','text'),('string','text')])
        self.assertTrue(all(not p['hasUniqueValue'] for p in s.DEFINITIONS))
    def test_apply_and_verify(self):
        s.run(self.fake, True, s.plan(self.fake)[1])
        self.assertEqual(len(self.fake.writes), 8)
        self.assertEqual(s.plan(self.fake)[0], [])
    def test_reuse_existing(self):
        self.fake.groups = [copy.deepcopy(s.GROUP)]
        self.fake.props = copy.deepcopy(s.DEFINITIONS[:2])
        self.assertEqual(len(s.plan(self.fake)[0]), 5)
    def test_incompatible_stops_before_writes(self):
        for key, value in [('type','enumeration'), ('fieldType','select'), ('label','wrong'), ('groupName','wrong'), ('hasUniqueValue',True)]:
            with self.subTest(key=key):
                self.fake.props = [dict(s.DEFINITIONS[0], **{key:value})]
                with self.assertRaises(s.SchemaError): s.run(self.fake, True, 'bad')
                self.assertFalse(self.fake.writes)
    def test_readonly_or_archived_stops(self):
        for extra in [{'archived':True}, {'modificationMetadata':{'readOnlyValue':True}}]:
            self.fake.props = [dict(s.DEFINITIONS[0], **extra)]
            with self.assertRaises(s.SchemaError): s.plan(self.fake)
    def test_incompatible_group(self):
        self.fake.groups = [dict(s.GROUP, label='wrong')]
        with self.assertRaises(s.SchemaError): s.plan(self.fake)
    def test_hash_change_stops(self):
        digest = s.plan(self.fake)[1]
        self.fake.groups = [s.GROUP]
        with self.assertRaises(s.SchemaError): s.run(self.fake, True, digest)
        self.assertFalse(self.fake.writes)
    def test_missing_approval(self):
        with self.assertRaises(s.SchemaError): s.run(self.fake, True)
        self.assertFalse(self.fake.writes)
    def test_verification_failure(self):
        self.fake.ignore = True
        with self.assertRaises(s.SchemaError): s.run(self.fake, True, s.plan(self.fake)[1])
    def test_incomplete_response(self):
        for result in [{'results': [], 'paging': {'next':1}}, {}, {'results':[{},{}]}]:
            client = Mock()
            client.request.return_value = result
            with self.assertRaises(s.SchemaError): s.plan(client)
    def test_schema_env_only_and_header(self):
        with patch.dict('os.environ', {'HUBSPOT_SCHEMA_TOKEN':'synthetic-secret'}, clear=True):
            client=s.SchemaClient()
        client.opener=Mock()
        client.opener.open.return_value=io.BytesIO(b'{"results":[]}')
        client.request('GET', s.PROPERTIES)
        req=client.opener.open.call_args.args[0]
        self.assertEqual(req.get_header('Authorization'), 'Bearer synthetic-secret')
        self.assertEqual(req.get_method(), 'GET')
    def test_no_readonly_fallback(self):
        with patch.dict('os.environ', {'HUBSPOT_READONLY_TOKEN':'synthetic-secret'}, clear=True), patch.object(s,'build_opener') as opener:
            with self.assertRaises(s.SchemaError): s.SchemaClient()
            opener.assert_not_called()
    def test_allowlist_and_preview_guard(self):
        with patch.dict('os.environ', {'HUBSPOT_SCHEMA_TOKEN':'synthetic-secret'}): client=s.SchemaClient()
        client.opener=Mock()
        for method,path,body in [('POST',s.PROPERTIES,s.DEFINITIONS[0]), ('DELETE',s.PROPERTIES,None), ('PATCH',s.PROPERTIES,None), ('POST','/crm/v3/objects/companies',{}), ('GET','/crm/v3/objects/contacts',None)]:
            with self.assertRaises(s.SchemaError): client.request(method,path,body)
        client.opener.open.assert_not_called()
    def test_unapproved_payload_blocked(self):
        with patch.dict('os.environ', {'HUBSPOT_SCHEMA_TOKEN':'synthetic-secret'}): client=s.SchemaClient(True)
        with self.assertRaises(s.SchemaError): client.request('POST',s.PROPERTIES,{'name':'other'})
    def test_secret_redacted_and_no_retry(self):
        with patch.dict('os.environ', {'HUBSPOT_SCHEMA_TOKEN':'synthetic-secret'}): client=s.SchemaClient(True)
        client.opener=Mock()
        client.opener.open.side_effect=HTTPError('url',400,'bad',{},io.BytesIO(b'synthetic-secret'))
        with self.assertRaises(s.SchemaError) as err: client.request('POST',s.PROPERTIES,s.DEFINITIONS[0])
        self.assertNotIn('synthetic-secret',str(err.exception))
        self.assertEqual(client.opener.open.call_count,1)
    def test_cli_apply_requires_hash_locally(self):
        with patch('sys.stderr',new=io.StringIO()), patch.object(s,'SchemaClient') as client:
            with self.assertRaises(SystemExit): s.main(['--apply'])
            client.assert_not_called()

if __name__ == '__main__': unittest.main()
