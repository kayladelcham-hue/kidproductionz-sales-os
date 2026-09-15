"""Controlled V3 orchestration; V2 modules stay GET-only and unchanged."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from check_hubspot import load_config
from hubspot_client import HubSpotReader
from hubspot_snapshot import retrieve, validate
from crm_normalize import identity
from crm_match import CompanyIndex, classify
from v3_plan import load_import_config, payload, build_plan, validate_plan, save_plan

ROOT = Path(__file__).resolve().parents[1]

def append_event(path, event):
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"at":datetime.now(timezone.utc).isoformat(), **event}, ensure_ascii=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())

def execute(plan, approval, cfg, match_cfg, reader, creator_factory, root):
    if cfg["enabled"] is not True:
        raise ValueError("V3 is disabled; no writes permitted")
    validate_plan(plan, cfg)
    if (approval.get("approved") is not True or not str(approval.get("approved_by", "")).strip() or
        approval.get("plan_sha256") != plan["plan_sha256"] or
        str(approval.get("portal_id")) != plan["portal_id"] or
        approval.get("lead_ids") != [i["lead_id"] for i in plan["items"]] or
        str(match_cfg.get("portal_id")) != plan["portal_id"]):
        raise ValueError("Explicit approval for this exact plan, selection and account is required")
    folder = root / "v3_imports"
    folder.mkdir(parents=True, exist_ok=True)
    lock = folder / "execution.lock"
    # Exclusive local execution. A crash intentionally leaves a lock for review.
    with lock.open("x", encoding="utf-8") as handle:
        handle.write(plan["plan_sha256"])
    journal = folder / "import_journal.jsonl"
    outcomes = []
    try:
        history = [json.loads(line) for line in journal.read_text().splitlines()] if journal.exists() else []
        blocked = {e["source_key"] for e in history if e.get("status") in ("ATTEMPT", "CREATED", "CREATE_FAILED_OR_UNKNOWN")}
        last = {}
        attempts = {}
        for event in history:
            if event.get("status") in ("ATTEMPT", "CREATED", "CREATE_FAILED_OR_UNKNOWN"):
                last[event["source_key"]] = event
            if event.get("status") == "ATTEMPT":
                attempts[event["source_key"]] = event
        if any(e["status"] in ("ATTEMPT", "CREATE_FAILED_OR_UNKNOWN") for e in last.values()):
            raise ValueError("An earlier write has an unresolved outcome; reconcile it before further imports")
        local_created = [{"id": e["hubspot_company_id"], "properties": attempts[k]["request"]["properties"], "archived": False}
                         for k, e in last.items() if e["status"] == "CREATED"]
        creator = None
        for item in plan["items"]:
            base = {"plan_sha256":plan["plan_sha256"], "v2_run_id":plan["v2_run_id"],
                    "lead_id":item["lead_id"], "source_key":item["source_key"]}
            if item["source_key"] in blocked:
                event = {**base, "status":"SKIP_PREVIOUS_ATTEMPT"}
                append_event(journal, event)
                outcomes.append(event)
                continue
            try:
                definitions = reader.get("/crm/v3/properties/companies").get("results")
                if not isinstance(definitions, list):
                    raise ValueError("Invalid fresh property schema")
                schema = {p["name"]:p for p in definitions}
                request, omitted = payload(item["source"], plan["source_summary"], cfg, schema)
                if request != item["request"]:
                    raise ValueError("Fresh schema changes approved payload; create and approve a new plan")
                # Full active+archived retrieval immediately before EACH attempted create.
                snapshot = retrieve(reader, match_cfg)
                validate(snapshot, match_cfg)
                known_ids = {r["id"] for r in snapshot["records"]}
                visible = snapshot["records"] + [r for r in local_created if r["id"] not in known_ids]
                result = classify(identity(item["source"], match_cfg), CompanyIndex(visible, match_cfg), match_cfg)
                if result["crm_status"] != "NEW":
                    event = {**base, "status":"SKIP_" + result["crm_status"], "recheck":result,
                             "snapshot_id":snapshot["snapshot_id"]}
                    append_event(journal, event)
                    outcomes.append(event)
                    continue
                if creator is None:
                    creator = creator_factory()
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(snapshot["completed_at"])).total_seconds()
                if age > cfg["max_recheck_age_seconds"]:
                    raise ValueError("Duplicate recheck too old; no create attempted")
            except Exception:
                append_event(journal, {**base, "status":"RECHECK_OR_PREFLIGHT_FAILED"})
                raise
            append_event(journal, {**base, "status":"ATTEMPT", "snapshot_id":snapshot["snapshot_id"],
                                  "request":request, "omitted_fields":omitted,
                                  "source_metadata":item["source"]})
            blocked.add(item["source_key"])
            try:
                cid = creator.create_company(request)
                event = {**base, "status":"CREATED", "hubspot_company_id":cid}
                append_event(journal, event)
                local_created.append({"id":cid, "properties":request["properties"], "archived":False})
                outcomes.append(event)
            except Exception:
                # Don't persist arbitrary exception text from a transport. The
                # dedicated writer's error is redacted when shown by the CLI.
                append_event(journal, {**base, "status":"CREATE_FAILED_OR_UNKNOWN"})
                raise
        return outcomes
    finally:
        lock.unlink()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Default: local plan only, zero HTTP calls")
    mode.add_argument("--execute", action="store_true", help="Requires enabled config and exact approval file")
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--refresh-schema", action="store_true", help="Dry-run only: explicitly allow a read-only property-schema GET")
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--approval", type=Path)
    parser.add_argument("--config", type=Path, default=ROOT / "config/hubspot_import.json")
    parser.add_argument("--matching-config", type=Path, default=ROOT / "config/hubspot_matching.json")
    parser.add_argument("--output-root", type=Path, default=ROOT)
    args = parser.parse_args()
    cfg = load_import_config(args.config)
    if not args.execute:
        if not args.summary or (not args.snapshot and not args.refresh_schema):
            parser.error("Dry-run needs --summary and either --snapshot or --refresh-schema")
        if args.refresh_schema:
            match_cfg = load_config(args.matching_config)
            schema_reader = HubSpotReader.from_environment(match_cfg)
            definitions = schema_reader.get("/crm/v3/properties/companies")["results"]
            schema = {p["name"]:p for p in definitions}
            schema_portal = str(match_cfg["portal_id"])
        else:
            cached = json.loads(args.snapshot.read_text(encoding="utf-8-sig"))
            schema = {name:{"name":name} for name in cached["properties"]}
            schema_portal = str(cached["portal_id"])
        plan = build_plan(args.summary, cfg, schema)
        if schema_portal != plan["portal_id"]:
            raise ValueError("Schema account does not match V2 run")
        print(json.dumps(save_plan(plan, args.output_root), indent=2))
        return
    if cfg["enabled"] is not True:
        raise ValueError("V3 is disabled")
    if not args.plan or not args.approval:
        parser.error("Execute needs --plan and --approval")
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    approval = json.loads(args.approval.read_text(encoding="utf-8"))
    match_cfg = load_config(args.matching_config)
    # Loading a credential makes no request. Writes live only in V3 modules.
    reader = HubSpotReader.from_environment(match_cfg)
    from v3_writer import CompanyCreator
    results = execute(plan, approval, cfg, match_cfg, reader, lambda:CompanyCreator(cfg), args.output_root)
    print(json.dumps(results, ensure_ascii=True, indent=2))

if __name__ == "__main__":
    main()
