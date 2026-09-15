"""Controlled import tests. All readers and writers are synthetic/mocked."""
import copy
import csv
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from check_hubspot import load_config
from hubspot_snapshot import retrieve
from v2_audit import audit
from v3_plan import load_import_config, build_plan, save_plan, payload
from v3_import import execute
from v3_writer import CompanyCreator, CreateError
from test_hubspot_v2 import FakeReader, company, business

def write_csv(path, rows, fields=None):
    fields = fields or list(rows[0])
    with path.open("w", encoding="utf-8-sig", newline="") as h:
        w = csv.DictWriter(h, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

class ControlledImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cfg = load_import_config(ROOT / "config/hubspot_import.json")
        self.match = load_config(ROOT / "config/hubspot_matching.json")
        self.match["portal_id"] = "12345"
        self.schema = {k: {"name":k} for k in self.match["properties"]}

    def source(self, new=2, existing=0, review=0):
        outputs, counts = {}, {}
        for status, count in (("NEW",new),("EXISTING",existing),("REVIEW",review)):
            rows = [{**business(name=f"Prospect {i*928374:08x} {status}", website=f"https://{status.lower()}{i}.example",
                                phone=f"407555{i+1000:04d}", address=f"{i+100} Example Street"),
                     "lead_id":status+str(i),"score":"75","grade":"B / Qualified","queue":"qualified",
                     "normalized_category":"hair salon","city":"Orlando","state":"FL",
                     "score_explanation":"Original score explanation","source_file":"source.xlsx","source_row":str(i+2),
                     "crm_status":status,"match_confidence":"0","match_rule":"NO_CREDIBLE_MATCH",
                     "match_evidence":"[]","conflicting_evidence":"[]","review_reason_crm":""} for i in range(count)]
            path=self.root/(status+".csv")
            fields=list(rows[0]) if rows else ["lead_id","crm_status","queue"]
            write_csv(path,rows,fields)
            outputs[status]=str(path)
            counts[status]=count
        candidates=self.root/"candidates.csv"
        write_csv(candidates,[],["lead_id","hubspot_id","hubspot_values"])
        outputs["candidates"]=str(candidates)
        summary={"run_id":"V2-test","portal_id":"12345","input":"qualified_leads_V1-test.csv",
                 "input_sha256":"synthetic-input-hash","outputs":outputs,"counts":counts}
        path=self.root/"summary.json"
        path.write_text(json.dumps(summary))
        return path

    def plan(self, new=2):
        return build_plan(self.source(new), self.cfg, self.schema)

    def approve(self, plan):
        self.cfg["enabled"]=True
        return {"approved":True,"approved_by":"Synthetic Reviewer","portal_id":"12345",
                "plan_sha256":plan["plan_sha256"],"lead_ids":[i["lead_id"] for i in plan["items"]]}

    def test_disabled_by_default(self):
        self.assertIs(self.cfg["enabled"],False)
        self.assertEqual(self.cfg["pilot_limit"],10)

    def test_audit_10_10_all_review_and_blank_decisions(self):
        result=audit(self.source(15,12,28),self.root)
        self.assertEqual(result["sample_counts"],{"NEW":10,"EXISTING":10,"REVIEW":28})
        with open(result["output"],encoding="utf-8-sig",newline="") as h:
            rows=list(csv.DictReader(h))
        self.assertEqual(len(rows),48)
        self.assertTrue(all(r["audit_decision"]=="" for r in rows))
        self.assertTrue(all("hubspot_candidate_data" in r for r in rows))

    def test_audit_reproducible(self):
        source=self.source(20,20,2)
        a=audit(source,self.root)
        b=audit(source,self.root)
        def ids(path):
            with open(path,encoding="utf-8-sig",newline="") as h:
                return [r["lead_id"] for r in csv.DictReader(h)]
        self.assertEqual(ids(a["output"]),ids(b["output"]))

    def test_only_new_can_be_selected(self):
        source=self.source(1,1,1)
        for lid in ("EXISTING0","REVIEW0"):
            with self.assertRaises(ValueError):
                build_plan(source,self.cfg,self.schema,[lid])

    def test_default_pilot_limit(self):
        plan=self.plan(12)
        self.assertEqual(plan["count"],10)

    def test_explicit_over_limit_rejected(self):
        source=self.source(11)
        with self.assertRaises(ValueError):
            build_plan(source,self.cfg,self.schema,["NEW"+str(i) for i in range(11)])

    def test_disabled_execution_no_reads_or_writes(self):
        plan=self.plan()
        reader,writer=Mock(),Mock()
        with self.assertRaises(ValueError):
            execute(plan,{},self.cfg,self.match,reader,lambda:writer,self.root)
        reader.get.assert_not_called()
        writer.create_company.assert_not_called()

    def test_approval_required(self):
        plan=self.plan()
        self.cfg["enabled"]=True
        reader=Mock()
        with self.assertRaises(ValueError):
            execute(plan,{},self.cfg,self.match,reader,Mock(),self.root)
        reader.get.assert_not_called()

    def test_fresh_snapshot_before_every_write(self):
        plan=self.plan()
        approval=self.approve(plan)
        reader=FakeReader(self.match)
        writer=Mock()
        sequence=[]
        def refresh(*args):
            sequence.append("read")
            return retrieve(FakeReader(self.match),self.match)
        def create(request):
            sequence.append("write")
            return str(100+len(sequence))
        writer.create_company.side_effect=create
        with patch("v3_import.retrieve",side_effect=refresh):
            outcomes=execute(plan,approval,self.cfg,self.match,reader,lambda:writer,self.root)
        self.assertEqual(sequence,["read","write","read","write"])
        self.assertEqual(len(outcomes),2)
        log=(self.root/"v3_imports/import_journal.jsonl").read_text()
        self.assertIn('"status": "ATTEMPT"',log)
        self.assertIn("hubspot_company_id",log)

    def test_existing_skipped(self):
        plan=self.plan(1)
        approval=self.approve(plan)
        row=plan["items"][0]["source"]
        reader=FakeReader(self.match,[{"id":"42","properties":row,"archived":False}])
        writer=Mock()
        result=execute(plan,approval,self.cfg,self.match,reader,lambda:writer,self.root)
        self.assertEqual(result[0]["status"],"SKIP_EXISTING")
        writer.create_company.assert_not_called()

    def test_ambiguous_skipped(self):
        plan=self.plan(1)
        approval=self.approve(plan)
        row=plan["items"][0]["source"]
        reader=FakeReader(self.match,[company(name="Different Business",phone=row["phone"],website="https://other.example",address="789 Elsewhere Road")])
        writer=Mock()
        result=execute(plan,approval,self.cfg,self.match,reader,lambda:writer,self.root)
        self.assertEqual(result[0]["status"],"SKIP_REVIEW")
        writer.create_company.assert_not_called()

    def test_incomplete_recheck_stops_before_write(self):
        plan=self.plan(1)
        approval=self.approve(plan)
        writer=Mock()
        with patch("v3_import.retrieve",return_value={"status":"incomplete"}):
            with self.assertRaises(Exception):
                execute(plan,approval,self.cfg,self.match,FakeReader(self.match),lambda:writer,self.root)
        writer.create_company.assert_not_called()

    def test_dry_run_zero_network_and_writes(self):
        with patch("v3_writer.CompanyCreator") as writer,patch("hubspot_client.HubSpotReader.get") as get:
            result=save_plan(self.plan(1),self.root)
        writer.assert_not_called()
        get.assert_not_called()
        self.assertEqual(result["writes"],0)
        approval=json.loads(Path(result["approval_template"]).read_text())
        self.assertIs(approval["approved"],False)

    def test_payload_preserves_metadata_where_available(self):
        plan=self.plan(1)
        row=plan["items"][0]["source"]
        schema={v:{"name":v} for v in self.cfg["property_map"].values()}
        request,omitted=payload(row,plan["source_summary"],self.cfg,schema)
        self.assertFalse(omitted)
        for source in ("score","grade","normalized_category","city","state","score_explanation","source_file"):
            self.assertEqual(request["properties"][self.cfg["property_map"][source]],row[source])
        self.assertEqual(request["properties"]["kidproductionz_source_run_id"],"V1-test")

    def test_missing_metadata_reported_no_property_creation(self):
        plan=self.plan(1)
        self.assertIn("score",plan["items"][0]["omitted_fields"])
        self.assertNotIn("kidproductionz_lead_score",plan["items"][0]["request"]["properties"])

    def test_schema_change_requires_new_approval(self):
        plan=self.plan(1)
        approval=self.approve(plan)
        reader=FakeReader(self.match)
        original=reader.get
        def get(path,params=None):
            response=original(path,params)
            if params is None:
                response["results"].append({"name":"kidproductionz_lead_score"})
            return response
        reader.get=get
        writer=Mock()
        with self.assertRaises(ValueError):
            execute(plan,approval,self.cfg,self.match,reader,lambda:writer,self.root)
        writer.create_company.assert_not_called()

    def test_prior_success_never_repeated(self):
        plan=self.plan(1)
        approval=self.approve(plan)
        writer=Mock()
        writer.create_company.return_value="123"
        execute(plan,approval,self.cfg,self.match,FakeReader(self.match),lambda:writer,self.root)
        result=execute(plan,approval,self.cfg,self.match,FakeReader(self.match),lambda:writer,self.root)
        self.assertEqual(writer.create_company.call_count,1)
        self.assertEqual(result[0]["status"],"SKIP_PREVIOUS_ATTEMPT")

    def test_unknown_outcome_not_retried(self):
        plan=self.plan(1)
        approval=self.approve(plan)
        writer=Mock()
        writer.create_company.side_effect=RuntimeError("synthetic")
        for _ in range(2):
            with self.assertRaises(Exception):
                execute(plan,approval,self.cfg,self.match,FakeReader(self.match),lambda:writer,self.root)
        self.assertEqual(writer.create_company.call_count,1)

    def test_creator_company_post_only(self):
        self.cfg["enabled"]=True
        with patch.dict("os.environ",{self.cfg["write_token_env"]:"synthetic-key"}):
            creator=CompanyCreator(self.cfg)
        creator.opener=Mock()
        creator.opener.open.return_value=io.BytesIO(b'{"id":"123"}')
        self.assertEqual(creator.create_company({"properties":{"name":"Test"}}),"123")
        req=creator.opener.open.call_args.args[0]
        self.assertEqual(req.get_method(),"POST")
        self.assertEqual(req.full_url,"https://api.hubapi.com/crm/v3/objects/companies")
        self.assertEqual(set(json.loads(req.data)),{"properties"})
        for method in ("patch","put","delete","create_contact","create_deal","create_task"):
            self.assertFalse(hasattr(creator,method))

    def test_associations_payload_rejected(self):
        self.cfg["enabled"]=True
        with patch.dict("os.environ",{self.cfg["write_token_env"]:"synthetic-key"}):
            creator=CompanyCreator(self.cfg)
        creator.opener=Mock()
        with self.assertRaises(CreateError):
            creator.create_company({"properties":{"name":"Test"},"associations":[]})
        creator.opener.open.assert_not_called()

    def test_secret_redacted_on_create_failure_no_retry(self):
        self.cfg["enabled"]=True
        secret="synthetic-create-secret"
        with patch.dict("os.environ",{self.cfg["write_token_env"]:secret}):
            creator=CompanyCreator(self.cfg)
        creator.opener=Mock()
        creator.opener.open.side_effect=HTTPError("https://api.hubapi.com",400,"Bad",{},io.BytesIO(("Bearer "+secret).encode()))
        with self.assertRaises(CreateError) as exc:
            creator.create_company({"properties":{"name":"Test"}})
        self.assertNotIn(secret,str(exc.exception))
        self.assertEqual(creator.opener.open.call_count,1)

    def test_cli_offline_dry_run_never_loads_credentials(self):
        from v3_import import main
        source=self.source(1)
        snapshot=self.root/"cached.json"
        snapshot.write_text(json.dumps({"portal_id":"12345","properties":list(self.schema)}))
        cfgpath=self.root/"import-config.json"
        cfgpath.write_text(json.dumps(self.cfg))
        argv=["v3_import.py","--dry-run","--summary",str(source),"--snapshot",str(snapshot),"--config",str(cfgpath),"--output-root",str(self.root)]
        with patch("sys.argv",argv),patch("sys.stdout",new=io.StringIO()),patch("v3_import.HubSpotReader.from_environment") as reader,patch("v3_writer.CompanyCreator") as writer:
            main()
        reader.assert_not_called()
        writer.assert_not_called()

    def test_cli_refresh_schema_is_get_only_no_creator(self):
        from v3_import import main
        source=self.source(1)
        cfgpath=self.root/"import-config.json"
        cfgpath.write_text(json.dumps(self.cfg))
        matchpath=self.root/"matching.json"
        matchpath.write_text(json.dumps(self.match))
        reader=Mock()
        reader.get.return_value={"results":list(self.schema.values())}
        argv=["v3_import.py","--dry-run","--refresh-schema","--summary",str(source),"--config",str(cfgpath),"--matching-config",str(matchpath),"--output-root",str(self.root)]
        with patch("sys.argv",argv),patch("sys.stdout",new=io.StringIO()),patch("v3_import.HubSpotReader.from_environment",return_value=reader),patch("v3_writer.CompanyCreator") as writer:
            main()
        reader.get.assert_called_once_with("/crm/v3/properties/companies")
        writer.assert_not_called()

if __name__=="__main__":
    unittest.main()
