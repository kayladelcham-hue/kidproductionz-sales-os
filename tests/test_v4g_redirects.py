import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from v4g_redirects import policy,registrable
class RedirectTests(unittest.TestCase):
 def test_upgrade(self):self.assertEqual(policy('http://example.com','https://example.com')[1],'')
 def test_www(self):self.assertEqual(policy('https://example.com','https://www.example.com/a')[1],'')
 def test_subdomain(self):self.assertEqual(policy('https://a.example.co.uk','https://b.example.co.uk')[1],'')
 def test_crossdomain(self):self.assertEqual(policy('https://a.com','https://b.com')[1],'CROSS_DOMAIN_UNCORROBORATED')
 def test_private_suffix(self):self.assertNotEqual(registrable('a.github.io'),registrable('b.github.io'))
 def test_auth(self):self.assertEqual(policy('https://example.com','https://example.com/login')[1],'AUTH_OR_TRACKING_DESTINATION')
 def test_social(self):self.assertEqual(policy('https://example.com','https://instagram.com/a')[1],'DISALLOWED_DOMAIN')
 def test_downgrade(self):self.assertEqual(policy('https://example.com','http://example.com')[1],'HTTPS_DOWNGRADE')
if __name__=='__main__':unittest.main()
