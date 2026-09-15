# KidProductionz Lead Automation V1.1

Local Python 3.10+ processing for Outscraper CSV/XLSX. No HubSpot, CRM, scraping or network integration. Source files are never moved, modified or overwritten.

## Run on this computer

Place your exports in `incoming/`, then open PowerShell in this project and run:

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1
```

The launcher uses `.venv` when present, otherwise this computer's bundled Codex Python. Python is not currently available on PATH. For a portable setup with Python 3.10+ installed:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe src/process_leads.py
```

Explicit inputs: `python src/process_leads.py "C:\Exports\salons.csv" "C:\Exports\beauty.xlsx"`

Custom configuration: `python src/process_leads.py --config config/ideal_client_profile.json`

Tests: `python -m unittest discover -s tests -v`

## Outputs

- `processed/`: qualified CSV, score >=65 without a review or rejection override.
- `review/`: score 50â€“64, ambiguous chains, uncertain duplicates, unknown city/state, and unclassified categories.
- `rejected/`: hard exclusions, exact duplicates, and remaining scores below 50. Nothing is deleted.
- `logs/`: run counts, source SHA-256 hashes, output paths and the full configuration snapshot. Errors are logged when possible.

Each CSV includes original cells as JSON, source path/sheet/row, normalized data, score, grade, explanations for every scoring rule, flags, duplicate references and queue reasons. Grades reflect score; overrides control the actual queue. All output filenames are unique and created exclusively.

All inputs are parsed before exports start. Invalid files fail the batch rather than silently skipping rows. Inputs support UTF-8/BOM and Windows-1252 CSV with comma, semicolon or tab delimiters, and every nonempty XLSX sheet with unique headers in row 1. Formulas are not evaluated. Other formats must be converted.

Spreadsheet-sensitive strings are prefixed with an apostrophe in exported CSVs, including +1 phones, to prevent formula execution. Strip this protective prefix only in a trusted downstream system if necessary. Original values remain inside the JSON field.

## Configuration

All markets, category aliases, priorities, weights, penalties, exclusions and thresholds are in `config/ideal_client_profile.json`. Orlando is enabled. Set `markets.atlanta.enabled` to `true` to activate Atlanta; review its starting city list first.

City plus state determines service-area eligibility. Missing either routes to review; a ZIP never substitutes for city/state. ZIP is retained as supporting data; `supporting_zip_codes` is reference-only. There is no geocoding or guessing city from full_address.

Primary category +30 OR secondary +15 (never both); active area +15; one usable contact path +8; website +6; social +4; rating >=4 +8; reviews >=20 +8; supported independent/local ownership +10; supported visual opportunity +7; named contact +4. Positive maximum is 100. Penalties remain likely chain -35, outside area -30, no contact -25. Scores are clamped to 0–100 with raw scores retained.

Primary auto-qualification requires score >=65, active city/state, usable contact, rating >=4, reviews >=20 and no closure, exclusion, unresolved chain concern or credible duplicate conflict. High-scoring primary leads that fail a reputation gate remain in review with an explicit reason. Missing ownership, visual and named-contact evidence earns zero but does not block qualification. The common category/location/phone/website/rating/reviews profile now scores 75; without the website it scores 69. Thresholds remain 80/65/50.

Usable contact earns points once across phone, website, email, social and business-specific booking/contact URLs. The booking_appointment_link export column is now mapped. URLs are syntax-validated and directory links and generic social/booking homepages are excluded; reachability is not verified. owner_title is not mapped as a person or ownership signal. Barber shops remain unclassified unless categories are explicitly configured later.

80â€“100 A / Hot; 65â€“79 B / Qualified; 50â€“64 C / Review; below 50 Reject/Hold. Explicit exclusions take precedence: permanently or temporarily closed, outside active markets, excluded categories, no usable contact path. Each exclusion can be disabled in JSON.

Category matching uses whole phrases in category/type/subtypes. Unknown categories go to review. Food/drink and other creative local businesses require visual evidence for secondary points. Excluded categories override target matches. Add terms to the excluded list to mark clearly irrelevant categories.

## Evidence and chains

Ownership and creative opportunity are not invented from sparse exports. Optional enrichment columns:
- `ownership`: e.g. `locally owned` or `owner operated`, plus `ownership_evidence`: supporting note/source.
- `visual_opportunity`: `yes`, plus `visual_evidence`: supporting note/source.
- `owner_name` or `contact_name`: a named person.
- `instagram`, `facebook`, `tiktok`, `booking_url`, `email`: additional contact paths.

Column aliases and accepted affirmative/ownership values are configurable. Evidence is user-supplied and is not verified online. The absence of a chain match never awards independence points. Chain names/domains are a heuristic list, not an exhaustive registry. V1.1 adds observed brand signals including Hair Cuttery, Floyd's 99 Barbershop and Sally Beauty. Salon Lofts is configured separately as a shared platform: operator-name patterns trigger chain concern; distinct stylist names using its domain or location pages receive SHARED_PLATFORM_TENANT, not a chain label. Platform patterns and brand vocabulary are configurable. Tenant classification is not proof of independent ownership. `LIKELY_CHAIN` receives -35 and review, even below 50. Supported local/independent ownership can waive that penalty and chain-only review override. Hard exclusions still apply.

Social links do not also earn website points. Directory links do not count as contact. Configured booking links count as contact without website points. US phone normalization does not verify reachability.

## Duplicates and reruns

Matching place IDs are strong exact-duplicate evidence. Matching normalized name and full address/city/state is exact only without conflicting populated place IDs. Conflicting IDs with corroborating identity/location evidence go to review. The best non-excluded/non-review copy is preferred, then highest score.

Shared domains and phone numbers alone create nonblocking relationship flags. Distinct locations and suites remain separate. Fuzzy names require corroborating compatible address, phone, or the same business-specific URL (with location checks); name similarity alone cannot block qualification. Shared phones plus full addresses retain review for possible rebranding/conflicting listings.

Exports include duplicate_matches and relationship_matches JSON with counterpart ID, name, place ID, address, website, source row and exact evidence codes. duplicate_of is reserved for identity conflicts. Suites and URL paths are preserved. chain_evidence and platform_evidence explain brand decisions; contact_paths and qualification_reason explain qualification.

Each default run scans all exports still in incoming and deduplicates across them. There is no persistent cross-run database: explicitly selected subsets only deduplicate against each other. Reruns create new output sets; they never append to earlier outputs. Pairwise duplicate comparison can be slow for very large exports.

The supplied .gitignore excludes business data and run outputs. Tests use synthetic fixtures in temporary directories and do not populate your incoming folder.
