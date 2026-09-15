import unittest
from pathlib import Path
from v5a_config import load
class V5A(unittest.TestCase):
 def setUp(self): self.root=Path(__file__).parents[1]
 def test_default_and_overrides(self):
  self.assertEqual(load(self.root)['scoring']['qualification_threshold'],65)
  self.assertEqual(load(self.root,'orlando_beauty')['market']['active'],'orlando')
  self.assertEqual(load(self.root,'atlanta_beauty')['market']['active'],'atlanta')
 def test_unknown_rejected(self):
  self.assertRaises(FileNotFoundError,load,self.root,'missing')
if __name__=='__main__': unittest.main()
