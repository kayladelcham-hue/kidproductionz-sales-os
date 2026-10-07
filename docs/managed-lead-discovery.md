# Built-in lead discovery

Configure `KP_OUTSCRAPER_API_KEY` in the hosting service's secret environment
settings. An existing server `OUTSCRAPER_API_KEY` is also supported, but the
dedicated key takes precedence. Personal integration keys are not read, changed,
or returned. No key is bundled into frontend assets.

Use the authenticated cloud deployment. Discovery requires a signed-in account
even when other local endpoints allow anonymous access. Existing CSRF protection
applies to searches and admin tier changes.

## Tiers

| Tier | Requested leads per calendar month (UTC) |
| --- | ---: |
| Beta (default) | 100 |
| Starter | 250 |
| Growth | 1,000 |
| Pro | 2,500 |

These are usage allowances, not paid subscription plans. No checkout or automatic
billing is introduced. Override amounts with the environment variables shown in
`.env.example`. Only admins can assign a tier via
`PUT /api/admin/discovery/users/{user_id}/tier` with `{"tier":"growth"}` and their
authenticated session/CSRF header. Assignments persist in the shared database.

## Shared monthly budget

`DISCOVERY_MONTHLY_BUDGET_USD=50` limits reserved estimated costs across all users.
`DISCOVERY_COST_MICROS_PER_RECORD=3000` reserves $0.003 per requested Google Maps
record, ignoring the vendor's free tier and volume discounts conservatively.
This is an application estimate, not a guarantee about Outscraper's invoice.
Review the provider's current pricing and configure prepaid credits/provider
limits separately if a hard cash ceiling is required. No credits are purchased
by this change. Extra enrichment services are not requested by this integration.

Reservations are atomic database transactions, retained even after provider
timeouts or other uncertain failures because the provider may have processed
the request. Failed quota checks roll back both user and shared reservations.
Requests are limited to 100 records. Every fresh preview or search consumes its
requested count, regardless of how many qualified results are returned.

Successful searches are cached privately per account and query for 15 minutes.
Confirming a matching preview within that interval reuses the result without
another provider call or reservation. Expired previews perform a fresh search
and are subject to remaining allowance. Concurrent fresh requests can each
reserve allowance; the shared/user limits still cannot be exceeded.

Usage is stored in `managed_discovery_usage` and cache in
`managed_discovery_cache`, created by normal database initialization. Periods
reset automatically by UTC month. SQLite and PostgreSQL are supported.

## Activation

Merge/deploy the change, configure the server key and environment limits, and
restart the service. Users see their tier and remaining allowance in Settings
and Find Leads. Without the server key, the app displays an unavailable message
and does not send a discovery request. Existing personal keys can remain in the
database, but are unused; the old key-save endpoint returns HTTP 410.
