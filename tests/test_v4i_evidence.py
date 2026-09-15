import unittest,tempfile,json,io,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from v4i_evidence import capture,path_for,ObservedResponse,MAX_OUTPUT
class EvidenceTests(unittest.TestCase):
 def save(self,html,meta=None):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
  return capture(t.name,'L1','https://example.com','https://example.com',html.encode(),meta or {})
 def test_visible_sanitized(self):
  _,e=self.save('<p>Hello   world</p><script>hidden key</script><style>private</style>');self.assertEqual(e['visible_text'],'Hello world')
 def test_bound(self):
  p,e=self.save('x'*200000);self.assertLessEqual(p.stat().st_size,MAX_OUTPUT);self.assertTrue(e['evidence_text_truncated'])
 def test_links(self):
  _,e=self.save('<a href="https://linkedin.com/company/a">a</a><a href="/contact">c</a>');self.assertEqual([l['link_type'] for l in e['links']],['linkedin','contact_link'])
 def test_email(self):
  _,e=self.save('hello@example.com <a href="mailto:hello@example.com">email</a>');self.assertEqual(len(e['emails']),2)
 def test_secrets(self):
  _,e=self.save('Authorization: Bearer abc <a href="/contact?token=secret">c</a>',{'headers':{'Authorization':'synthetic-header-value'}});self.assertNotIn('secret',json.dumps(e));self.assertNotIn('synthetic-header-value',json.dumps(e));self.assertNotIn('abc',json.dumps(e))
 def test_truncation(self):
  _,e=self.save('test',{'truncation':True});self.assertTrue(e['truncation']);self.assertEqual(e['inspected_byte_count'],4)
 def test_path(self):self.assertEqual(path_for('out','../lead','https://e.com'),path_for('out','../lead','https://e.com'))
 def test_observer_no_extra_read(self):
  s=io.BytesIO(b'abcdef');seen=[];o=ObservedResponse(s,lambda b,t:seen.append(b));self.assertEqual(o.read(2),b'ab');o.close();self.assertEqual(seen,[b'ab'])
 def test_callback_failure_not_behavior(self):
  o=ObservedResponse(io.BytesIO(b'a'),lambda b,t:1/0);o.read(1);o.close();self.assertTrue(o.capture_failed)
if __name__=='__main__':unittest.main()
