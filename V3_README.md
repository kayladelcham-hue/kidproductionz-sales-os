# V2 audit and V3 controlled company import

V3 is DISABLED by default in config/hubspot_import.json. No live HubSpot reads or writes were made while building these features. V2 matching and its GET-only client are unchanged.

## Architecture

- src/v2_audit.py reads a completed V2 summary and samples 10 NEW, 10 EXISTING and all REVIEW records reproducibly. It retains original lead fields, links all candidate evidence, and adds blank audit_decision and audit_notes fields.
- src/v3_plan.py creates exact company-property payload previews and an unapproved approval template. It accepts only NEW rows, enforces the pilot limit (10), and binds source rows, configuration and plan contents with checksums.
- src/v3_import.py controls approval, locking, fresh duplicate rechecks and durable local journals.
- src/v3_writer.py contains the only CRM POST code. It permits company creation at /crm/v3/objects/companies with a properties-only body. No PATCH, PUT, DELETE, batch, contact, deal, task or association operations are implemented.
- config/hubspot_import.json holds the disabled switch, pilot limit, separate create-token variable and source-to-HubSpot property mapping.

## Audit deliverable

audits/v2_audit_20260913T011707975314Z_e2fbb18e_7d0c8aee.csv contains 48 rows: 10 NEW, 10 EXISTING and 28 REVIEW. All 48 audit_decision cells are blank. Record your judgment in that column and supporting notes in audit_notes. Completing this file does not approve an import or change V2 classifications.

## Current dry-run deliverable

v3_imports/plan_978bdfa24b05bba1.json previews 10 NEW prospects with exact proposed properties. Its adjacent _approval.json file has approved=false. No companies were created.

The current offline snapshot confirms only the standard property names used by V2. Proposed payloads contain name, website where available, phone, address, city, state and zip. Score, grade, category, source/run identity and explanation remain in the plan and omitted_fields report because their configured custom targets are not present in that cached property list. This does not prove the custom properties are absent from the portal's full schema.

## Dry-run commands

From the project directory, recreate an offline preview with zero network calls:

```powershell
& "C:\Users\CJ\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -B src/v3_import.py --dry-run --summary "crm_checks/20260913T011707975314Z_e2fbb18e/summary_20260913T011707975314Z_e2fbb18e.json" --snapshot "hubspot_snapshots/companies_e79d527f5ad444649a28b56a327457b9.json"
```

To build a future preview against actual full property definitions, --dry-run --refresh-schema uses one explicit GET via the existing read-only credential. It creates no HubSpot properties or records. Review and configure property_map to use actual internal property names. Existing writable custom fields receive original source values; absent/read-only/incompatible enum fields are reported, never created or guessed.

## Future execution controls (not authorized or performed yet)

Live creation requires all of:
1. Explicit user approval of a concrete import plan.
2. enabled=true in config/hubspot_import.json.
3. An approval JSON containing approved=true, a nonblank approved_by, the exact plan_sha256, portal_id and ordered lead_ids.
4. Explicit --execute with --plan and --approval paths.
5. The existing read-only credential plus a separate HUBSPOT_COMPANY_CREATE_TOKEN configured for the intended account and company creation only. This project does not create keys or add scopes. Confirm both credentials belong to the approved portal.
6. Unchanged source rows, plan checksum and property mapping, and a selection no larger than pilot_limit.

Before each attempted create, V3 checks current writable property definitions, then retrieves a NEW complete active-and-archived snapshot through V2. The unchanged V2 matcher must still classify the prospect NEW. EXISTING and REVIEW results are skipped and logged. Retrieval failure, payload changes requiring reapproval, or stale recheck blocks the create. Skipped leads are not replaced by extra leads beyond the approved pilot selection.

Successful creations in this and prior local runs are included in subsequent comparisons if the API snapshot does not show them yet, reducing the risk from delayed CRM visibility.

## Logging and recovery

v3_imports/import_journal.jsonl records each attempt BEFORE POST with source/run identity, original metadata, approved payload and recheck snapshot ID. The CREATED event records the resulting HubSpot company ID. Writes are sequential and fsynced to local storage. A local execution lock prevents concurrent runs in the same workspace.

No create POST is automatically retried. A transport error, malformed success response or crash can leave an uncertain outcome; further imports stop until that outcome is reconciled. A prior attempted source row cannot be automatically submitted again. A crash may leave execution.lock; inspect journal and CRM state before manually resolving it. Never blindly remove a lock or retry an uncertain POST.

## Limitations

- A duplicate read followed by creation is not an atomic HubSpot transaction. Another integration could create a company in the intervening interval.
- Fresh full snapshots before every write favor caution and can be slow or consume API quota.
- The original saved snapshot used for dry-run is not used as a live duplicate check.
- Company creation can activate existing HubSpot account workflows. This code itself never requests contacts, deals, tasks or associations; it cannot govern portal automations.
- The audit sample is a review aid, not statistical certification of all 198 NEW records.
- Local plans and journals retain business data and are excluded from version control.
- V1.1 scores/grades, V2 match rules and past source/output files remain unchanged.

## Verification

131 local tests passed after implementation, including audit sampling, NEW-only eligibility, approval/disabled gates, per-write refresh, ambiguous/existing skips, incomplete snapshots, pilot limits, dry-run zero writes, property preservation, secret redaction, create-only endpoints and uncertain-outcome retry prevention.
