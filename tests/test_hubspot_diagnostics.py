"""Offline HTTP-error diagnostics and schema validation regression tests."""
import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit, quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hubspot_client import HubSpotReader, ReadError, redact
from hubspot_snapshot import retrieve, SnapshotError
from check_hubspot import load_config, main
from test_hubspot_v2 import FakeReader, company

class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.cfg = load_config(ROOT / "config/hubspot_matching.json")
        self.cfg["portal_id"] = "12345"
        self.token = "synthetic-secret+/with-space"
        self.reader = HubSpotReader(self.token, self.cfg)
        self.reader.opener = Mock()

    def fail(self, body, status=400, path="/crm/v3/objects/companies", params=None, headers=None):
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.reader.opener.open.side_effect = HTTPError("https://api.hubapi.com" + path, status, "Bad Request",
            headers or {}, io.BytesIO(raw))
        stderr = io.StringIO()
        with patch("sys.stderr", new=stderr):
            with self.assertRaises(ReadError) as caught:
                self.reader.get(path, params)
        return caught.exception, stderr.getvalue()

    def test_400_has_body_message_correlation_and_properties(self):
        exc, printed = self.fail({"message": "Property is invalid", "correlationId": "test-correlation",
                                 "category": "VALIDATION_ERROR"},
                                params={"limit": 100, "archived": "false", "properties": "name,domain"})
        d = exc.diagnostic
        self.assertEqual(d["http_status"], 400)
        self.assertEqual(d["message"], "Property is invalid")
        self.assertEqual(d["correlation_id"], "test-correlation")
        self.assertEqual(d["endpoint"], "https://api.hubapi.com/crm/v3/objects/companies")
        self.assertEqual(d["requested_properties"], ["name", "domain"])
        self.assertIn("Property is invalid", printed)
        self.assertEqual(self.reader.opener.open.call_count, 1)

    def test_schema_error_identifies_schema_endpoint(self):
        exc, _ = self.fail({"message": "Schema request failed"},
                          path="/crm/v3/properties/companies")
        self.assertTrue(exc.diagnostic["endpoint"].endswith("/properties/companies"))
        self.assertEqual(exc.diagnostic["requested_properties"], [])

    def test_correlation_header_fallback(self):
        exc, _ = self.fail({"message": "Bad input"}, headers={"X-HubSpot-Correlation-Id": "header-id"})
        self.assertEqual(exc.diagnostic["correlation_id"], "header-id")

    def test_plain_text_response_preserved(self):
        exc, _ = self.fail(b"Invalid query parameter: after")
        self.assertEqual(exc.diagnostic["response_body"], "Invalid query parameter: after")

    def test_nested_secrets_and_token_echo_redacted(self):
        body = {"message": "Failed " + self.token,
                "context": {"Authorization": "Bearer different-secret", "access_token": "another-secret",
                            "client_secret": "client-secret", "url": "https://example.com?hapikey=api-secret"},
                "encoded": quote(self.token, safe="")}
        exc, printed = self.fail(body)
        exposed = str(exc) + printed + json.dumps(self.reader.diagnostics)
        for secret in (self.token, quote(self.token, safe=""), "different-secret", "another-secret", "client-secret", "api-secret"):
            self.assertNotIn(secret, exposed)
        self.assertIn("[REDACTED]", exposed)

    def test_plain_text_bearer_redacted(self):
        exc, printed = self.fail(b'Authorization: Bearer arbitrary-secret')
        self.assertNotIn("arbitrary-secret", str(exc) + printed)

    def test_response_headers_not_dumped(self):
        exc, printed = self.fail({"message": "Bad input"}, headers={"Set-Cookie": "secret-cookie", "Authorization": "secret-auth"})
        self.assertNotIn("secret-cookie", str(exc) + printed)
        self.assertNotIn("secret-auth", str(exc) + printed)

    def test_request_parameters_roundtrip_and_get_only(self):
        params = {"limit": 100, "archived": "true", "properties": "name,hs_additional_domains,address2", "after": "NTI1Cg%3D%3D"}
        self.reader.opener.open.return_value = io.BytesIO(b'{"results":[]}')
        self.reader.get("/crm/v3/objects/companies", params)
        request = self.reader.opener.open.call_args.args[0]
        parsed = urlsplit(request.full_url)
        self.assertEqual(parsed.path, "/crm/v3/objects/companies")
        self.assertEqual(parse_qs(parsed.query), {k: [str(v)] for k, v in params.items()})
        self.assertEqual(request.get_method(), "GET")
        self.assertIsNone(request.data)

    def test_retryable_failure_is_also_diagnosed(self):
        error = HTTPError("https://api.hubapi.com", 429, "Rate limit", {"Retry-After": "0"}, io.BytesIO(b'{"message":"Rate limit","correlationId":"rate-id"}'))
        self.reader.opener.open.side_effect = [error, io.BytesIO(b'{"results":[]}')]
        with patch("sys.stderr", new=io.StringIO()), patch("hubspot_client.time.sleep"):
            self.assertEqual(self.reader.get("/crm/v3/objects/companies"), {"results": []})
        self.assertEqual(len(self.reader.diagnostics), 1)
        self.assertEqual(self.reader.diagnostics[0]["correlation_id"], "rate-id")

    def test_missing_optional_is_reported_and_never_requested(self):
        reader = FakeReader(self.cfg, [company()])
        original = reader.get
        def get(path, params=None):
            value = original(path, params)
            if params is None:
                value["results"] = [p for p in value["results"] if p["name"] != "hs_additional_domains"]
            return value
        reader.get = get
        snapshot = retrieve(reader, self.cfg)
        self.assertIn("hs_additional_domains", snapshot["missing_optional_properties"])
        self.assertNotIn("hs_additional_domains", snapshot["properties"])
        for path, params in reader.calls:
            if params:
                self.assertNotIn("hs_additional_domains", params["properties"])
        report = snapshot["property_validation"]
        self.assertEqual(next(p for p in report["properties"] if p["configured_name"] == "hs_additional_domains")["action"], "omit_optional")

    def test_missing_required_fails_before_company_get(self):
        reader = FakeReader(self.cfg)
        original = reader.get
        def get(path, params=None):
            value = original(path, params)
            value["results"] = [p for p in value["results"] if p["name"] != "phone"]
            return value
        reader.get = get
        with self.assertRaises(SnapshotError):
            retrieve(reader, self.cfg)
        self.assertEqual(len(reader.calls), 1)

    def test_possible_alternative_reported_not_auto_mapped(self):
        reader = FakeReader(self.cfg)
        original = reader.get
        def get(path, params=None):
            value = original(path, params)
            if params is None:
                for p in value["results"]:
                    if p["name"] == "hs_additional_domains":
                        p["name"] = "additional_domains"
            return value
        reader.get = get
        snapshot = retrieve(reader, self.cfg)
        prop = next(p for p in snapshot["property_validation"]["properties"] if p["configured_name"] == "hs_additional_domains")
        self.assertIn("additional_domains", prop["possible_alternative_names"])
        self.assertNotIn("additional_domains", snapshot["properties"])

    def test_available_additional_domains_included(self):
        snapshot = retrieve(FakeReader(self.cfg), self.cfg)
        self.assertIn("hs_additional_domains", snapshot["properties"])
        self.assertFalse(snapshot["missing_optional_properties"])

    def test_schema_report_included_in_error(self):
        with patch("sys.stderr", new=io.StringIO()):
            self.reader.report_property_validation({"missing_optional_properties": ["hs_additional_domains"]})
        exc, _ = self.fail({"message": "Bad request"})
        self.assertEqual(exc.diagnostic["property_validation"]["missing_optional_properties"], ["hs_additional_domains"])

    def test_cli_saves_redacted_error_no_snapshot_or_classifications(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            cfgfile = root / "config.json"
            cfgfile.write_text(json.dumps(self.cfg))
            source = root / "qualified.csv"
            source.write_text("lead_id,name,score,grade,queue\nL1,Test,75,B,qualified\n")
            schema = {"results": [{"name": p} for p in self.cfg["properties"]]}
            error = HTTPError("https://api.hubapi.com", 400, "Bad Request", {},
                             io.BytesIO(json.dumps({"message": "Rejected " + self.token, "correlationId": "local-test"}).encode()))
            self.reader.opener.open.side_effect = [io.BytesIO(json.dumps(schema).encode()), error]
            with patch("check_hubspot.HubSpotReader.from_environment", return_value=self.reader), patch.dict("os.environ", {self.cfg["token_env"]: self.token}), patch("sys.stderr", new=io.StringIO()):
                code = main([str(source), "--live", "--config", str(cfgfile), "--output-root", str(root)])
            self.assertEqual(code, 1)
            self.assertFalse((root / "crm_checks").exists())
            self.assertFalse((root / "hubspot_snapshots").exists())
            logs = list((root / "logs").glob("hubspot_read_error_*.json"))
            self.assertEqual(len(logs), 1)
            saved = logs[0].read_text()
            self.assertNotIn(self.token, saved)
            self.assertIn("local-test", saved)
            self.assertIn("property_validation", saved)

if __name__ == "__main__":
    unittest.main()
