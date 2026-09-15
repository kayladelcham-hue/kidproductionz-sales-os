"""KidProductionz Lead Automation v1.1. Local files only; no CRM integration."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import uuid

from ingest import read_rows
from normalize import normalize, key
from scoring import evaluate
from deduplicate import annotate
from export import write_csv

ROOT = Path(__file__).resolve().parents[1]

def load_config(path):
    cfg = json.loads(path.read_text(encoding="utf-8-sig"))
    if cfg["schema_version"] != 1:
        raise ValueError("Unsupported ICP schema_version")
    required_weights = {"primary_category", "secondary_category", "active_area", "independent", "usable_contact", "website", "social", "rating", "reviews", "visual", "named_contact"}
    required_penalties = {"likely_chain", "outside_area", "no_contact"}
    if set(cfg["weights"]) != required_weights or set(cfg["penalties"]) != required_penalties:
        raise ValueError("ICP must contain all supported scoring rules")
    if any(not isinstance(v, (int, float)) or v < 0 for v in cfg["weights"].values()):
        raise ValueError("Weights must be nonnegative numbers")
    if any(not isinstance(v, (int, float)) or v > 0 for v in cfg["penalties"].values()):
        raise ValueError("Penalties must be nonpositive numbers")
    t = cfg["thresholds"]
    if not 0 <= t["review"] < t["qualified"] <= t["hot"] <= 100:
        raise ValueError("Require 0 <= review < qualified <= hot <= 100")
    if not 0 <= t["rating"] <= 5 or t["reviews"] < 0:
        raise ValueError("Invalid rating or review threshold")
    if not 0 <= cfg["duplicates"]["fuzzy_name_ratio"] <= 1:
        raise ValueError("Invalid fuzzy name ratio")
    if cfg["categories"]["unknown_action"] not in ("review", "reject"):
        raise ValueError("unknown_action must be review or reject")
    if cfg["chains"]["ambiguous_action"] != "review":
        raise ValueError("v1 requires ambiguous chains to be reviewed")
    for rule in ("shared_domain_action", "shared_phone_action"):
        if cfg["duplicates"][rule] != "relationship":
            raise ValueError("V1.1 requires domain/phone-only matches to remain relationship flags")
    if not all(isinstance(v, bool) for v in cfg["primary_qualification"].values()):
        raise ValueError("Primary qualification gates must be booleans")
    if "owner_title" in cfg["column_aliases"]["owner"]:
        raise ValueError("owner_title is not named-contact evidence")

    for market in cfg["markets"].values():
        if not isinstance(market["enabled"], bool) or not market["state"] or not isinstance(market["cities"], list):
            raise ValueError("Markets require boolean enabled, state, and cities")
    return cfg

def run(inputs, config_path, output_root):
    cfg = load_config(config_path)
    files = sorted({p.resolve() for p in inputs}, key=lambda p: str(p).casefold())
    if not files:
        raise ValueError("No CSV/XLSX inputs found. Add exports to incoming/.")
    leads, manifest = [], []
    for path in files:
        rows = list(read_rows(path))
        if not rows:
            raise ValueError(f"No business rows found in {path.name}")
        for sheet, row_number, raw in rows:
            if not any(key(h) in {key(a) for a in cfg["column_aliases"]["name"]} for h in raw):
                raise ValueError(f"{path.name}/{sheet}: no recognized business-name column")
            lead = normalize(raw, cfg)
            lead.update(lead_id=f"L{len(leads)+1:07d}", source_file=str(path),
                        source_sheet=sheet, source_row=row_number)
            leads.append(evaluate(lead, cfg))
        manifest.append({"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "rows": len(rows)})
    annotate(leads, cfg)
    queues = {"qualified": [], "review": [], "rejected": []}
    for lead in leads:
        if lead["rejection_reasons"]:
            queue = "rejected"
        elif lead["review_reasons"]:
            queue = "review"
        elif lead["score"] >= cfg["thresholds"]["qualified"]:
            queue = "qualified"
        elif lead["score"] >= cfg["thresholds"]["review"]:
            queue = "review"
            lead["review_reasons"].append("SCORE_REVIEW_BAND")
        else:
            queue = "rejected"
            lead["rejection_reasons"].append("BELOW_REVIEW_THRESHOLD_HOLD")
        lead["queue"] = queue
        lead["rejection_reason"] = "; ".join(dict.fromkeys(lead["rejection_reasons"]))
        lead["review_reason"] = "; ".join(dict.fromkeys(lead["review_reasons"]))
        lead["flags"] = "; ".join(dict.fromkeys(lead["flags"]))
        lead["qualification_reason"] = ("PRIMARY_CRITERIA_MET" if lead["category_tier"] == "primary" else "SECONDARY_SCORE_AND_EVIDENCE_MET") if queue == "qualified" else ""
        lead["platform_evidence"] = json.dumps(lead.get("platform_evidence", []), ensure_ascii=False)

        queues[queue].append(lead)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "_" + uuid.uuid4().hex[:8]
    summary = {"version": cfg["version"], "run_id": run_id, "inputs": manifest, "total_rows": len(leads),
               "counts": {k: len(v) for k, v in queues.items()}, "outputs": {},
               "config": cfg, "warnings": ["Contact paths are syntax-validated, not checked online. Ownership and visual awards require explicit evidence. Chain/platform rules are heuristic, not exhaustive. Shared-domain/phone relationships do not block qualification."]}
    created = []
    try:
        for queue, directory in (("qualified", "processed"), ("review", "review"), ("rejected", "rejected")):
            folder = output_root / directory
            folder.mkdir(parents=True, exist_ok=True)
            output = folder / f"{queue}_leads_{run_id}.csv"
            write_csv(output, queues[queue])
            created.append(output)
            summary["outputs"][queue] = str(output.resolve())
        log_dir = output_root / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        with (log_dir / f"run_{run_id}.json").open("x", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2, ensure_ascii=False)
    except Exception:
        print(f"Output failed; partial files retained: {[str(p) for p in created]}", file=sys.stderr)
        raise
    return summary

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*", type=Path, help="Explicit CSV/XLSX paths; default: all incoming files")
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "ideal_client_profile.json")
    parser.add_argument("--output-root", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        inputs = args.files or [p for p in (ROOT / "incoming").iterdir() if p.is_file() and p.suffix.lower() in (".csv", ".xlsx") and not p.name.startswith("~$")]
        summary = run(inputs, args.config, args.output_root)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        try:
            folder = args.output_root / "logs"
            folder.mkdir(parents=True, exist_ok=True)
            with (folder / f"error_{uuid.uuid4().hex}.json").open("x", encoding="utf-8") as handle:
                json.dump({"error": str(exc), "inputs": [str(p) for p in args.files]}, handle, indent=2)
        except OSError:
            pass
        return 1
    print(json.dumps({k: summary[k] for k in ("run_id", "counts", "outputs")}, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
