"""Regression tests for approved V1.1 calibration and safeguards."""
import json
import unittest
import test_pipeline as legacy
full = legacy.full
from deduplicate import compare

def sparse(**changes):
    row = full(ownership="", ownership_evidence="", visual_opportunity="",
               visual_evidence="", owner_name="", instagram="")
    row.update(changes)
    return row

class CalibrationTests(unittest.TestCase):
    setUp = legacy.PipelineTests.setUp
    process = legacy.PipelineTests.process
    score = legacy.PipelineTests.score

    def test_phone_only_strong_primary_qualifies(self):
        out, _, _ = self.process([sparse(site="")])
        self.assertEqual(out["qualified"][0]["score"], "69")

    def test_contact_awarded_once(self):
        lead = self.score(full(email="test@example.com", booking_appointment_link="https://booksy.com/example"))
        self.assertEqual(lead["score"], 100)
        self.assertEqual(lead["score_explanation"].count("usable_contact: +8"), 1)
        self.assertNotIn("phone: +8", lead["score_explanation"])

    def test_booking_alias_alone_qualifies(self):
        out, _, _ = self.process([sparse(phone="", site="", booking_appointment_link="https://booksy.com/en-us/123_business")])
        lead = out["qualified"][0]
        self.assertEqual(lead["score"], "69")
        self.assertEqual(lead["contact_paths"], "other_contact")

    def test_invalid_booking_is_not_contact(self):
        for link in ("not a url", "javascript:alert(1)", "https://google.com/maps",
                     "https://booksy.com", "https://instagram.com/", "https://bad..com/page"):
            with self.subTest(link=link):
                lead = self.score(sparse(phone="", site="", booking_appointment_link=link))
                self.assertIn("NO_USABLE_CONTACT", lead["rejection_reasons"])

    def test_booking_alias_can_reveal_social(self):
        lead = self.score(sparse(phone="", site="", booking_appointment_link="https://instagram.com/my_studio"))
        self.assertEqual(lead["score"], 73)
        self.assertTrue(lead["social"])

    def test_owner_title_is_not_named_owner(self):
        lead = self.score(sparse(owner_title="Synthetic Owner", owner_id="123", owner_link="https://google.com/profile/123"))
        self.assertIn("named_contact: +0", lead["score_explanation"])
        self.assertIn("independent: +0", lead["score_explanation"])

    def test_rating_gate_blocks_high_score(self):
        out, _, _ = self.process([full(rating="3.9")])
        self.assertEqual(out["review"][0]["score"], "92")
        self.assertIn("PRIMARY_RATING_REQUIREMENT_NOT_MET", out["review"][0]["review_reason"])

    def test_review_count_gate_blocks_high_score(self):
        out, _, _ = self.process([full(reviews="19")])
        self.assertIn("PRIMARY_REVIEW_COUNT_REQUIREMENT_NOT_MET", out["review"][0]["review_reason"])

    def test_missing_reputation_blocks_high_score(self):
        out, _, _ = self.process([full(rating="", reviews="")])
        self.assertEqual(out["review"][0]["score"], "84")
        self.assertIn("PRIMARY_RATING_REQUIREMENT_NOT_MET", out["review"][0]["review_reason"])
        self.assertIn("PRIMARY_REVIEW_COUNT_REQUIREMENT_NOT_MET", out["review"][0]["review_reason"])

    def test_exact_reputation_boundary_passes(self):
        out, _, _ = self.process([sparse(rating="4.0", reviews="20")])
        self.assertEqual(len(out["qualified"]), 1)

    def test_missing_location_cannot_qualify(self):
        out, _, _ = self.process([full(city="", postal_code="32801")])
        self.assertEqual(len(out["qualified"]), 0)
        self.assertIn("UNKNOWN_SERVICE_AREA", out["review"][0]["review_reason"])

    def test_barber_is_not_target_category(self):
        out, _, _ = self.process([full(category="Barber shop")])
        self.assertEqual(out["review"][0]["category_tier"], "unclassified")
        self.assertIn("CATEGORY_NEEDS_REVIEW", out["review"][0]["review_reason"])

    def test_shared_domain_and_phone_different_locations_are_relationships(self):
        out, _, _ = self.process([full(place_id="a"), full(place_id="b", street="456 Different Road")])
        self.assertEqual(len(out["qualified"]), 2)
        for row in out["qualified"]:
            self.assertIn("SHARED_DOMAIN", row["flags"])
            self.assertIn("SHARED_PHONE", row["flags"])
            self.assertEqual(json.loads(row["duplicate_matches"]), [])
            self.assertTrue(json.loads(row["relationship_matches"]))

    def test_shared_phone_alone_nonblocking(self):
        out, _, _ = self.process([full(place_id="a", site=""), full(name="Other Name", place_id="b", street="456 Different Road", site="")])
        self.assertEqual(len(out["qualified"]), 2)

    def test_name_only_similarity_nonblocking(self):
        out, _, _ = self.process([full(name="Cool beauty salon", place_id="a"),
            full(name="Eco-Beauty Salon", place_id="b", street="456 Different Road", phone="4075550199", site="https://other.example")])
        self.assertEqual(len(out["qualified"]), 2)

    def test_similar_name_plus_compatible_address_requires_review(self):
        out, _, _ = self.process([full(name="Isabel's Touch", place_id="a", street="11701 International Dr"),
            full(name="Isabels Touch", place_id="b", street="inside bamboo Nails and spa, 11701 International Dr #330", phone="4075550199", site="https://other.example")])
        self.assertEqual(len(out["review"]), 2)
        match = json.loads(out["review"][0]["duplicate_matches"])[0]
        self.assertIn("COMPATIBLE_STREET_ADDRESS_CITY_STATE", match["evidence"])
        self.assertIn("lead_id", match)
        self.assertIn("address", match)

    def test_distinct_suites_are_preserved_and_not_collapsed(self):
        out, _, _ = self.process([full(place_id="a", street="123 Main St Suite 1"),
                                 full(place_id="b", street="123 Main St Suite 2")])
        self.assertEqual(len(out["qualified"]), 2)
        self.assertEqual({r["address"] for r in out["qualified"]}, {"123 Main St Suite 1", "123 Main St Suite 2"})

    def test_different_place_ids_same_name_address_review_not_reject(self):
        out, _, _ = self.process([full(place_id="a"), full(place_id="b")])
        self.assertEqual(len(out["review"]), 2)
        self.assertFalse(out["rejected"])
        self.assertIn("DIFFERENT_PLACE_IDS_REQUIRES_REVIEW", out["review"][0]["duplicate_matches"])

    def test_same_place_id_remains_exact_with_evidence(self):
        out, _, _ = self.process([full(place_id="a"), full(name="Updated Name", place_id="a")])
        self.assertEqual(len(out["rejected"]), 1)
        self.assertIn("SAME_PLACE_ID", out["rejected"][0]["duplicate_matches"])
        self.assertEqual(len(out["qualified"]), 1)

    def test_hair_cuttery_is_chain(self):
        out, _, _ = self.process([sparse(name="Hair Cuttery", site="https://haircuttery.com/locations/fl/orlando/123")])
        self.assertEqual(len(out["review"]), 1)
        self.assertIn("LIKELY_CHAIN", out["review"][0]["flags"])
        self.assertIn("likely_chain: -35", out["review"][0]["score_explanation"])

    def test_platform_operator_is_chain_concern(self):
        for name in ("Salon Lofts", "Salon Lofts Maitland South"):
            with self.subTest(name=name):
                lead = self.score(sparse(name=name, site="https://salonlofts.com/salons/example"))
                self.assertIn("LIKELY_CHAIN", lead["review_reasons"])
                self.assertIn("platform operator name", lead["chain_evidence"])

    def test_platform_tenant_profile_not_chain(self):
        out, _, _ = self.process([sparse(name="parke.hair", site="https://salonlofts.com/bennet_parke")])
        lead = out["qualified"][0]
        self.assertEqual(lead["website"], "https://salonlofts.com/bennet_parke")
        self.assertIn("SHARED_PLATFORM_TENANT", lead["flags"])
        self.assertNotIn("LIKELY_CHAIN", lead["flags"])

    def test_tenant_linking_operator_page_not_chain(self):
        out, _, _ = self.process([sparse(name="Victoria Berry salon lofts Waterford lakes", site="https://salonlofts.com/salons/waterford_lakes")])
        self.assertEqual(len(out["qualified"]), 1)
        self.assertNotIn("LIKELY_CHAIN", out["qualified"][0]["flags"])

    def test_closure_overrides_full_score(self):
        out, _, _ = self.process([full(business_status="TEMPORARILY_CLOSED")])
        self.assertEqual(out["rejected"][0]["score"], "100")
        self.assertIn("TEMPORARILY_CLOSED", out["rejected"][0]["rejection_reason"])

if __name__ == "__main__":
    unittest.main()
