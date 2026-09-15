import unittest,json,hashlib,tempfile,csv,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from enrichment_pipeline import enrich,adapt
from enrichment_sources import FixtureProvider,PublicProvider,SourceUnavailable
from enrichment_email import emails
from enrichment_social import socials
from v4b_enrich import ROOT,run
class EnrichmentTests(unittest.TestCase):
    def setUp(self):
        self.cfg=json.loads((ROOT/'config/enrichment_config.json').read_text())
        self.row=dict(lead_id='1',queue='qualified',name='Example Salon',city='Orlando',state='FL',phone='4075552345',website='https://example.com',email='',social='',score='75')
        self.html='Example Salon Orlando 407-555-2345 <a href="mailto:info@example.com">Email</a><a href="https://instagram.com/example">Instagram</a>'
    def enrich(self,html=None):return enrich(self.row,FixtureProvider({'https://example.com':self.html if html is None else html}),self.cfg,'run','time')
    def test_exact_email(self):self.assertEqual(self.enrich()['enriched_email'],'info@example.com')
    def test_exact_instagram(self):self.assertEqual(self.enrich()['enriched_social'],'https://instagram.com/example')
    def test_no_guessed_email(self):self.assertEqual(emails(['https://example.com/contact']),[])
    def test_wrong_city(self):self.assertEqual(self.enrich(self.html.replace('Orlando','Atlanta'))['enrichment_status'],'REVIEW')
    def test_shared_platform(self):
        self.row['website']='https://salonlofts.com/example'
        p=FixtureProvider({self.row['website']:self.html})
        self.assertEqual(enrich(self.row,p,self.cfg,'r','t')['enrichment_status'],'REVIEW')
    def test_shared_phone(self):
        self.row['flags']='SHARED_PHONE'
        self.assertEqual(self.enrich()['enrichment_status'],'REVIEW')
    def test_conflicting_existing(self):
        self.row['email']='hello@different.com'
        self.assertEqual(self.enrich()['enriched_email'],'')
        self.assertEqual(self.enrich()['enrichment_status'],'REVIEW')
    def test_conflicting_social(self):
        self.assertEqual(self.enrich(self.html+'<a href="https://instagram.com/other">Other</a>')['enrichment_status'],'REVIEW')
    def test_provenance(self):
        ev=json.loads(self.enrich()['enrichment_evidence'])[0]
        self.assertEqual(ev['source_url'],'https://example.com');self.assertEqual(ev['confidence'],'HIGH');self.assertEqual(ev['run_id'],'run')
    def test_preservation_and_adapter(self):
        out=self.enrich()
        for k,v in self.row.items():self.assertEqual(out[k],v)
        self.assertEqual(adapt(out)['email'],'info@example.com')
        self.assertEqual(adapt(out)['original_email'],'')
    def test_low_not_adapted(self):
        out=self.enrich();out['email_confidence']='LOW'
        self.assertEqual(adapt(out)['email'],'')
    def test_unsupported_blank(self):
        out=self.enrich('Example Salon Orlando 407-555-2345')
        self.assertEqual(out['enriched_email'],'');self.assertEqual(out['contact_name'],'')
    def test_deterministic(self):self.assertEqual(self.enrich(),self.enrich())
    def test_error_isolated(self):
        p=FixtureProvider({'https://example.com':RuntimeError('synthetic')})
        self.assertEqual(enrich(self.row,p,self.cfg,'r','t')['enrichment_status'],'ERROR')
    def test_inaccessible_review(self):
        p=FixtureProvider({})
        self.assertEqual(enrich(self.row,p,self.cfg,'r','t')['enrichment_status'],'REVIEW')
    def test_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            provider=PublicProvider(self.cfg,tmp)
            with patch.object(provider,'_get',side_effect=['User-agent: *\nAllow: /',self.html]) as get:
                self.assertEqual(provider.fetch('https://example.com'),provider.fetch('https://example.com'))
                self.assertEqual(get.call_count,2)
    def test_no_reenrichment(self):
        with self.assertRaises(ValueError):enrich(self.enrich(),FixtureProvider({}),self.cfg,'r','t')
    def test_named_email_review(self):self.assertEqual(self.enrich(self.html.replace('info@','jane@'))['enrichment_status'],'REVIEW')
    def test_regression(self):
        for path,digest in json.loads((ROOT/'tests/v4b_regression_manifest.json').read_text()).items():self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),digest,path)
    def test_pilot_outputs_and_v4a(self):
        from v4_outreach import generate
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'input.csv'
            with source.open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(self.row));w.writeheader();w.writerow(self.row)
            result=run(source,self.cfg,FixtureProvider({'https://example.com':self.html}),root/'out')
            from datetime import date
            routed=generate(Path(result['output_directory'])/'v4a_input.csv',json.loads((ROOT/'config/outreach_config.json').read_text()),date(2026,9,14),root/'queue')
            self.assertEqual(routed['total_routed'],1);self.assertEqual(result['hubspot_writes'],0);self.assertEqual(result['outbound_communications'],0)
    def test_ten_cap(self):
        with self.assertRaises(ValueError):run(Path('unused'),self.cfg,FixtureProvider({}),Path('unused'),11)
if __name__=='__main__':unittest.main()
