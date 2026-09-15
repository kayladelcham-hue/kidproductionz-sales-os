"""V2 tests: all HubSpot responses are local fakes; no live network access."""
import copy
import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from check_hubspot import load_config, compare_snapshot, main
from hubspot_client import HubSpotReader, ReadError, NoRedirect
from hubspot_snapshot import retrieve, validate, digest, SnapshotError
from crm_normalize import identity
from crm_match import CompanyIndex, classify

def business(**changes):
    row = {"name": "Orchid Hair Studio", "website": "https://orchid.example",
           "phone": "4075550123", "address": "123 Example Street", "city": "Orlando",
           "state": "FL", "country": "US"}
    row.update(changes)
    return row

def company(cid="1", archived=False, **changes):
    return {"id": cid, "properties": business(**changes), "archived": archived,
            "updatedAt": "2026-09-01T00:00:00Z"}

class FakeReader:
    def __init__(self, cfg, active=None, archived=None):
        self.cfg = cfg
        self.active = active or []
        self.archived = archived or []
        self.calls = []
    def get(self, path, params=None):
        self.calls.append((path, params))
        if path.endswith("properties/companies"):
            return {"results": [{"name": p} for p in self.cfg["properties"]]}
        records = self.archived if params["archived"] == "true" else self.active
        start = int(params.get("after", 0))
        # One record per fake page ensures pagination is exercised.
        result = {"results": records[start:start+1]}
        if start+1 < len(records):
            result["paging"] = {"next": {"after": str(start+1)}}
        return result

class HubSpotV2Tests(unittest.TestCase):
    def setUp(self):
        self.cfg = load_config(ROOT / "config/hubspot_matching.json")
        self.cfg["portal_id"] = "12345"

    def match(self, lead=None, records=None):
        return classify(identity(lead or business(), self.cfg),
                        CompanyIndex(records or [], self.cfg), self.cfg)

    def snapshot(self, records=None, archived=None):
        return retrieve(FakeReader(self.cfg, records, archived), self.cfg)

    def test_exact_name_and_address_existing(self):
        r = self.match(records=[company()])
        self.assertEqual(r["crm_status"], "EXISTING")
        self.assertEqual(r["matched_hubspot_id"], "1")
        self.assertEqual(r["match_confidence"], 95)

    def test_domain_phone_and_name_existing_without_address(self):
        r = self.match(business(address="", city=""), [company(address="", city="")])
        self.assertEqual(r["crm_status"], "EXISTING")

    def test_domain_name_city_existing(self):
        r = self.match(business(address="", phone=""), [company(address="", phone="")])
        self.assertEqual(r["match_confidence"], 90)
        self.assertEqual(r["crm_status"], "EXISTING")

    def test_fuzzy_phone_address_existing(self):
        r = self.match(business(website=""), [company(name="Orchid Hair Studios", website="")])
        self.assertEqual(r["crm_status"], "EXISTING")
        self.assertEqual(r["match_confidence"], 90)

    def test_fuzzy_name_alone_never_existing(self):
        r = self.match(business(address="", city="", website=""),
                       [company(name="Orchid Hair Studios", phone="3215550199", website="", address="", city="")])
        self.assertEqual(r["crm_status"], "REVIEW")
        self.assertEqual(r["match_confidence"], 40)

    def test_domain_only_review(self):
        r = self.match(business(name="Different Creative Business", phone="", address="", city=""), [company()])
        self.assertEqual(r["crm_status"], "REVIEW")
        self.assertEqual(r["match_confidence"], 70)

    def test_shared_phone_only_review(self):
        r = self.match(business(name="Distinct Business", website="", address="", city=""), [company(), company("2", name="Another Name")])
        self.assertEqual(r["crm_status"], "REVIEW")
        self.assertEqual(r["match_confidence"], 55)

    def test_shared_domain_alone_never_existing(self):
        r = self.match(business(name="Different Brand", phone="", address="", city=""),
                       [company(), company("2", name="Other Location", address="456 Example St")])
        self.assertNotEqual(r["crm_status"], "EXISTING")

    def test_two_confident_companies_review(self):
        r = self.match(records=[company(), company("2")])
        self.assertEqual(r["crm_status"], "REVIEW")
        self.assertIn("MULTIPLE_CREDIBLE_COMPANIES", r["review_reason_crm"])
        self.assertEqual(r["matched_hubspot_id"], "")
        self.assertEqual(r["candidate_hubspot_ids"], "1; 2")

    def test_archived_match_review(self):
        r = self.match(records=[company(archived=True)])
        self.assertEqual(r["crm_status"], "REVIEW")
        self.assertIn("ARCHIVED_MATCH", r["review_reason_crm"])

    def test_active_and_archived_match_review(self):
        r = self.match(records=[company(), company("2", archived=True)])
        self.assertIn("ARCHIVED_MATCH", r["review_reason_crm"])

    def test_different_location_brand_review(self):
        r = self.match(records=[company(address="456 Other Road")])
        self.assertEqual(r["crm_status"], "REVIEW")
        self.assertIn("POSSIBLE_RELATED_LOCATION", r["review_reason_crm"])

    def test_distinct_suite_review(self):
        r = self.match(business(address="123 Example St Suite 1"),
                       [company(address="123 Example Street", address2="Suite 2")])
        self.assertEqual(r["crm_status"], "REVIEW")

    def test_missing_suite_review(self):
        r = self.match(business(address="123 Example St Suite 1"), [company()])
        self.assertIn("SUITE_INFORMATION_INCOMPLETE", r["review_reason_crm"])

    def test_street_state_country_normalization(self):
        r = self.match(business(address="123 Example St", state="Florida", country="United States"), [company()])
        self.assertEqual(r["crm_status"], "EXISTING")

    def test_tenant_operator_not_existing(self):
        r = self.match(business(name="Kayla Beauty", website="https://salonlofts.com/kayla"),
                       [company(name="Salon Lofts", website="https://salonlofts.com/salons/orlando")])
        self.assertEqual(r["crm_status"], "REVIEW")
        self.assertIn("PLATFORM_TENANT_OPERATOR_CONFLICT", r["conflicting_evidence"])

    def test_unrelated_tenants_shared_platform_not_match(self):
        r = self.match(business(name="Kayla Beauty", website="https://salonlofts.com/kayla"),
                       [company(name="Other Stylist", website="https://salonlofts.com/other", phone="3215550199", address="456 Other Rd")])
        self.assertEqual(r["crm_status"], "NEW")

    def test_business_url_paths_preserved(self):
        n = identity(business(website="https://www.salonlofts.com/kayla"), self.cfg)
        self.assertIn("https://salonlofts.com/kayla", n["urls"])

    def test_additional_domain_match(self):
        r = self.match(business(address="", phone=""),
                       [company(website="https://new.example", hs_additional_domains="old.example;orchid.example", address="", phone="")])
        self.assertEqual(r["crm_status"], "EXISTING")

    def test_missing_values_not_evidence(self):
        r = self.match(business(website="", phone="", address="", city="", state=""),
                       [company(name="Unrelated Name", website="", phone="", address="", city="", state="")])
        self.assertEqual(r["crm_status"], "REVIEW")
        self.assertIn("INSUFFICIENT_IDENTIFIERS", r["review_reason_crm"])

    def test_generic_name_weak_identity(self):
        r = self.match(business(name="Hair Salon", phone="", website="", address=""), [])
        self.assertEqual(r["crm_status"], "REVIEW")

    def test_no_match_sufficient_identity_new(self):
        self.assertEqual(self.match(records=[])["crm_status"], "NEW")

    def test_full_pagination_active_and_archived(self):
        reader = FakeReader(self.cfg, [company(), company("2")], [company("3", archived=True)])
        snap = retrieve(reader, self.cfg)
        self.assertEqual(len(snap["records"]), 3)
        self.assertEqual(snap["partitions"]["active"]["pages"], 2)
        self.assertEqual(snap["partitions"]["archived"]["pages"], 1)
        self.assertEqual(len(reader.calls), 4)
        validate(snap, self.cfg)

    def test_empty_complete_snapshot_valid(self):
        snap = self.snapshot()
        self.assertEqual(snap["records"], [])
        validate(snap, self.cfg)

    def test_failed_page_never_complete(self):
        reader = FakeReader(self.cfg, [company(), company("2")])
        original = reader.get
        def fail(path, params=None):
            if params and params.get("after"):
                raise RuntimeError("synthetic page failure")
            return original(path, params)
        reader.get = fail
        with self.assertRaises(RuntimeError):
            retrieve(reader, self.cfg)

    def test_repeated_cursor_fails(self):
        reader = FakeReader(self.cfg)
        original = reader.get
        reader.get = lambda path, params=None: original(path, params) if params is None else {"results": [], "paging": {"next": {"after": "same"}}}
        with self.assertRaises(SnapshotError):
            retrieve(reader, self.cfg)

    def test_repeated_record_fails(self):
        with self.assertRaises(SnapshotError):
            retrieve(FakeReader(self.cfg, [company(), company()]), self.cfg)

    def test_missing_required_property_fails(self):
        reader = FakeReader(self.cfg)
        reader.get = lambda *args: {"results": [{"name": "name"}]}
        with self.assertRaises(SnapshotError):
            retrieve(reader, self.cfg)

    def test_incomplete_snapshot_no_outputs(self):
        snap = self.snapshot()
        snap["status"] = "incomplete"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with self.assertRaises(SnapshotError):
                compare_snapshot(root / "unused.csv", snap, self.cfg, root)
            self.assertFalse((root / "crm_checks").exists())

    def test_tampered_snapshot_fails(self):
        snap = self.snapshot([company()])
        snap["records"][0]["properties"]["name"] = "Tampered"
        with self.assertRaises(SnapshotError):
            validate(snap, self.cfg)

    def test_incomplete_archived_partition_fails_even_with_checksum(self):
        snap = self.snapshot()
        snap["partitions"]["archived"]["exhausted"] = False
        snap.pop("manifest_sha256")
        snap["manifest_sha256"] = digest(snap)
        with self.assertRaises(SnapshotError):
            validate(snap, self.cfg)

    def test_wrong_account_fails(self):
        snap = self.snapshot()
        self.cfg["portal_id"] = "999"
        with self.assertRaises(SnapshotError):
            validate(snap, self.cfg)

    def test_stale_snapshot_fails(self):
        snap = self.snapshot()
        snap["started_at"] = snap["completed_at"] = "2000-01-01T00:00:00+00:00"
        snap.pop("manifest_sha256")
        snap["manifest_sha256"] = digest(snap)
        with self.assertRaises(SnapshotError):
            validate(snap, self.cfg)

    def test_export_preserves_v11_values_and_has_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            path = root / "qualified.csv"
            row = {**business(), "lead_id": "L1", "score": "75", "grade": "B / Qualified",
                   "queue": "qualified", "score_explanation": "Original explanation", "phone": "'+14075550123"}
            with path.open("w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(row))
                writer.writeheader()
                writer.writerow(row)
            original = path.read_bytes()
            result = compare_snapshot(path, self.snapshot([company()]), self.cfg, root)
            with open(result["outputs"]["EXISTING"], newline="", encoding="utf-8-sig") as handle:
                output = next(csv.DictReader(handle))
            for k, v in row.items():
                self.assertEqual(output[k], v)
            self.assertEqual(output["matched_hubspot_id"], "1")
            self.assertTrue(json.loads(output["match_evidence"]))
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(result["counts"], {"NEW": 0, "EXISTING": 1, "REVIEW": 0})

    def test_reader_rejects_non_allowlisted_path(self):
        reader = HubSpotReader("synthetic-token", self.cfg)
        with self.assertRaises(ReadError):
            reader.get("/crm/v3/objects/contacts")

    def test_reader_issues_get_only(self):
        reader = HubSpotReader("synthetic-token", self.cfg)
        response = io.BytesIO(b'{"results":[]}')
        reader.opener = Mock()
        reader.opener.open.return_value = response
        reader.get("/crm/v3/objects/companies")
        request = reader.opener.open.call_args.args[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertIsNone(request.data)

    def test_reader_rejects_other_host(self):
        self.cfg["api_base"] = "https://example.com"
        with self.assertRaises(ReadError):
            HubSpotReader("synthetic", self.cfg)

    def test_redirects_disabled(self):
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, "", {}, "https://example.com"))

    def test_no_live_call_for_offline_failure(self):
        with patch("check_hubspot.HubSpotReader") as reader:
            with patch("sys.stderr", new=io.StringIO()):
                self.assertEqual(main(["missing.csv", "--snapshot", "missing.json"]), 1)
            reader.assert_not_called()

if __name__ == "__main__":
    unittest.main()
