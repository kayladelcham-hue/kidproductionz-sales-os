"""Paginated active+archived snapshot with fail-closed local validation."""
from datetime import datetime, timezone
import hashlib
from difflib import get_close_matches
import json
import uuid

class SnapshotError(RuntimeError):
    pass

def now():
    return datetime.now(timezone.utc).isoformat()

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()

def retrieve(reader, cfg):
    if not cfg.get("portal_id"):
        raise SnapshotError("Set portal_id to your intended HubSpot account ID before live retrieval")
    started = now()
    schema = reader.get("/crm/v3/properties/companies")
    props = schema.get("results")
    if not isinstance(props, list) or any(not isinstance(p, dict) or not isinstance(p.get("name"), str) or not p["name"] for p in props):
        raise SnapshotError("Invalid company property response")
    available = {p["name"] for p in props if not p.get("archived", False)}
    labels = {p["name"]: p.get("label", "") for p in props}
    requested = list(dict.fromkeys(p for p in cfg["properties"] if p in available))
    missing = set(cfg["required_properties"]) - available
    optional = sorted(set(cfg["properties"]) - available - set(cfg["required_properties"]))
    validation_report = {
        "schema_endpoint": "/crm/v3/properties/companies",
        "schema_property_count": len(available),
        "requested_properties": requested,
        "missing_required_properties": sorted(missing),
        "missing_optional_properties": optional,
        "properties": [{
            "configured_name": name,
            "available": name in available,
            "required": name in cfg["required_properties"],
            "label": labels.get(name),
            "action": "request" if name in available else "fail" if name in missing else "omit_optional",
            "possible_alternative_names": get_close_matches(name, sorted(available), n=3, cutoff=0.6) if name not in available else []
        } for name in cfg["properties"]],
        "note": "Exact internal names only. Suggestions are diagnostic hints; no automatic renaming."
    }
    if hasattr(reader, "report_property_validation"):
        reader.report_property_validation(validation_report)
    if missing:
        raise SnapshotError("Required properties unavailable: " + ", ".join(sorted(missing)))
    records, partitions, seen_ids = [], {}, set()
    for archived in (False, True):
        cursors, cursor, count, pages = set(), None, 0, 0
        while True:
            if pages >= cfg["retrieval"]["max_pages_per_partition"]:
                raise SnapshotError("Pagination safety limit reached; snapshot incomplete")
            params = {"limit": cfg["retrieval"]["page_size"],
                      "archived": str(archived).lower(), "properties": ",".join(requested)}
            if cursor is not None:
                params["after"] = cursor
            response = reader.get("/crm/v3/objects/companies", params)
            results = response.get("results")
            if not isinstance(results, list):
                raise SnapshotError("Invalid company page; snapshot incomplete")
            for item in results:
                if (not isinstance(item, dict) or not isinstance(item.get("id"), str) or
                    not item["id"] or not isinstance(item.get("properties"), dict) or
                    item.get("archived") is not archived):
                    raise SnapshotError("Invalid company record or archived partition")
                if item["id"] in seen_ids:
                    raise SnapshotError("Repeated company ID during pagination; retry a fresh snapshot")
                seen_ids.add(item["id"])
                records.append(item)
            count += len(results)
            pages += 1
            paging = response.get("paging", {})
            if not isinstance(paging, dict):
                raise SnapshotError("Invalid pagination metadata")
            next_page = paging.get("next")
            if next_page is None:
                break
            if not isinstance(next_page, dict) or next_page.get("after") in (None, ""):
                raise SnapshotError("Missing next-page cursor")
            cursor = str(next_page["after"])
            if cursor in cursors:
                raise SnapshotError("Repeated pagination cursor")
            cursors.add(cursor)
        partitions["archived" if archived else "active"] = {
            "pages": pages, "records": count, "exhausted": True}
    snapshot = {"format_version": 1, "snapshot_id": uuid.uuid4().hex,
                "portal_id": str(cfg["portal_id"]), "started_at": started, "completed_at": now(),
                "status": "complete", "partitions": partitions, "properties": requested,
                "missing_optional_properties": optional, "property_validation": validation_report,
                "records": records, "records_sha256": digest(records)}
    snapshot["manifest_sha256"] = digest(snapshot)
    validate(snapshot, cfg)
    return snapshot

def validate(snapshot, cfg):
    if snapshot.get("status") != "complete" or snapshot.get("format_version") != 1:
        raise SnapshotError("Only a complete validated snapshot may be classified")
    manifest = dict(snapshot)
    checksum = manifest.pop("manifest_sha256", None)
    if checksum != digest(manifest):
        raise SnapshotError("Snapshot manifest checksum mismatch")
    if str(snapshot.get("portal_id")) != str(cfg.get("portal_id")) or not cfg.get("portal_id"):
        raise SnapshotError("Snapshot does not match configured account ID")
    records = snapshot.get("records")
    if not isinstance(records, list) or digest(records) != snapshot.get("records_sha256"):
        raise SnapshotError("Snapshot record checksum mismatch")
    required = set(cfg["required_properties"])
    if not required.issubset(snapshot.get("properties", [])):
        raise SnapshotError("Snapshot lacks required property coverage")
    ids = set()
    for r in records:
        if (not isinstance(r.get("id"), str) or not r["id"] or
            not isinstance(r.get("properties"), dict) or type(r.get("archived")) is not bool or r["id"] in ids):
            raise SnapshotError("Invalid or repeated snapshot record")
        ids.add(r["id"])
    for partition, archived in (("active", False), ("archived", True)):
        item = snapshot.get("partitions", {}).get(partition, {})
        if item.get("exhausted") is not True or item.get("pages", 0) < 1:
            raise SnapshotError("Both company partitions must be fully paginated")
        if item.get("records") != sum(r["archived"] is archived for r in records):
            raise SnapshotError("Partition count mismatch")
    try:
        start = datetime.fromisoformat(snapshot["started_at"])
        end = datetime.fromisoformat(snapshot["completed_at"])
        age = (datetime.now(timezone.utc) - end).total_seconds() / 3600
        if start > end or age < -0.01 or age > cfg["snapshot"]["max_age_hours"]:
            raise ValueError()
    except (ValueError, TypeError, KeyError):
        raise SnapshotError("Snapshot timestamps are invalid or stale") from None
    return snapshot

def save(snapshot, directory):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / ("companies_" + snapshot["snapshot_id"] + ".json")
    with path.open("x", encoding="utf-8") as handle:
        json.dump(snapshot, handle, ensure_ascii=False, indent=2)
    return path
