import unittest
from v5m_snapshot_diff import diff
class V5M(unittest.TestCase):
 def test_diff_types_and_order(self):
  self.assertEqual(diff({'a':1},{'a':1}),[])
  d=diff({'a':1,'gone':2,'nested':{'x':1},'list':[1]},{'a':2,'nested':{'x':2},'list':[1,3],'new':4})
  self.assertEqual([x['change_type'] for x in d],['CHANGED','REMOVED','ADDED','CHANGED','ADDED'])
  self.assertEqual(d[0]['field_path'],'a')
if __name__=='__main__':unittest.main()
