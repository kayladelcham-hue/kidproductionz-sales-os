"""V2 read-only comparison. Live GET access requires an explicit --live flag."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import uuid

from hubspot_client import HubSpotReader, ReadError
from hubspot_snapshot import retrieve, validate, save
from crm_normalize import identity
from crm_match import CompanyIndex, classify
from export import safe_cell

ROOT = Path(__file__).resolve().parents[1]
ADDED = ["crm_status", "match_confidence", "matched_hubspot_id", "candidate_hubspot_ids",
         "matched_company_name", "match_rule", "review_reason_crm", "match_evidence",
         "conflicting_evidence", "snapshot_id", "checked_at"]
CANDIDATE_FIELDS = ["lead_id", "hubspot_id", "hubspot_name", "archived", "confidence",
                    "rule", "name_similarity", "evidence", "conflicts", "hubspot_values"]

def load_config(path):
    cfg = json.loads(path.read_text(encoding="utf-8-sig"))
    if cfg["version"] != "2.0" or cfg["api_base"] != "https://api.hubapi.com":
        raise ValueError("Unsupported V2 configuration")
    t = cfg["thresholds"]
    if not (0 < t["review"] <= t["competing"] < t["existing"] <= 100 and 0 < t["name_similarity"] <= 1):
        raise ValueError("Invalid confidence thresholds")
    if not cfg["snapshot"]["include_archived"] or cfg["snapshot"]["max_age_hours"] <= 0:
        raise ValueError("A fresh snapshot including archived companies is required")
    if cfg["confidence"]["fuzzy_only"] >= t["existing"]:
        raise ValueError("Fuzzy-only matches cannot meet EXISTING threshold")
    if any(cfg["confidence"][k] >= t["existing"] for k in ("domain_only", "phone_only", "address_only", "shared_identifier", "name_city")):
        raise ValueError("Weak identifier rules cannot meet EXISTING threshold")
    r = cfg["retrieval"]
    if not 1 <= r["page_size"] <= 100 or not 0 <= r["max_retries"] <= 5 or r["max_pages_per_partition"] < 1 or r["timeout_seconds"] <= 0:
        raise ValueError("Invalid retrieval limits")
    if not set(cfg["required_properties"]).issubset(cfg["properties"]):
        raise ValueError("Required properties must be requested")
    return cfg

def read_qualified(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        if len(fields) != len(set(fields)) or not {"lead_id", "name", "score", "grade", "queue"}.issubset(fields):
            raise ValueError("Expected a V1.1 qualified-leads CSV with unique headers")
        if set(fields) & set(ADDED):
            raise ValueError("Input already contains V2 matching columns")
        rows = list(reader)
    if not rows:
        raise ValueError("Qualified input has no rows")
    ids = set()
    for row in rows:
        if None in row or any(v is None for v in row.values()):
            raise ValueError("Malformed CSV row")
        if row["queue"] != "qualified" or not row["lead_id"] or row["lead_id"] in ids:
            raise ValueError("Input must contain unique qualified prospect IDs only")
        ids.add(row["lead_id"])
    return fields, rows

def as_cell(value):
    return safe_cell(json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value)

def compare_snapshot(input_path, snapshot, cfg, output_root):
    # Completeness is checked here too, including on offline/replayed snapshots.
    validate(snapshot, cfg)
    fields, prospects = read_qualified(input_path)
    index = CompanyIndex(snapshot["records"], cfg)
    checked_at = datetime.now(timezone.utc).isoformat()
    groups = {"NEW": [], "EXISTING": [], "REVIEW": []}
    pair_rows = []
    for row in prospects:
        result = classify(identity(row, cfg), index, cfg)
        for pair in result.pop("candidates"):
            pair_rows.append({"lead_id": row["lead_id"], **pair})
        result.update(snapshot_id=snapshot["snapshot_id"], checked_at=checked_at)
        groups[result["crm_status"]].append({**row, **result})
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "_" + uuid.uuid4().hex[:8]
    checks = output_root / "crm_checks"
    checks.mkdir(parents=True, exist_ok=True)
    pending = checks / (run_id + "_incomplete")
    final = checks / run_id
    pending.mkdir()
    summary = {"version": "2.0", "run_id": run_id, "snapshot_id": snapshot["snapshot_id"],
               "portal_id": snapshot["portal_id"], "checked_at": checked_at,
               "input": str(input_path.resolve()),
               "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
               "counts": {k: len(v) for k, v in groups.items()},
               "snapshot_partitions": snapshot["partitions"],
               "snapshot_started_at": snapshot["started_at"], "snapshot_completed_at": snapshot["completed_at"],
               "config": cfg, "outputs": {},
               "warnings": [
                   "No CRM writes or import actions performed.",
                   "Snapshot covers API-visible companies; account ID is supplied by configuration.",
                   "Pagination is not a transactional snapshot; CRM changes during retrieval can affect coverage.",
                   "Matching confidence is rule strength, not a probability.",
                   "NEW means no credible match in this snapshot, not permission to import.",
                   "Property values and contact reachability are not verified online."
               ]}
    summary["missing_optional_properties"] = snapshot["missing_optional_properties"]
    for status, leads in groups.items():
        filename = status.lower() + "_leads_" + run_id + ".csv"
        with (pending / filename).open("x", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields + ADDED)
            writer.writeheader()
            for lead in leads:
                # V1.1 cells already carry CSV safety escaping: copy them exactly.
                writer.writerow({**{k: lead[k] for k in fields},
                                 **{k: as_cell(lead.get(k)) for k in ADDED}})
        summary["outputs"][status] = str((final / filename).resolve())
    filename = "match_candidates_" + run_id + ".csv"
    with (pending / filename).open("x", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CANDIDATE_FIELDS)
        writer.writeheader()
        for pair in pair_rows:
            writer.writerow({k: as_cell(pair.get(k)) for k in CANDIDATE_FIELDS})
    summary["outputs"]["candidates"] = str((final / filename).resolve())
    with (pending / ("summary_" + run_id + ".json")).open("x", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, ensure_ascii=False)
    # Only a fully written run receives a final directory name. No overwrite.
    if final.exists():
        raise FileExistsError("Final run directory already exists")
    pending.rename(final)
    return summary

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("qualified_csv", type=Path)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--snapshot", type=Path, help="Offline: validated local snapshot; no API access")
    source.add_argument("--live", action="store_true", help="Explicitly permit company/property GET requests")
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "hubspot_matching.json")
    parser.add_argument("--output-root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        cfg = load_config(args.config)
        read_qualified(args.qualified_csv)
        if args.live:
            if not cfg.get("portal_id"):
                raise ValueError("Set portal_id in hubspot_matching.json before a live run")
            snapshot = retrieve(HubSpotReader.from_environment(cfg), cfg)
            path = save(snapshot, args.output_root / "hubspot_snapshots")
            print("Complete snapshot saved: " + str(path))
        else:
            snapshot = json.loads(args.snapshot.read_text(encoding="utf-8-sig"))
        summary = compare_snapshot(args.qualified_csv, snapshot, cfg, args.output_root)
    except Exception as exc:
        if isinstance(exc, ReadError) and exc.diagnostic is not None:
            # Only the already-redacted diagnostic is persisted.
            try:
                folder = args.output_root / "logs"
                folder.mkdir(parents=True, exist_ok=True)
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                diagnostic_path = folder / ("hubspot_read_error_" + stamp + "_" + uuid.uuid4().hex[:8] + ".json")
                with diagnostic_path.open("x", encoding="utf-8") as handle:
                    json.dump(exc.diagnostic, handle, ensure_ascii=True, indent=2)
                print("Redacted HubSpot diagnostic saved: " + str(diagnostic_path), file=sys.stderr)
            except OSError:
                print("Could not save diagnostic file; redacted diagnostic follows.", file=sys.stderr)
        print(f"V2 FAILED: {exc}. No finalized results should be used from an incomplete run.", file=sys.stderr)
        return 1
    print(json.dumps({k: summary[k] for k in ("run_id", "counts", "outputs")}, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
