# SQLite schema snapshot

Source: read-only byte-for-byte copy `tmp/schema_db_copy.db`; schema metadata only.

## Tables

- `app_setting`: key TEXT PRIMARY KEY NOT NULL; value TEXT NOT NULL.
- `calendar_event`: id INTEGER PRIMARY KEY; prospect_id INTEGER NOT NULL; provider TEXT NOT NULL; calendar_event_id TEXT; event_url TEXT; consultation_start TEXT; consultation_end TEXT; created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP.
- `campaign`: id INTEGER PRIMARY KEY; slug TEXT UNIQUE NOT NULL; name TEXT NOT NULL; market TEXT; active INTEGER NOT NULL DEFAULT 1; config_ref TEXT; created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP; updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP; city TEXT; state TEXT; category TEXT; description TEXT; daily_queue_limit INTEGER; status TEXT.
- `crm_state`: id INTEGER PRIMARY KEY; prospect_id INTEGER UNIQUE NOT NULL; sync_status TEXT; hubspot_contact_id TEXT; hubspot_company_id TEXT; hubspot_deal_id TEXT; association_verified INTEGER NOT NULL DEFAULT 0; last_synced_at TEXT; metadata TEXT.
- `email_activity`: id INTEGER PRIMARY KEY; prospect_id INTEGER NOT NULL; provider TEXT NOT NULL; provider_message_id TEXT; recipient TEXT; subject TEXT; sent_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP.
- `external_action`: id INTEGER PRIMARY KEY; prospect_id INTEGER NOT NULL; action_type TEXT NOT NULL; metadata TEXT; created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP.
- `google_connection`: id INTEGER PRIMARY KEY CHECK(id=1); access_token TEXT; refresh_token TEXT; expires_at REAL; scope TEXT; status TEXT NOT NULL DEFAULT 'NOT_CONNECTED'.
- `prospect`: id INTEGER PRIMARY KEY; campaign_id INTEGER NOT NULL; name TEXT NOT NULL; email TEXT; phone TEXT; website TEXT; social TEXT; category TEXT; normalized_category TEXT; address TEXT; city TEXT; state TEXT; zip TEXT; status TEXT; score REAL; raw_score REAL; grade TEXT; queue TEXT; ownership TEXT; research TEXT; created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP; updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP; sales_status TEXT NOT NULL DEFAULT 'NOT_CONTACTED'; notes TEXT; booked_value REAL; last_activity_at TEXT; contacted_at TEXT; replied_at TEXT; consultation_set_at TEXT; booked_at TEXT; external_key TEXT. Unique(campaign_id,name,email).
- `queue_item`: id INTEGER PRIMARY KEY; run_id INTEGER NOT NULL; prospect_id INTEGER NOT NULL; position INTEGER; priority TEXT; queue_type TEXT; status TEXT; created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP. Unique(run_id,prospect_id).
- `run`: id INTEGER PRIMARY KEY; campaign_id INTEGER NOT NULL; run_id TEXT UNIQUE NOT NULL; run_status TEXT; dry_run INTEGER NOT NULL DEFAULT 1; qualified_count INTEGER; daily_queue_count INTEGER; deferred_count INTEGER; research_count INTEGER; ineligible_count INTEGER; manifest_ref TEXT; queue_artifact_ref TEXT; started_at TEXT; completed_at TEXT; created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP.
- `upload`: id TEXT PRIMARY KEY; original_filename TEXT NOT NULL; stored_reference TEXT NOT NULL; file_type TEXT NOT NULL; size INTEGER NOT NULL; sheets TEXT; created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP; expires_at TEXT; status TEXT NOT NULL DEFAULT 'ACTIVE'.

## Constraints and indexes

Unique constraints: campaign.slug, crm_state.prospect_id, run.run_id, prospect(campaign_id,name,email), queue_item(run_id,prospect_id). Check constraint: google_connection.id=1. No foreign keys or additional indexes were reported by PRAGMA inspection.
