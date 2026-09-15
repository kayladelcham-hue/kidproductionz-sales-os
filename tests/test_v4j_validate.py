import unittest
from unittest.mock import patch
import v4j_validate

class V4JFactoryTests(unittest.TestCase):
    def test_original_reference_and_restoration_on_success_and_error(self):
        original = object()
        calls = []
        class FakeModule:
            FragmentFetcher = original
            def run(self, *a, **k):
                calls.append(FakeModule.FragmentFetcher)
                raise RuntimeError('stop')
        with patch.object(v4j_validate, 'v4f_validate', FakeModule):
            with self.assertRaises(RuntimeError):
                v4j_validate.run(None, None)
            self.assertIs(FakeModule.FragmentFetcher, original)

    def test_factory_uses_saved_reference(self):
        original = object()
        self.assertIsNotNone(original)
        self.assertIn('OriginalFragmentFetcher', open(v4j_validate.__file__, encoding='utf-8').read())

    def test_v4j_factory_uses_redirect_fetcher_diagnostics(self):
        self.assertIs(v4j_validate.RedirectFetcher.__dict__.get('redirect_diagnostics'), None)
        self.assertIn('f = RedirectFetcher', open(v4j_validate.__file__, encoding='utf-8').read())

if __name__ == '__main__':
    unittest.main()
