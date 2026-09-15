# V2: read-only HubSpot company comparison

V2 consumes a specific V1.1 qualified CSV. It never recalculates or changes V1.1 scores, grades, explanations or qualification decisions. Its outputs append separate CRM classifications. No live connection has been performed during implementation.

## First live run: requires Kayla's explicit approval

Do not run the live command until the first live read-only comparison has been approved.

1. Edit config/hubspot_matching.json: replace portal_id: null with your intended HubSpot account ID as a string. The account ID is configured, not independently verified through an extra account endpoint.
2. Prepare a dedicated token limited to crm.objects.companies.read and crm.schemas.companies.read. Give it company visibility sufficient to read the intended whole account. Do not add any write, import, merge, contact, deal, or sensitive-data scopes.
3. Set the token only in the current PowerShell session. Do not put it in JSON, source code, a command-line argument or a saved report.

```powershell
$taskSecret = Read-Host 'HubSpot read-only token' -AsSecureString
$env:HUBSPOT_READONLY_TOKEN = [System.Net.NetworkCredential]::new('', $taskSecret).Password
```

After approval, the exact command for the current 272 qualified leads is:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Users\CJ\Documents\ChatGPT\Kid Productionz Lead Automation\run_hubspot.ps1" "C:\Users\CJ\Documents\ChatGPT\Kid Productionz Lead Automation\processed\qualified_leads_20260912T235447927192Z_d7bb8a99.csv" --live
```

Remove the process environment token after the run:

```powershell
Remove-Item Env:\HUBSPOT_READONLY_TOKEN
```

The launcher uses the project virtual environment if present, otherwise the existing bundled Python. V2 introduces no new package dependency.

## Offline replay

An already validated snapshot can be compared without a network call:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\run_hubspot.ps1 .\processed\qualified_leads_<run>.csv --snapshot .\hubspot_snapshots\companies_<snapshot-id>.json
```

Offline replay requires the snapshot account ID to match configuration and a snapshot age of at most 24 hours by default. Missing, malformed, modified, stale or incomplete snapshots fail validation. --live and --snapshot are mutually exclusive; no mode defaults to live.

## Modules

- src/hubspot_client.py: allowlisted GET-only client, official host restriction, redirects disabled, bounded retries for 429/transient server failures. Only the company listing and company-property listing endpoints are allowed.
- src/hubspot_snapshot.py: property validation, every active and archived page, duplicate-ID/cursor checks, checksums, timestamps and coverage validation.
- src/crm_normalize.py: matching-only normalization of names, legal suffixes, domains, additional domains, phone, street/suite, city/state and platform roles.
- src/crm_match.py: identifier indexes, candidate discovery, evidence rules and NEW/EXISTING/REVIEW decisions.
- src/check_hubspot.py: explicit live/offline entry point, qualified-input validation and local exports.
- tests/test_hubspot_v2.py: mocked API tests; no live HubSpot access.

## Match confidence

Confidence measures rule strength, not statistical probability. Use the strongest applicable rule, without adding correlated evidence:
- 95: exact distinctive normalized name plus complete matching address, or nonshared domain + nonshared phone + name similarity >=0.92.
- 90: nonshared domain + exact distinctive name + city/state, or fuzzy name + phone + full address.
- 70: nonshared domain alone, or exact name + city/state.
- 55: phone, full address, or a potentially related shared business identifier.
- 40: distinctive fuzzy name alone.
- 0: no credible evidence. An unrelated tenant using the same shared platform alone is not a credible match.

EXISTING requires >=90 with no blocking ambiguity, archived candidate, material location/suite conflict, weak identity or competing candidate >=70. Fuzzy names and shared identifiers alone never suffice. Shared identifiers can coexist with independent full name/address evidence; they do not themselves establish identity.

REVIEW includes possible/ambiguous matches, archived matches, different-location brand matches, incomplete suite details, weak prospect identity and operator/tenant conflicts. Candidate IDs and evidence are retained; no arbitrary winner is selected for REVIEW.

NEW requires no candidate >=40, sufficient business-specific identity and a fully validated snapshot. It is not permission to import. Snapshot retrieval failure produces no finalized classification report.

## Snapshot and output contract

Snapshot files go to hubspot_snapshots/. Reports go to crm_checks/<timestamp-and-run-id>/. Outputs are new_leads_<run>.csv, existing_leads_<run>.csv, review_leads_<run>.csv, match_candidates_<run>.csv and summary_<run>.json. Each snapshot includes the exact record set, properties, active/archived counts, page exhaustion, timestamps and checksums.

Each prospect retains all V1.1 columns exactly as read. Added fields include crm_status, match_confidence, matched_hubspot_id, candidate_hubspot_ids, matched_company_name, match_rule, review_reason_crm, match_evidence, conflicting_evidence, snapshot_id and checked_at. CRM match evidence shows normalized values from both sides. The candidate file includes raw selected HubSpot properties, record IDs, archived status and conflicts.

Output writing uses a uniquely named _incomplete directory until every report is written, then finalizes the directory name. A failure may leave a local _incomplete directory; never use its files for import decisions. Original files and past outputs are never overwritten.

## Limitations

- HubSpot pagination is not a transactional point-in-time snapshot. Concurrent CRM changes can affect results; duplicate IDs/cursors abort retrieval, but not every concurrent change is detectable.
- Completeness covers API-visible companies and successful exhaustion of both partitions; token permissions and the intended portal must be configured correctly.
- Checksums detect local corruption, not malicious fabrication of a snapshot.
- Names, addresses and platform patterns are heuristic. Unrecognized address formats may conservatively route to review. Additional platforms can be configured.
- Domain normalization folds known corporate subdomains only; it deliberately does not collapse arbitrary tenant subdomains.
- Missing optional properties are reported. Required property definitions must be available; empty individual values remain unknown.
- Candidate name discovery scans distinct CRM names to avoid geographic blind spots; very large accounts may be slower.
- Token scope restrictions must be applied when the credential is issued. The code uses GET-only endpoints regardless; it does not introspect token grants.
- No contact reachability verification, geocoding, CRM edits, associations, merges, restores or imports occur.

## Local verification

```powershell
& "C:\Users\CJ\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -B -m unittest discover -s tests -v
```

## Service Key authentication diagnostics

HubSpot Service Keys use Bearer authentication in the Authorization header. The client now reads the exact configured token_env via HubSpotReader.from_environment; the CLI uses that entry point. Missing or blank values fail locally. Surrounding whitespace is trimmed; embedded whitespace, quotes and a pasted Bearer prefix are rejected without echoing the credential. There is no credential fallback to another environment variable.

Every schema/company GET, page and retry constructs an Authorization header and checks its presence before transport. Console and error diagnostics show only authorization_header_present (boolean), never the header value. A true value proves local request construction, not that an intermediary forwarded it or that HubSpot accepted the key. Key length alone does not prove credential validity. No authentication-method change, scope change or live verification was performed for this diagnostic update.
