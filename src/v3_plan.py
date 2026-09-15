"""Offline import planning. No HTTP or write client imports."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import uuid
from v2_audit import load_run
from crm_normalize import unprotect
from hubspot_snapshot import digest

def load_import_config(path):
    cfg = json.loads(path.read_text(encoding="utf-8-sig"))
    if cfg["version"] != "3.0" or type(cfg["enabled"]) is not bool or type(cfg["pilot_limit"]) is not int or cfg["pilot_limit"] < 1:
        raise ValueError("Invalid V3 configuration")
    if not cfg["property_map"] or cfg["max_recheck_age_seconds"] <= 0:
        raise ValueError("Missing V3 mapping or invalid recheck age")
    if len(set(cfg["property_map"].values())) != len(cfg["property_map"]):
        raise ValueError("Property targets must be unique")
    return cfg

def source_values(row, summary):
    return {**row, "source_run_id": Path(summary["input"]).stem.removeprefix("qualified_leads_"),
            "v2_run_id": summary["run_id"]}

def payload(row, summary, cfg, schema):
    values = source_values(row, summary)
    props, omitted = {}, {}
    for source, target in cfg["property_map"].items():
        value = values.get(source, "")
        if value == "":
            continue
        definition = schema.get(target)
        if definition is None:
            omitted[source] = "HubSpot property unavailable: " + target
        elif definition.get("archived") or definition.get("modificationMetadata", {}).get("readOnlyValue"):
            omitted[source] = "HubSpot property not writable: " + target
        elif definition.get("type") == "enumeration" and str(value) not in {v["value"] for v in definition.get("options", [])}:
            omitted[source] = "Value not in HubSpot property options: " + target
        else:
            props[target] = unprotect(value)
    if not props.get("name"):
        raise ValueError("Writable name property is required")
    return {"properties": props}, omitted

def build_plan(summary_path, cfg, schema, selected_ids=None):
    summary, groups = load_run(summary_path)
    available = {r["lead_id"]: r for r in groups["NEW"]}
    if selected_ids is None:
        selected_ids = sorted(available)[:cfg["pilot_limit"]]
    if len(selected_ids) != len(set(selected_ids)) or len(selected_ids) > cfg["pilot_limit"]:
        raise ValueError("Duplicate selection or pilot limit exceeded")
    if not selected_ids or any(k not in available for k in selected_ids):
        raise ValueError("Only NEW records are eligible")
    items = []
    for lid in selected_ids:
        row = available[lid]
        request, omitted = payload(row, summary, cfg, schema)
        items.append({"lead_id": lid, "source": row, "request": request, "omitted_fields": omitted,
                      "source_key": digest([summary["input_sha256"], lid])})
    plan = {"version": "3.0", "mode": "DRY_RUN", "created_at": datetime.now(timezone.utc).isoformat(),
            "portal_id": str(summary["portal_id"]), "v2_run_id": summary["run_id"],
            "summary_path": str(summary_path.resolve()), "summary_sha256": hashlib.sha256(summary_path.read_bytes()).hexdigest(),
            "source_summary": {"input": summary["input"], "run_id": summary["run_id"], "input_sha256": summary["input_sha256"]},
            "import_config_sha256": digest({k:v for k,v in cfg.items() if k != "enabled"}),
            "count": len(items), "items": items,
            "warnings": ["Offline preview only; each create requires a fresh complete duplicate recheck and schema validation.",
                         "Unavailable metadata stays in the local plan/journal; no HubSpot properties are created.",
                         "Cached property names do not establish writability. Fresh schema must reproduce this exact payload."]}
    plan["plan_sha256"] = digest(plan)
    return plan

def validate_plan(plan, cfg):
    unsigned = dict(plan)
    checksum = unsigned.pop("plan_sha256", None)
    if checksum != digest(unsigned) or plan.get("version") != "3.0":
        raise ValueError("Import plan checksum invalid")
    if plan["import_config_sha256"] != digest({k:v for k,v in cfg.items() if k != "enabled"}):
        raise ValueError("Import mapping/configuration changed; make a new plan")
    if len(plan["items"]) != plan["count"] or plan["count"] > cfg["pilot_limit"]:
        raise ValueError("Pilot limit exceeded or plan count invalid")
    if any(i["source"].get("crm_status") != "NEW" for i in plan["items"]):
        raise ValueError("Only NEW records are eligible")
    if len({i["source_key"] for i in plan["items"]}) != plan["count"]:
        raise ValueError("Duplicate plan source records")
    summary_path = Path(plan["summary_path"])
    if hashlib.sha256(summary_path.read_bytes()).hexdigest() != plan["summary_sha256"]:
        raise ValueError("V2 summary changed")
    _, groups = load_run(summary_path)
    current = {r["lead_id"]:r for r in groups["NEW"]}
    if any(current.get(i["lead_id"]) != i["source"] for i in plan["items"]):
        raise ValueError("V2 source rows changed")

def save_plan(plan, root):
    folder = root / "v3_imports"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / ("plan_" + plan["plan_sha256"][:16] + ".json")
    with path.open("x", encoding="utf-8") as handle:
        json.dump(plan, handle, indent=2, ensure_ascii=False)
    approval = {"approved": False, "approved_by": "", "plan_sha256": plan["plan_sha256"],
                "portal_id": plan["portal_id"], "lead_ids": [i["lead_id"] for i in plan["items"]]}
    apath = path.with_name(path.stem + "_approval.json")
    with apath.open("x", encoding="utf-8") as handle:
        json.dump(approval, handle, indent=2)
    return {"plan": str(path.resolve()), "approval_template": str(apath.resolve()),
            "mode": "DRY_RUN", "writes": 0, "count": plan["count"]}
