import unittest
from v4k_drift_audit import run

class V4KTests(unittest.TestCase):
    def test_audit_entrypoint_exists_and_is_offline(self):
        self.assertTrue(callable(run))
        self.assertIn('OFFLINE_ARTIFACT_COMPARISON', open(run.__code__.co_filename, encoding='utf-8').read())

if __name__ == '__main__': unittest.main()
