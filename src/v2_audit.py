"""Offline, reproducible human review sampling; no HubSpot access."""
import argparse
from collections import defaultdict
import csv
import hashlib
import json
from pathlib import Path
import random
import uuid
from export import safe_cell

ROOT = Path(__file__).resolve().parents[1]

def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        rows = list(reader)
    if not fields or len(fields) != len(set(fields)) or any(None in r or None in r.values() for r in rows):
        raise ValueError("Malformed CSV")
    return fields, rows

def load_run(path):
    if "_incomplete" in str(path.parent):
        raise ValueError("Cannot use an incomplete V2 run")
    summary = json.loads(path.read_text(encoding="utf-8-sig"))
    groups, ids = {}, set()
    for status in ("NEW", "EXISTING", "REVIEW"):
        output = Path(summary["outputs"][status])
        if not output.exists():
            output = path.parent / output.name
        _, rows = read_csv(output)
        if len(rows) != summary["counts"][status]:
            raise ValueError("V2 count mismatch")
        for row in rows:
            if row["crm_status"] != status or row["lead_id"] in ids or row.get("queue") != "qualified":
                raise ValueError("V2 status, qualification or identity mismatch")
            ids.add(row["lead_id"])
        groups[status] = rows
    return summary, groups

def audit(summary_path, output_root, seed="kidproductionz-v2-audit-1"):
    summary, groups = load_run(summary_path)
    candidates_path = Path(summary["outputs"]["candidates"])
    if not candidates_path.exists():
        candidates_path = summary_path.parent / candidates_path.name
    _, candidates = read_csv(candidates_path)
    by_lead = defaultdict(list)
    for candidate in candidates:
        by_lead[candidate["lead_id"]].append(candidate)
    sample = []
    for status in ("NEW", "EXISTING", "REVIEW"):
        rows = sorted(groups[status], key=lambda r: r["lead_id"])
        if status != "REVIEW":
            random.Random(seed + summary["run_id"] + status).shuffle(rows)
            rows = rows[:10]
        for row in rows:
            sample.append({**row, "audit_v2_run_id": summary["run_id"],
                           "hubspot_candidate_data": json.dumps(by_lead[row["lead_id"]], ensure_ascii=False),
                           "audit_decision": "", "audit_notes": ""})
    folder = output_root / "audits"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / ("v2_audit_" + summary["run_id"] + "_" + uuid.uuid4().hex[:8] + ".csv")
    fields = list(sample[0]) if sample else ["audit_decision", "audit_notes"]
    with path.open("x", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        # Original V2 cells already have CSV protection; do not escape twice.
        writer.writerows(sample)
    return {"output": str(path.resolve()), "count": len(sample),
            "sample_counts": {k: sum(r["crm_status"] == k for r in sample) for k in groups},
            "seed": seed, "v2_run_id": summary["run_id"]}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary", type=Path)
    parser.add_argument("--output-root", type=Path, default=ROOT)
    args = parser.parse_args()
    print(json.dumps(audit(args.summary, args.output_root), indent=2))
