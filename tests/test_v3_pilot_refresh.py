import copy
import json
import unittest
from unittest.mock import Mock, patch
import test_v3_controlled as fixtures
from test_hubspot_v2 import FakeReader
from hubspot_snapshot import retrieve
import v3_pilot_refresh as p

class PilotRefreshTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.ControlledImportTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        f=self.fixture
        self.original=f.plan(12)
        self.schema=[{'name':n,'type':t,'fieldType':ft} for n,(t,ft) in p.METADATA.items()]
        self.schema += list(f.schema.values())
        self.reader=Mock()
        self.reader.get.return_value={'results':self.schema}
        self.snapshot=retrieve(FakeReader(f.match),f.match)
    def run_refresh(self, statuses=None):
        f=self.fixture
        results=[{'crm_status':s} for s in (statuses or ['NEW']*10)]
        with patch.object(p,'retrieve',return_value=self.snapshot), patch.object(p,'classify',side_effect=results):
            return p.refresh(self.original,f.cfg,f.match,self.reader,f.root)
    def test_all_new_metadata_and_unapproved(self):
        result=self.run_refresh()
        self.assertEqual(result['proposed'],10)
        self.assertEqual(result['writes'],0)
        self.assertFalse(json.loads(p.Path(result['approval_template']).read_text())['approved'])
        plan=json.loads(p.Path(result['plan']).read_text())
        self.assertTrue(all(set(p.METADATA)<=set(i['request']['properties']) for i in plan['items']))
    def test_skips_no_replacement(self):
        result=self.run_refresh(['EXISTING','REVIEW']+['NEW']*8)
        plan=json.loads(p.Path(result['plan']).read_text())
        self.assertEqual([i['lead_id'] for i in plan['items']],[i['lead_id'] for i in self.original['items'][2:]])
        self.assertEqual(result['skipped'],2)
    def test_all_skipped_empty_plan(self):
        result=self.run_refresh(['REVIEW']*10)
        self.assertEqual(result['proposed'],0)
    def test_incomplete_snapshot_no_output(self):
        self.snapshot['status']='incomplete'
        with self.assertRaises(Exception): self.run_refresh()
        self.assertFalse((self.fixture.root/'v3_imports').exists())
    def test_missing_metadata_blocks(self):
        self.reader.get.return_value={'results':[]}
        with self.assertRaises(ValueError): self.run_refresh()
    def test_incompatible_metadata_blocks(self):
        self.schema[0]['fieldType']='textarea'
        with self.assertRaises(ValueError): self.run_refresh()
    def test_enabled_blocks(self):
        self.fixture.cfg['enabled']=True
        with self.assertRaises(ValueError): self.run_refresh()
        self.reader.get.assert_not_called()
    def test_cap_changed_blocks(self):
        self.fixture.cfg['pilot_limit']=11
        with self.assertRaises(ValueError): self.run_refresh()
    def test_unique_outputs(self):
        a=self.run_refresh(); b=self.run_refresh()
        self.assertNotEqual(a['plan'],b['plan'])
        self.assertTrue(p.Path(a['plan']).exists())
    def test_readonly_transport_only(self):
        import inspect
        source=inspect.getsource(p)
        self.assertNotIn('CompanyCreator',source)
        self.assertNotIn('SchemaClient',source)
        self.assertNotIn('.request(',source)
        self.run_refresh()
        self.reader.get.assert_called_once_with('/crm/v3/properties/companies')

if __name__=='__main__': unittest.main()

