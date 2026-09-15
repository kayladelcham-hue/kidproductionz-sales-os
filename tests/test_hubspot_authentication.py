"""Service Key authentication tests: synthetic secrets and mocked HTTP only."""
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hubspot_client import HubSpotReader, ReadError
from hubspot_snapshot import retrieve
from check_hubspot import load_config, main
from test_hubspot_v2 import FakeReader, company

class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.cfg = load_config(ROOT / "config/hubspot_matching.json")
        self.cfg["portal_id"] = "12345"
        self.cfg["token_env"] = "SYNTHETIC_CONFIGURED_KEY"
        self.secret = "synthetic-service-key-only-for-local-tests"

    def test_configured_variable_is_read(self):
        with patch.dict("os.environ", {"SYNTHETIC_CONFIGURED_KEY": self.secret}, clear=True), patch("sys.stderr", new=io.StringIO()):
            reader = HubSpotReader.from_environment(self.cfg)
            reader.opener = Mock()
            reader.opener.open.return_value = io.BytesIO(b'{"results":[]}')
            reader.get("/crm/v3/properties/companies")
            request = reader.opener.open.call_args.args[0]
            self.assertEqual(request.get_header("Authorization"), "Bearer " + self.secret)

    def test_does_not_fall_back_to_other_environment_variable(self):
        with patch.dict("os.environ", {"HUBSPOT_READONLY_TOKEN": self.secret}, clear=True), patch("hubspot_client.build_opener") as build:
            with self.assertRaises(ReadError):
                HubSpotReader.from_environment(self.cfg)
            build.assert_not_called()

    def test_missing_credentials_fail_before_http_setup(self):
        with patch.dict("os.environ", {}, clear=True), patch("hubspot_client.build_opener") as build:
            with self.assertRaises(ReadError):
                HubSpotReader.from_environment(self.cfg)
            build.assert_not_called()

    def test_blank_credentials_fail_before_http_setup(self):
        with patch.dict("os.environ", {"SYNTHETIC_CONFIGURED_KEY": " \t "}, clear=True), patch("hubspot_client.build_opener") as build:
            with self.assertRaises(ReadError):
                HubSpotReader.from_environment(self.cfg)
            build.assert_not_called()

    def test_malformed_credentials_fail_without_echo(self):
        for value in ("Bearer " + self.secret, '"' + self.secret + '"', self.secret + "\r\nInjected: yes"):
            with self.subTest(kind="malformed"), patch("hubspot_client.build_opener") as build:
                with self.assertRaises(ReadError) as exc:
                    HubSpotReader(value, self.cfg)
                self.assertNotIn(self.secret, str(exc.exception))
                build.assert_not_called()

    def test_outer_whitespace_trimmed_before_header(self):
        with patch("sys.stderr", new=io.StringIO()):
            reader = HubSpotReader(" \t" + self.secret + "\n", self.cfg)
            reader.opener = Mock()
            reader.opener.open.return_value = io.BytesIO(b'{"results":[]}')
            reader.get("/crm/v3/objects/companies")
            self.assertEqual(reader.opener.open.call_args.args[0].get_header("Authorization"), "Bearer " + self.secret)

    def test_header_on_schema_active_archived_and_all_pages(self):
        reader = HubSpotReader(self.secret, self.cfg)
        source = FakeReader(self.cfg, [company(), company("2")], [company("3", archived=True)])
        requests = []
        def respond(request, timeout=None):
            requests.append(request)
            parsed = urlsplit(request.full_url)
            params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
            return io.BytesIO(json.dumps(source.get(parsed.path, params or None)).encode())
        reader.opener = Mock()
        reader.opener.open.side_effect = respond
        stderr = io.StringIO()
        with patch("sys.stderr", new=stderr):
            snapshot = retrieve(reader, self.cfg)
        self.assertEqual(len(snapshot["records"]), 3)
        self.assertEqual(len(requests), 4)
        for request in requests:
            self.assertEqual(request.get_header("Authorization"), "Bearer " + self.secret)
            self.assertEqual(request.get_method(), "GET")
            self.assertIsNone(request.data)
            self.assertNotIn(self.secret, request.full_url)
        self.assertNotIn(self.secret, stderr.getvalue())
        self.assertIn('"authorization_header_present": true', stderr.getvalue())

    def test_header_attached_on_retry(self):
        reader = HubSpotReader(self.secret, self.cfg)
        reader.opener = Mock()
        reader.opener.open.side_effect = [
            HTTPError("https://api.hubapi.com", 429, "Rate limited", {"Retry-After":"0"}, io.BytesIO(b'{"message":"rate limited"}')),
            io.BytesIO(b'{"results":[]}')]
        with patch("sys.stderr", new=io.StringIO()), patch("hubspot_client.time.sleep"):
            reader.get("/crm/v3/objects/companies")
        self.assertEqual(reader.opener.open.call_count, 2)
        for call in reader.opener.open.call_args_list:
            self.assertEqual(call.args[0].get_header("Authorization"), "Bearer " + self.secret)

    def test_401_diagnostic_header_presence_without_secret(self):
        reader = HubSpotReader(self.secret, self.cfg)
        reader.opener = Mock()
        body = {"category":"INVALID_AUTHENTICATION","message":"Authentication credentials not found. " + self.secret,
                "correlationId":"synthetic-correlation","Authorization":"Bearer " + self.secret}
        reader.opener.open.side_effect = HTTPError("https://api.hubapi.com",401,"Unauthorized",{},io.BytesIO(json.dumps(body).encode()))
        stderr = io.StringIO()
        with patch("sys.stderr", new=stderr):
            with self.assertRaises(ReadError) as caught:
                reader.get("/crm/v3/properties/companies")
        self.assertIs(caught.exception.diagnostic["authorization_header_present"], True)
        self.assertNotIn(self.secret, stderr.getvalue() + str(caught.exception) + json.dumps(reader.diagnostics))
        self.assertEqual(reader.opener.open.call_count, 1)

    def test_missing_constructed_header_stops_before_transport(self):
        reader = HubSpotReader(self.secret, self.cfg)
        reader.opener = Mock()
        with patch("hubspot_client.Request") as request:
            request.return_value.get_header.return_value = None
            with self.assertRaises(ReadError):
                reader.get("/crm/v3/objects/companies")
        reader.opener.open.assert_not_called()

    def test_read_only_allowlist_unchanged(self):
        self.assertEqual(HubSpotReader.PATHS, {"/crm/v3/properties/companies", "/crm/v3/objects/companies"})
        reader = HubSpotReader(self.secret, self.cfg)
        reader.opener = Mock()
        for path in ("/crm/v3/objects/companies/123", "/crm/v3/objects/companies/batch/create",
                     "/crm/v3/objects/companies/123/associations", "/crm/v3/objects/contacts"):
            with self.assertRaises(ReadError):
                reader.get(path)
        reader.opener.open.assert_not_called()
        for method in ("post", "put", "patch", "delete"):
            self.assertFalse(hasattr(reader, method))

    def test_cli_missing_credentials_fails_before_any_http(self):
        with patch.dict("os.environ", {}, clear=True), patch("check_hubspot.load_config", return_value=self.cfg), \
             patch("check_hubspot.read_qualified", return_value=([], [])), \
             patch("hubspot_client.build_opener") as build, patch("sys.stderr", new=io.StringIO()):
            result = main(["synthetic.csv", "--live"])
        self.assertEqual(result, 1)
        build.assert_not_called()

if __name__ == "__main__":
    unittest.main()
