import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from v4h_audit import classify,matches
class AuditTests(unittest.TestCase):
 def test_missing_is_not_inspectable(self):self.assertEqual(classify('mailto',[],[], '', '')[0],'F')
 def test_promoted(self):self.assertEqual(classify('mailto',['mailto:x'],['x'],'x','')[0],'B')
 def test_withheld_email(self):self.assertEqual(classify('mailto',['mailto:x'],['x'],'','Multiple plausible social findings')[0],'D')
 def test_social_ambiguity(self):self.assertEqual(classify('instagram',['url'],['url'],'','Multiple plausible social findings')[0],'E')
 def test_supporting_evidence(self):self.assertEqual(classify('contact_link',['/contact'],[],'','')[0],'B')
 def test_domain_exact(self):self.assertFalse(matches('instagram','https://instagram.com.evil.test/x'))
 def test_plain_text_not_inferred(self):self.assertFalse(matches('plain_text_email','mailto:hello@example.com'))
if __name__=='__main__':unittest.main()
