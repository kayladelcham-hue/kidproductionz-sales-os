import json
import unittest
from unittest.mock import Mock, patch
import test_v3_controlled as fixtures
from test_hubspot_v2 import FakeReader
from hubspot_snapshot import retrieve, digest
import v3_remainder_refresh as b

class RemainderTests(unittest.TestCase):
    def setUp(self):
        f=fixtures.ControlledImportTests(); f.setUp()
        self.addCleanup(f.doCleanups); self.f=f
        self.summary=f.source(75)
        summary, groups=b.load_run(self.summary)
        self.ordered=sorted(groups['NEW'],key=lambda r:r['lead_id'])
        folder=f.root/'v3_imports'; folder.mkdir()
        self.journal=folder/'import_journal.jsonl'
        self.events=[{'status':'CREATED','source_key':digest([summary['input_sha256'],r['lead_id']]),'hubspot_company_id':str(i+1)} for i,r in enumerate(self.ordered[:10])]
        self.journal.write_text('\n'.join(json.dumps(e) for e in self.events))
        self.reader=Mock()
        self.reader.get.return_value={'results':list(f.schema.values())+[{'name':n,'type':t,'fieldType':ft} for n,(t,ft) in b.METADATA.items()]}
        self.snapshot=retrieve(FakeReader(f.match),f.match)
    def run_batch(self,statuses=None):
        with patch.object(b,'retrieve',return_value=self.snapshot),patch.object(b,'classify',side_effect=[{'crm_status':s} for s in (statuses or ['NEW']*65)]) as classify:
            result=b.refresh(self.summary,self.f.cfg,self.f.match,self.reader,self.f.root)
            self.assertEqual(classify.call_count,65)
            self.assertEqual(len({str(call.args[0]) for call in classify.call_args_list}),65)
            return result
    def test_excludes_pilot_caps_fifty_metadata(self):
        result=self.run_batch()
        plan=json.loads(b.Path(result['plan']).read_text())
        self.assertEqual([i['lead_id'] for i in plan['items']],[r['lead_id'] for r in self.ordered[10:]])
        self.assertTrue(all(set(b.METADATA)<=set(i['request']['properties']) for i in plan['items']))
        self.assertFalse(json.loads(b.Path(result['approval_template']).read_text())['approved'])
        self.assertEqual(self.f.cfg['pilot_limit'],10)
        self.assertFalse(self.f.cfg['enabled'])
        self.assertEqual(result['writes'],0)
    def test_skips_without_replacement(self):
        result=self.run_batch(['EXISTING','REVIEW']+['NEW']*63)
        self.assertEqual(result['proposed'],63)
        self.assertEqual(result['skipped'],2)
    def test_all_skipped(self):
        self.assertEqual(self.run_batch(['REVIEW']*65)['proposed'],0)
    def test_uncertain_stops_before_reads(self):
        with self.journal.open('a') as f: f.write('\n'+json.dumps({'status':'ATTEMPT','source_key':'unknown'}))
        with self.assertRaises(ValueError): self.run_batch()
        self.reader.get.assert_not_called()
    def test_missing_journal_blocks(self):
        self.journal.unlink()
        with self.assertRaises(FileNotFoundError): self.run_batch()
    def test_incomplete_snapshot_blocks(self):
        self.snapshot['status']='incomplete'
        with self.assertRaises(Exception): self.run_batch()
        self.assertFalse((self.f.root/'v3_imports'/'remainder_refreshes').exists())
    def test_missing_metadata_blocks(self):
        self.reader.get.return_value={'results':[]}
        with self.assertRaises(ValueError): self.run_batch()
    def test_enabled_blocks(self):
        self.f.cfg['enabled']=True
        with self.assertRaises(ValueError): self.run_batch()
        self.reader.get.assert_not_called()

    def test_every_attempt_is_excluded_even_skip_history(self):
        summary,_=b.load_run(self.summary)
        key=digest([summary['input_sha256'],self.ordered[10]['lead_id']])
        with self.journal.open('a') as f:
            f.write('\n'+json.dumps({'status':'SKIP_PREVIOUS_ATTEMPT','source_key':key}))
        with patch.object(b,'retrieve',return_value=self.snapshot), patch.object(b,'classify',return_value={'crm_status':'NEW'}) as matcher:
            result=b.refresh(self.summary,self.f.cfg,self.f.match,self.reader,self.f.root)
        self.assertEqual(matcher.call_count,64)
        self.assertEqual(result['total_previously_attempted_lead_ids'],11)
    def test_rules_unchanged(self):
        import hashlib
        root=b.ROOT
        expected={'src/crm_match.py':'84b8eb398cab8a0ea3e99db7edb73aa644d1167d6a4adeda280f8bca00332e4a',
                  'src/crm_normalize.py':'13bc7fc02e3f96171b847b6acb8b75449d300c2eac98d3cf0bf99515cf5af290',
                  'config/ideal_client_profile.json':'ac69c479c9f9cd55530a34b7ca4ec937d436b8bbb8096f2d79abe29ec87e63e2',
                  'config/hubspot_matching.json':'d51ccda624dc6836ac06fafeaeb7ddcbb9a910407dc0ea0191dfa64d42754585'}
        for name, checksum in expected.items():
            self.assertEqual(hashlib.sha256((root/name).read_bytes()).hexdigest(),checksum)
    def test_transport_is_get_only(self):
        import inspect
        text=inspect.getsource(b)
        self.assertNotIn('CompanyCreator',text)
        self.assertNotIn('SchemaClient',text)
        self.assertNotIn('.post(',text)
        self.assertEqual(b.HubSpotReader.__module__, 'hubspot_client')
    def test_lock_blocks_before_network(self):
        (self.f.root/'v3_imports'/'execution.lock').touch()
        with self.assertRaises(ValueError): self.run_batch()
        self.reader.get.assert_not_called()

if __name__=='__main__': unittest.main()
