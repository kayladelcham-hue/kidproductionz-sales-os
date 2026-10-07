# Beginner discovery workflow

The main journey is: tell us what you sell → find potential customers → decide who looks worth contacting.

Skye guides three short questions across four setup screens including search confirmation, offers examples and “Help me figure this out,” and shows an editable plain-language search summary. Advanced provider criteria stay under More search options. Searches use confirmed industry, city, and state; they are never automatically broadened. The product/service answer is saved to the existing ideal-customer profile, not submitted as an invented provider criterion.

Results show recorded business type/location, matching details, unverified contact paths, missing information, and previous decisions. Numeric conversion predictions are absent. A provider category inferred from the query is explicitly excluded from qualification evidence. Unsupported budget, company size, buying interest, and decision-maker details remain unknown. Existing profile exclusions remain part of the assessment.

Individual decisions are displayed as Looks like a fit / Not sure / Not a fit, while the underlying stored values remain QUALIFIED / NEEDS_RESEARCH / DISQUALIFIED. A choice saves immediately. Optional notes have an explicit Save my notes control. When no reason is typed, history records the user's selected decision rather than inventing an evidence-based explanation. Revision checks prevent conflicting updates. Undo restores the latest decision, reason, and notes without deleting a saved business or prior sales activity.

In the guided review, Looks like a fit saves the business automatically; in the full list/detail view, saving remains an explicit action. Existing records are reused by provider identity or name/location; campaign locking prevents concurrent duplicate inserts. Bulk saving accepts only independent fit decisions. Saved businesses offer website checks and a draft based only on the recorded business name and the user's stated offer. No communication is sent. Full sales records remain available under Advanced tools, fetched from the existing records API so qualification notes cannot accidentally overwrite existing sales notes.

Skye offers grounded fit/missing-information help inside business details and comparisons in its existing panel. Sources link to the business website/listing; website content and contact identity are not represented as verified. General sales chat continues through the existing AI integration. Its discovery explanations and basic first-message draft do not require an AI key.

## Data and deployment

- Additive SQLAlchemy tables: discovery_search, discovery_business, discovery_search_business, discovery_decision_event. The existing startup init_db/create_all creates them. No production database was changed during this work.
- Targeting preferences, searches, decisions, histories and saved links are owner scoped. Existing cloud authentication and CSRF middleware protect every route. Local desktop mode can still inspect its existing saved records/profile; managed provider searches require an authenticated cloud user.
- Search profile snapshots preserve the evidence criteria used by each search. Browser session storage retains result filters/search/scroll per owner and campaign. Business details open in a focus-trapped dialog and return to the prior scroll location.
- Begin outreach preserves existing statuses, notes, opportunities and activity while placing the saved prospect in the existing daily queue. The main contact page shows explicitly reviewed discovery businesses alongside existing ongoing conversations.
- This branch is stacked on feature/managed-lead-discovery (PR #10). Deploy that integration with this change and configure KP_OUTSCRAPER_API_KEY (or server OUTSCRAPER_API_KEY). The prior beta/starter/growth/pro quotas and $50 estimated monthly reservation cap remain in place. No credits were bought or real provider requests made.
- Repeated provider results retain the original captured listing and timestamp; they are not claimed to be refreshed. Cached provider results retain their actual fetch timestamp. Live website/decision-maker verification is separate research.
- An interrupted search older than three minutes reports a recoverable failure instead of polling forever. It keeps its criteria and warns that the original provider allowance may remain reserved.

## Verification evidence

Production Vite build passed (197 modules). The full targeted suite passed 61 tests, then the discovery suite passed 15 tests after adding interrupted-search recovery: 62 distinct tests verified across these runs.

Tests: test_discovery_workflow.py, test_icp_scoring.py, test_rescoring.py, test_managed_discovery.py, test_beta_readiness.py. These use isolated SQLite databases and synthetic provider responses only within test fixtures; production paths use the real provider integration. Verified target persistence; exact provider query; saved searches; empty/partial/failed results; duplicate removal; malformed/missing evidence; recorded versus inferred category; exclusions; decision/notes/history persistence; optimistic conflicts and latest-event undo; individual and bulk saves; concurrent duplicate prevention; legacy-record preservation; outreach queue integration; login/logout/relogin; CSRF enforcement; cross-owner isolation; grounded first-message drafting; existing local saved-record access.

Defined discovery text colors calculate above AA minimum: supporting text 9.26:1 dark / 8.18:1 light; primary button text at least 7.84:1 across existing theme accent colors. This is a palette calculation, not a verified whole-app accessibility audit. Forms use readable text, 44px minimum actions, visible focus, and responsive grids.

## Remaining verification and limitations

The local full app started on port 8004, but browser access was rejected because the browser could not verify its admin-enforced security policy. No workaround was attempted. Desktop/mobile rendering, text zoom, actual scroll restoration, keyboard focus behavior, navigation overlap and both themes therefore remain unverified in a browser. No screenshots or full browser success claim are provided.

The reused local frontend dependencies do not include TypeScript/type declarations, so a full TypeScript check was unavailable; Vite syntax/bundling passed. Live Outscraper behavior and PostgreSQL concurrency have not been exercised. General Skye AI answers still depend on the existing configured model credentials. Contact details are not independently verified. Drafts are starting templates, not claims of personalized knowledge or buying interest. This change has not been merged or deployed to Render.

## Skye-guided review rounds

Skye now leads setup one question at a time (offer, business type, location, then editable confirmation). Setup drafts stay in owner-scoped browser session storage and do not overwrite the server profile until the search is confirmed. After a search, the primary view reviews up to five actual businesses one at a time. All three decisions count as progress; only Looks like a fit also saves a prospect. The UI waits for the backend response before moving on and offers a save retry after a partial failure. Latest-decision undo remains available; undo never deletes an existing saved record. Returning after reload skips already reviewed businesses using their persisted status. View all businesses retains the existing comparison, filters, details and bulk save tools.

Skye’s setup instructions are task-specific guidance. Her Walk me through this business action uses the real assessment and cited sources, with the current search’s profile snapshot; it does not require model credentials or send communications. Completion counts come from recorded decisions and saved links. Gentle card transitions respect reduced motion.

Latest verification: production Vite build and 64 targeted API tests passed. These verify backend support for the three-choice review/save/undo sequence and search-grounded Skye explanations, not full browser interaction. Browser security continues to block mobile/desktop visual and interaction verification; guided focus, motion, draft restoration and round progression remain unverified in a browser.

## Neon guided-flow styling

The supplied dashboard references inform layered teal-black panels, lime/cyan gradients, restrained glow, a four-stage tracker, and gentle stage/review entrances. Saved-decision feedback animates after the recorded action completes. Skye’s accent pulses briefly on entry rather than continuously. Hover/tap feedback, bright light-mode surfaces, existing KP theme accents and readable business/evidence typography are retained. Reduced-motion preferences disable decorative animation and transitions. The guided review module loads only when needed. No reference metrics, NFT artwork or invented business data were added.

Validation: production Vite build and git diff --check pass. Static palette calculations check the defined text/background pairs; these are not a full accessibility audit. Mobile/desktop screenshots, actual motion and keyboard behavior still require browser verification, which remains blocked by the browser’s policy check.

## Focus carousel

Home setup and guided review now use a centered active card with dimmed, blurred previews of adjacent stages or actual business records. Only the active card contains controls; previews are hidden from assistive technology and cannot receive pointer or keyboard focus. Existing Next/Back and decision controls advance the carousel after validation or persistence. Side previews are clipped to avoid horizontal overflow, with narrower peeks on mobile. The loading card retains the deck while fresh details load. Reduced-motion preferences disable the entry transitions.

Production build and git diff --check pass. These changes do not alter records or provider criteria. Actual mobile/desktop layout, blur rendering, focus and motion remain unverified because browser access is blocked.
