import unittest,sys,io,ssl,socket
from pathlib import Path
from unittest.mock import Mock,patch
from urllib.error import HTTPError,URLError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from v4d_verification import *
class HardeningTests(unittest.TestCase):
 def test_directory_even_known(self):self.assertEqual(source_type('https://trustanalytica.org/a','https://trustanalytica.org'),'BUSINESS_DIRECTORY')
 def test_official(self):self.assertEqual(source_type('https://salonamoura.com/resume','http://www.salonamoura.com'),'OFFICIAL_WEBSITE')
 def test_unknown(self):self.assertEqual(source_type('https://unknown.com','https://known.com'),'OTHER_PUBLIC_SOURCE')
 def test_platforms(self):
  for d,t in [('booksy.com','BOOKING_PLATFORM'),('instagram.com','INSTAGRAM'),('facebook.com','FACEBOOK'),('tiktok.com','TIKTOK')]:self.assertEqual(source_type('https://'+d+'/a',''),t)
 def test_fallback_once(self):
  f=Mock();f.fetch.side_effect=[FetchFailure('HTTP_404','https://example.com/deep'),'<html>']
  r=check_candidate('https://example.com/deep','https://example.com',f)
  self.assertTrue(r['fallback_succeeded']);self.assertEqual(f.fetch.call_count,2);self.assertEqual(f.fetch.call_args.args[0],'https://example.com/')
 def test_no_bypass(self):
  for code,stage in [('HTTP_403','page'),('ROBOTS_BLOCKED','page'),('REDIRECT_BLOCKED','robots')]:
   f=Mock();f.fetch.side_effect=FetchFailure(code,'https://example.com/deep',stage)
   self.assertFalse(check_candidate('https://example.com/deep','https://example.com',f)['fallback_attempted']);self.assertEqual(f.fetch.call_count,1)
 def test_directory_no_fetch(self):
  f=Mock();check_candidate('https://trustanalytica.org/a','https://example.com',f);f.fetch.assert_not_called()
 def test_structured_errors(self):
  cfg=dict(max_requests=20,pace_seconds=0,timeout_seconds=1,max_bytes=1000,user_agent='test')
  f=SafeFetcher(cfg);f.opener=Mock()
  errors=[(HTTPError('u',403,'x',{},None),'HTTP_403'),(HTTPError('u',404,'x',{},None),'HTTP_404'),(HTTPError('u',429,'x',{},None),'HTTP_429'),(HTTPError('u',301,'x',{},None),'REDIRECT_BLOCKED'),(TimeoutError(),'TIMEOUT'),(ssl.SSLError(),'TLS_ERROR'),(URLError('x'),'CONNECTION_ERROR'),(ValueError(),'OTHER_FETCH_ERROR')]
  with patch('socket.getaddrinfo',return_value=[(None,None,None,None,('8.8.8.8',443))]):
   for error,code in errors:
    f.opener.open.side_effect=error
    with self.assertRaises(FetchFailure) as e:f._get('https://example.com','page')
    self.assertEqual(e.exception.detail['code'],code)
 def test_budget(self):
  f=SafeFetcher(dict(max_requests=0))
  with patch('socket.getaddrinfo',return_value=[(None,None,None,None,('8.8.8.8',443))]):
   with self.assertRaises(FetchFailure) as e:f._get('https://example.com','page')
   self.assertEqual(e.exception.detail['code'],'REQUEST_BUDGET_EXHAUSTED')
if __name__=='__main__':unittest.main()
