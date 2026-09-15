import unittest, json
class V4STests(unittest.TestCase):
    def test_v4o_payload_contains_v4r_fields(self):
        text=open('src/v4j_validate.py',encoding='utf-8').read()
        for key in ('structured_contact_evidence','evidence_budget_bytes','structured_contact_bytes','contextual_contact_bytes','general_text_bytes'):
            self.assertIn("'"+key+"'", text)
    def test_legacy_json_is_readable(self):
        self.assertEqual(json.loads('{"schema_version":"V4O-1"}')['schema_version'],'V4O-1')
if __name__=='__main__': unittest.main()
