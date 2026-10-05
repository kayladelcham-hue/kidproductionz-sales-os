# Beta fixes — 5 October 2026

These changes close the anonymous static-file traversal, enforce active account sessions, isolate Google, HubSpot, booking and discovery settings, bind OAuth state to the requesting session, protect run artifacts and uploads, and repair campaign creation and upload persistence. Skye reads the canonical queue, follow-ups and metrics and uses deterministic recommendations for first-call requests.

Recovery codes are generated only after re-entering the current password, stored as hashes, consumed once, and revoke all account sessions on password reset. Login and recovery attempts are bounded per process. A multi-instance public rollout should use a shared rate-limit store.

Tests run against isolated synthetic databases and mocked external providers. No customer messages, calendar invitations or CRM writes are sent by these checks. Live provider round trips still require configured accounts and a user-approved test recipient.

The maintained SQLAlchemy database replaces a Python-version-dependent recovered bytecode loader. Dry-run persistence uses the same maintained account-scoped database. Migrations are additive.

Historical regression manifests were refreshed to the current source baseline: the existing state/category normalization and HubSpot changes had invalidated old milestones. Three refresh modules now resolve macOS temporary paths before computing relative paths. Manifest paths use forward slashes, and checksums reflect Git's current LF checkout. Behavior remains covered by scoring, matching, routing and refresh tests. Report/view tests now generate their reports from checked-in logical fixtures instead of depending on missing generated artifacts. Weekly progress expectations account for the Monday boundary.

Render billing must be resolved by the account owner. Production backup retention/restore and a real PostgreSQL concurrency/load test are separate operational release gates; a synthetic SQLite restore smoke test cannot establish production recovery guarantees.
