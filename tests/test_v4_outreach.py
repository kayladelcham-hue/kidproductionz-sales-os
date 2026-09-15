import csv,copy,hashlib,json,sys,tempfile,unittest
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from outreach_routing import routing
from outreach_priority import priority
from outreach_queue import queue
from outreach_messaging import messaging,follow_up
from v4_outreach import generate,ROOT

class OutreachTests(unittest.TestCase):
    def setUp(self):
        self.cfg=json.loads((ROOT/'config/outreach_config.json').read_text())
        self.row=dict(lead_id='L1',name='Example',city='Orlando',state='FL',normalized_category='hair salon',category_tier='primary',phone='4075552345',email='',social='',score='85',grade='A / Hot',rating='4.5',reviews='30',queue='qualified')
    def test_call(self): self.assertEqual(routing(self.row,self.cfg)[0],'CALL_FIRST')
    def test_professional_email(self):
        self.row.update(normalized_category='realtor',email='hello@example.com')
        self.assertEqual(routing(self.row,self.cfg)[0],'EMAIL_FIRST')
    def test_social_operator_over_phone(self):
        self.row.update(normalized_category='braider',social='https://instagram.com/example')
        self.assertEqual(routing(self.row,self.cfg)[0],'DM_FIRST')
    def test_missing_contact(self):
        self.row['phone']=''
        self.assertEqual(routing(self.row,self.cfg)[0],'RESEARCH')
    def test_ambiguous(self):
        self.row['email']='a@example.com; b@example.com'
        self.assertEqual(routing(self.row,self.cfg)[0],'RESEARCH')
    def test_conflicting_identity(self):
        self.row['flags']='UNCERTAIN_DUPLICATE'
        self.assertEqual(routing(self.row,self.cfg)[0],'RESEARCH')
    def test_social_home_not_profile(self):
        self.row.update(phone='',social='https://instagram.com')
        self.assertEqual(routing(self.row,self.cfg)[0],'RESEARCH')
    def test_weak_phone_email(self):
        self.row.update(flags='SHARED_PHONE',email='hello@example.com')
        self.assertEqual(routing(self.row,self.cfg)[0],'EMAIL_FIRST')
    def test_deterministic_and_original_score(self):
        before=copy.deepcopy(self.row)
        self.assertEqual(routing(self.row,self.cfg),routing(self.row,self.cfg))
        self.assertEqual(self.row,before)
    def test_priority_p1(self):
        self.row['email']='a@example.com'
        route,_,channels=routing(self.row,self.cfg)
        self.assertEqual(priority(self.row,route,channels,self.cfg)[0],'P1')
        self.assertEqual(priority(self.row,route,channels,self.cfg),priority(self.row,route,channels,self.cfg))
    def test_priority_research(self): self.assertEqual(priority(self.row,'RESEARCH',{},self.cfg)[0],'RESEARCH')
    def test_priority_p3_missing_reputation(self):
        self.row['reviews']=''
        self.assertEqual(priority(self.row,'CALL_FIRST',{'phone':'x','email':'','social':''},self.cfg)[0],'P3')
    def test_generic_no_evidence(self):
        m=messaging({},'EMAIL_FIRST')
        self.assertTrue(m['email_body'].startswith('Hi there,'))
        self.assertNotIn('$',m['email_body'])
    def test_no_fabricated_personalization(self):
        a=messaging(self.row,'DM_FIRST')
        self.row.update(owner='Invented',pain_point='low sales',social_activity='daily posts')
        self.assertEqual(a,messaging(self.row,'DM_FIRST'))
    def test_research_no_message(self): self.assertEqual(messaging(self.row,'RESEARCH')['dm_draft'],'')
    def test_followup_weekend_and_year(self):
        self.assertEqual(follow_up(date(2026,9,11),3),'2026-09-16')
        self.assertEqual(follow_up(date(2026,12,31),1),'2027-01-01')
    def test_followup_invalid(self):
        with self.assertRaises(ValueError): follow_up(date(2026,9,11),0)
    def fixture(self,rows):
        t=tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup)
        root=Path(t.name); source=root/'qualified_leads_run.csv'
        with source.open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
        return source,root/'out'
    def test_output_limits_and_score(self):
        rows=[dict(self.row,lead_id=str(i)) for i in range(15)]
        source,out=self.fixture(rows)
        self.cfg['daily_limits']['CALL_FIRST']=2
        result=generate(source,self.cfg,date(2026,9,14),out)
        self.assertEqual(result['selected'],2);self.assertEqual(result['remaining'],13)
        data=json.loads((Path(result['output_directory'])/'daily_outreach_queue.json').read_text())
        self.assertTrue(all(r['lead_score']=='85' and r['outreach_status']=='NOT_CONTACTED' for r in data))
        self.assertEqual(len({r['lead_id'] for r in data}),2)
        again=generate(source,self.cfg,date(2026,9,14),out)
        self.assertEqual(data,json.loads((Path(again['output_directory'])/'daily_outreach_queue.json').read_text()))
    def test_duplicate_ids_fail(self):
        source,out=self.fixture([self.row,self.row])
        with self.assertRaises(ValueError):generate(source,self.cfg,date(2026,9,14),out)
    def test_queue_priority_first(self):
        rows=[dict(outreach_route='CALL_FIRST',outreach_priority=p,lead_score='70',company_name='x',lead_id=p) for p in ('P3','P1','P2')]
        self.assertEqual([r['lead_id'] for r in queue(rows,self.cfg)],['P1','P2','P3'])
    def test_no_network_imports(self):
        import ast
        allowed={'argparse','collections','csv','datetime','hashlib','json','pathlib','uuid','re','urllib.parse','normalize','crm_normalize','outreach_routing','outreach_priority','outreach_messaging','outreach_queue'}
        for name in ('v4_outreach','outreach_routing','outreach_priority','outreach_messaging','outreach_queue'):
            tree=ast.parse((ROOT/'src'/(name+'.py')).read_text())
            for n in ast.walk(tree):
                if isinstance(n,ast.Import): self.assertTrue(all(a.name in allowed for a in n.names))
                if isinstance(n,ast.ImportFrom): self.assertIn(n.module,allowed)
    def test_proven_modules_unchanged(self):
        manifest=json.loads((ROOT/'tests/v4_regression_manifest.json').read_text())
        for path,digest in manifest.items():self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),digest,path)

if __name__=='__main__':unittest.main()
