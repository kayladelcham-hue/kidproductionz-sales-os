"""Exclusive output creation with spreadsheet formula-injection protection."""
import csv

FIELDS = [
    "lead_id", "source_file", "source_sheet", "source_row", "name", "phone",
    "website", "social", "email", "other_contact", "category", "normalized_category",
    "address", "city", "state", "zip", "place_id", "market", "rating", "reviews",
    "owner", "ownership", "ownership_evidence", "visual", "visual_evidence",
    "status", "score", "raw_score", "grade", "queue", "score_explanation", "flags",
    "duplicate_of", "duplicate_matches", "relationship_matches", "chain_evidence",
    "platform_evidence", "category_tier", "contact_paths", "qualification_reason",
    "rejection_reason", "review_reason", "original_data"
]

def safe_cell(value):
    value = "" if value is None else str(value)
    if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")):
        return "'" + value
    return value

def write_csv(path, leads):
    with path.open("x", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for lead in leads:
            writer.writerow({field: safe_cell(lead.get(field)) for field in FIELDS})
