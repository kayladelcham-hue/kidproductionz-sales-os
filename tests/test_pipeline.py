import csv
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from zipfile import ZipFile
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from process_leads import run, load_config
from normalize import normalize, phone
from scoring import evaluate
from export import safe_cell

CONFIG = ROOT / "config" / "ideal_client_profile.json"

def full(**changes):
    row = dict(name="Synthetic Orchid Studio", category="Hair salon", city="Orlando",
               state="Florida", phone="(407) 555-0123", site="https://www.orchid.example/",
               instagram="https://instagram.com/synthetic_orchid", rating="4.8", reviews="42",
               ownership="locally owned", ownership_evidence="Synthetic test evidence",
               visual_opportunity="yes", visual_evidence="Synthetic content opportunity",
               owner_name="Synthetic Owner", street="123 Example Street")
    row.update(changes)
    return row

def csv_file(path, rows):
    headers = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        w.writerows(rows)
    return path

def xlsx_fixture(path, rows):
    # Minimal OOXML test fixture, not a user-facing workbook.
    headers = list(rows[0])
    data = [headers] + [[r.get(k, "") for k in headers] for r in rows]
    body = []
    for i, row in enumerate(data, 1):
        cells = []
        for j, value in enumerate(row):
            col = chr(65+j)
            cells.append(f'<c r="{col}{i}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>')
        body.append(f'<row r="{i}">' + "".join(cells) + '</row>')
    with ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        z.writestr("_rels/.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Leads" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr("xl/worksheets/sheet1.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>' + "".join(body) + '</sheetData></worksheet>')
    return path

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.cfg = load_config(CONFIG)

    def score(self, row):
        return evaluate(normalize(row, self.cfg), self.cfg)

    def process(self, rows):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        source = csv_file(base / "input.csv", rows)
        summary = run([source], CONFIG, base)
        outputs = {}
        for queue, path in summary["outputs"].items():
            with open(path, encoding="utf-8-sig", newline="") as f:
                outputs[queue] = list(csv.DictReader(f))
        return outputs, summary, source

    def test_full_score_and_mutually_exclusive_categories(self):
        lead = self.score(full(subtypes="Realtor"))
        self.assertEqual(lead["score"], 100)
        self.assertIn("secondary_category: +0", lead["score_explanation"])
        self.assertEqual(lead["website"], "https://orchid.example")
        self.assertEqual(lead["phone"], "+14075550123")

    def test_evidence_not_invented(self):
        lead = self.score(full(ownership_evidence="", visual_evidence="", owner_name=""))
        self.assertEqual(lead["score"], 79)
        self.assertIn("independent: +0", lead["score_explanation"])

    def test_atlanta_toggle_and_zip_not_override(self):
        row = full(city="Atlanta", state="GA", postal_code="32801")
        self.assertIn("OUTSIDE_ACTIVE_SERVICE_AREA", self.score(row)["rejection_reasons"])
        self.cfg["markets"]["atlanta"]["enabled"] = True
        self.assertEqual(self.score(row)["market"], "atlanta")
        self.assertIn("UNKNOWN_SERVICE_AREA", self.score(full(city="", postal_code="32801"))["review_reasons"])

    def test_all_orlando_cities(self):
        for city in self.cfg["markets"]["orlando"]["cities"]:
            self.assertEqual(self.score(full(city=city, state="fl"))["market"], "orlando")

    def test_chain_goes_to_review_even_below_50(self):
        output, _, _ = self.process([full(name="Great Clips", ownership="", ownership_evidence="", visual_opportunity="", owner_name="")])
        self.assertEqual(len(output["review"]), 1)
        self.assertLess(float(output["review"][0]["score"]), 50)
        self.assertIn("LIKELY_CHAIN", output["review"][0]["flags"])

    def test_local_chain_evidence(self):
        lead = self.score(full(name="Great Clips"))
        self.assertEqual(lead["score"], 100)
        self.assertIn("LIKELY_CHAIN", lead["flags"])
        self.assertNotIn("LIKELY_CHAIN", lead["review_reasons"])

    def test_explicit_exclusions(self):
        cases = [
            ({"business_status": "CLOSED_PERMANENTLY"}, "PERMANENTLY_CLOSED"),
            ({"temporarily_closed": "true"}, "TEMPORARILY_CLOSED"),
            ({"category": "Cosmetology school"}, "EXCLUDED_CATEGORY"),
            ({"city": "Miami"}, "OUTSIDE_ACTIVE_SERVICE_AREA"),
            ({"phone": "", "site": "", "instagram": ""}, "NO_USABLE_CONTACT")
        ]
        for change, reason in cases:
            with self.subTest(reason=reason):
                output, _, _ = self.process([full(**change)])
                self.assertIn(reason, output["rejected"][0]["rejection_reason"])

    def test_review_and_qualified_boundaries(self):
        self.assertEqual(self.cfg["thresholds"]["qualified"], 65)
        output, _, _ = self.process([full(ownership="", visual_opportunity="", owner_name="", instagram="")])
        self.assertEqual(output["qualified"][0]["score"], "75")
        self.assertEqual(output["qualified"][0]["qualification_reason"], "PRIMARY_CRITERIA_MET")
        self.cfg["weights"]["website"] = 7
        self.assertEqual(self.score(full(ownership="", visual_opportunity="", owner_name="", instagram=""))["score"], 76)

    def test_social_and_booking_are_not_business_websites(self):
        lead = self.score(full(site="https://instagram.com/example", instagram="", phone=""))
        self.assertEqual(lead["website"], "")
        self.assertTrue(lead["social"])
        lead = self.score(full(site="https://booksy.com/example", instagram="", phone=""))
        self.assertTrue(lead["other_contact"])
        self.assertNotIn("NO_USABLE_CONTACT", lead["rejection_reasons"])
        lead = self.score(full(site="https://google.com/maps/place/test", instagram="", phone=""))
        self.assertIn("NO_USABLE_CONTACT", lead["rejection_reasons"])

    def test_unknown_category_is_review(self):
        output, _, _ = self.process([full(category="Unclassified business")])
        self.assertIn("CATEGORY_NEEDS_REVIEW", output["review"][0]["review_reason"])

    def test_food_requires_visual_evidence(self):
        lead = self.score(full(category="Restaurant", visual_evidence=""))
        self.assertIn("CATEGORY_NEEDS_REVIEW", lead["review_reasons"])
        self.assertIn("secondary_category: +0", lead["score_explanation"])

    def test_exact_duplicate_preserved_and_best_copy_wins(self):
        output, summary, _ = self.process([full(owner_name=""), full()])
        self.assertEqual(summary["counts"], {"qualified": 1, "review": 0, "rejected": 1})
        self.assertEqual(output["qualified"][0]["source_row"], "3")
        self.assertIn("EXACT_DUPLICATE", output["rejected"][0]["rejection_reason"])
        self.assertEqual(output["rejected"][0]["duplicate_of"], output["qualified"][0]["lead_id"])

    def test_uncertain_duplicate_routes_both(self):
        output, summary, _ = self.process([full(), full(name="Another Studio", place_id="different")])
        self.assertEqual(summary["counts"]["review"], 2)
        self.assertTrue(all("UNCERTAIN_DUPLICATE" in r["review_reason"] for r in output["review"]))

    def test_xlsx_csv_cross_file_and_source_integrity(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            csv_path = csv_file(root / "a.csv", [full(place_id="synthetic-123")])
            xlsx_path = xlsx_fixture(root / "b.xlsx", [full(place_id="synthetic-123")])
            before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (csv_path, xlsx_path)}
            result = run([csv_path, xlsx_path], CONFIG, root)
            self.assertEqual(result["counts"], {"qualified": 1, "review": 0, "rejected": 1})
            again = run([csv_path, xlsx_path], CONFIG, root)
            self.assertNotEqual(result["run_id"], again["run_id"])
            self.assertTrue(all(Path(p).exists() for p in result["outputs"].values()))
            self.assertEqual(before, {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in before})

    def test_bad_file_fails_before_exports(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            bad = root / "bad.csv"
            bad.write_text("name,city\nbad,Orlando,unexpected\n")
            with self.assertRaises(ValueError):
                run([bad], CONFIG, root)
            self.assertFalse((root / "processed").exists())

    def test_csv_cell_safety_and_phone(self):
        self.assertEqual(safe_cell("=1+1"), "'=1+1")
        self.assertEqual(phone("407-555-0123 ext 9"), "+14075550123 ext 9")
        self.assertEqual(phone("0000000000"), "")
        self.assertEqual(phone("not available"), "")

    def test_no_contact_clamps_and_preserves_reason(self):
        lead = self.score(full(category="Other", city="Miami", phone="", site="", instagram="", ownership="", visual_opportunity="", owner_name="", rating="", reviews=""))
        self.assertEqual(lead["score"], 0)
        self.assertLess(lead["raw_score"], 0)
        self.assertIn("Clamp", lead["score_explanation"])

    def test_invalid_thresholds_fail(self):
        with tempfile.TemporaryDirectory() as d:
            self.cfg["thresholds"]["qualified"] = 110
            path = Path(d) / "bad.json"
            path.write_text(json.dumps(self.cfg))
            with self.assertRaises(ValueError):
                load_config(path)

if __name__ == "__main__":
    unittest.main()
