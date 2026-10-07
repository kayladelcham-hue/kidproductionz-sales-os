# KP / Skye UI makeover

The supplied mockup is the composition target: KP sidebar; centered condensed headline; cyan Skye mission strip; a sharp portrait business card between blurred, tilted real-record previews; separate three-choice decision dock; saved-business next step. No concept/demo businesses or production metrics were added.

## Implementation

- `WorkspaceShell.tsx` owns branded desktop/mobile navigation, campaign selection, headings, and skip link. Existing navigation handlers, authentication and page components remain connected.
- `FocusCarousel.tsx` owns a three-slot stage, including small visible mobile previews. Adjacent records/stages are inert and aria-hidden. Active content and navigation controls are interactive; arrow keys work when the carousel region itself has focus, without intercepting typing.
- `SkyeGuide.tsx` renders actual persisted mission progress. All three review decisions count.
- `BusinessHero.tsx` prioritizes a record-provided HTTP(S) logo; image failure falls back to a clearly labeled reusable industry illustration/icon. A separate luminous platform and halo support gentle floating motion. No listing photo is called a logo.
- `DesignSystem.css` is the sole appearance/shell/motion stylesheet. Fourteen historical theme/patch CSS files have been removed. `LegacyLayouts.css` contains migrated feature geometry in a lower-priority cascade layer, with theme declarations and `!important` removed. `scripts/consolidate_ui_layouts.py` reproducibly reads historical source from Git revision `5d49277`; it requires tinycss2 as a development tool.
- Shared surfaces, forms, readable business names, buttons, dialogs, saved records, contact tools, pipeline, calendar, settings, and Skye use the same dark/light tokens. Advanced tools remain secondary. Reduced-motion removes decorative animations and transitions.
- Skye's panel uses the same avatar/surfaces, focuses its input on opening, closes with Escape, restores focus, and avoids smooth scrolling under reduced motion. It loads lazily; messaging logic is unchanged.
- Existing decision/save/retry/undo handlers remain connected. No external communications are automatically sent.

## Verified

- Vite production build passes.
- 65 discovery/scoring/managed-discovery/beta backend tests pass: ownership, persistent criteria/decisions/notes, duplicates, empty/partial/failure recovery, save/undo and outreach handoff.
- Nine jsdom component checks pass: shell labels/navigation/skip link; inert carousel previews and click/keyboard navigation without intercepting inputs; real-logo priority and fallback; failed fit save staying on the current card; advancement only after successful save; undo returning to the previous record; all outcomes and actual completion counts; persisted dark/light theme toggles; Skye input focus and Escape closure.
- Stylesheets parse without declaration errors; runtime imports contain only the two canonical CSS files; migrated layout has no `!important` declarations.
- Calculated contrast for canonical flat text/surface pairs exceeds WCAG AA: lowest tested ratio 5.49:1 (light-mode links); dark muted text 9.70:1. This does not establish contrast on every rendered overlay or gradient.
- `git diff --check` passes.

Component checks use isolated synthetic test records only, never production data. To rerun, install jsdom 26 in a temporary tooling directory; bundle `tests/ui/makeover.tsx` with esbuild (`--bundle --platform=node --format=esm --define:import.meta.env='{}'`), then run `tests/ui/run-makeover.cjs` with the bundle path and `NODE_PATH` pointing at the tooling directory.

## Blocked / unverified

Browser selection was denied because the admin-enforced browser policy could not be verified. No workaround or alternative browser was used. Therefore actual desktop/mobile rendering, pixel comparison with the mockup, both themes visually, text zoom, long-name reflow, touch interaction, motion, dialog overlap and live reload behavior have not been browser-verified. Backend reload/persistence and component state checks are separate evidence.

Full TypeScript checking is blocked by missing React/React DOM declaration packages in the existing linked dependency installation. Vite compilation succeeds; this is not a claim of a clean full typecheck. The live Render deployment is not verified by these tests.

## Visual-first refinement from the October 7 screenshots

Home now moves search history, saved-search controls and advanced tools into a dialog; the main view keeps one visual carousel stage. Found/saved businesses use illustrated poster cards and three evidence tiles rather than text rows. Details retain full criteria, unknowns, contacts and sources in expandable research sections. The avatar image is absolutely bounded inside its fixed visual box to prevent intrinsic grid image sizing from overlapping its caption/title.

Pipeline now opens an actual populated stage when the initial stage is empty, displays industry avatars on deal cards, and uses a compact value header and empty state. Calendar's Today button has an explicit content-width minimum and cannot wrap into letters. Skye is a transparent floating avatar button with no permanent box or visible text label, an accessible name, keyboard focus ring and reduced-motion support. Contact session stats use a compact wrapping pill and a visible data-driven mission bar.

The production build and twelve DOM/component checks pass. The additional checks cover grounded evidence tiles, the secondary-tools dialog and Pipeline choosing the actual populated stage. Screenshot-based defects were inspected, but the corrected visual result still cannot be browser-verified under the administration policy.

## Beginner Home simplification

Removed the visible industry-avatar caption while retaining alt text that distinguishes generic artwork from a business logo. Home now uses a short headline, icon-led setup stages, Next/Search actions, shorter Skye prompts and concise Match/Contact/Missing tiles. Main gallery controls no longer expose result-status statistics, duplicate counts, active-filter descriptions, repeated tabs, reset controls or a disabled Save 0 button. Those details and filter controls remain in the secondary dialog; selected bulk-save controls appear only after selection. Search failures/partial-results notices stay visible. The launcher now uses its own kp-floating-skye class, transparent styling and a bottom-right mobile position above navigation, preventing legacy launcher rules from affecting it.

Build and twelve component checks pass. Actual live appearance remains unverified under the browser-policy block.

## Simple one-at-a-time review

Review now uses the same icon-led, short-copy treatment as Home: compact Skye/progress strip, image-first side previews with no repeated evidence paragraphs, three concise signal tiles and the existing three decisions. Long evidence remains under More info and Open details. Completion uses actual Reviewed/Saved counters and three next-step choices rather than a paragraph and repeated saved-business buttons. Save/undo/retry handlers and available research links/notes remain connected. Build and twelve component checks pass; live rendered comparison remains blocked.

## Compact Home header

The campaign selector no longer occupies Home's header. A small borderless navigation icon opens Menu, where the same real campaign selector remains wired to campaign switching. Other pages retain their campaign selector. The navigation panel removes redundant headings. Build and thirteen component checks pass, including selecting another campaign through Menu. Actual layout remains unverified in a browser.

## Contact quest and action sizing

Replaced the stacked contact session/mission/Power Hour panels with ContactMission: one compact quest card, actual daily progress ring, backend target/reward, real session points and queue count, Skye art, trophy completion state and selectable focus sprint. Missing mission data displays unavailable instead of fabricated fallback targets/rewards. The existing local timer controls remain connected. After a saved contact, mission progress is refreshed from the backend.

Contact actions now have icon-led responsive sizing with normal word wrapping; on mobile Contact is full-width and the three shorter secondary actions form the next row. No communications are sent by the quest/timer; outreach controls retain their existing review flow. Build and fifteen component checks pass, including actual quest values, sprint handlers and missing-data honesty. Live layout remains blocked by browser policy.

## Saved carousel, customer cards, level graph, and useful tour (October 7)
- Saved discovery businesses and review-completion next steps share an actual-record carousel: one interactive business, inert neighboring previews, avatar and recorded evidence, keyboard/button navigation, and next-step action. Empty completed rounds no longer show a 0/0 mission.
- Customers use compact cards, short labeled contact links, distinct contracted/collected amounts, and collapsed history. Follow-up actions have consistent touch targets and short labels.
- Momentum uses real level thresholds and totals for an SVG checkpoint map; API failure shows retry instead of fabricated zero progress.
- The quick tour has four short nonmodal steps. It highlights and scrolls to real content, leaves the background sharp and interactive, supports Back/Next/Done/Escape, and cleans up highlights. No external communication occurs.
- Verification: production Vite build passed; 19 jsdom component checks passed, including actual saved-record carousel navigation/opening, failed-save/retry/undo, quest timer, level thresholds, tour navigation/highlight cleanup, customer financial labels/contact links/new-deal dialog.
- Rendered desktop/mobile, text zoom, visual contrast/overlap, and live deployment verification remain blocked: browser automation cannot verify the administrator-enforced policy. jsdom does not establish visual correctness or production reload persistence. Full TypeScript checking remains blocked by the existing missing React type declarations in the installed dependencies.
- Backend regression verification for this batch: 65 tests passed across discovery, scoring, rescoring, managed discovery, and beta readiness.
- Initial publication attempt was blocked: Git push cannot read a GitHub username; the GitHub connector's create_blob returns internal errors, and read calls expose inconsistent required repository parameter schemas. No new PR or deployment was created for this batch.

- Publication access restored after the user completed GitHub CLI authentication on October 7. The saved changes were pushed using Git; browser-rendered verification remains blocked.

## Skye launcher placement repair
- Corrected a misgrouped CSS selector that restricted the base floating launcher geometry to the detail-open body state. Skye now has unconditional fixed bottom-right positioning, with the existing mobile safe-area offset above navigation. Detail-open bottom navigation retains its own hide rule.
- Added a regression check that base launcher positioning does not depend on opening details. Existing standalone manifest and install guide already provide a browser-chrome-free app window on supported browsers.

## Manrope typography (October 7)
- Self-hosted the full Manrope variable font as a 53,936-byte WOFF2, compressed from Google Fonts’ licensed TTF without glyph or outline changes. Included upstream license and source/checksum documentation. Both app and install page preload the same-origin font; font-display: swap and system fallbacks keep text available.
- Updated existing shared declarations in place: 400/16px/1.5 body, 500/15–16px controls/navigation, 600/20–24px business names, and supporting labels at least 14px. Removed Arial/shorthand conflicts and global condensed h1/h2 styling; an explicit major-page-title whitelist retains KP Display. Reduced all-bold labels and selected uppercase section copy.
- Fonts use rem sizing, names retain break opportunities/min-width safeguards, timer controls reflow, and mission rings use relative sizing. Mobile nav shows Find and Deals with full accessible names retained. Colors, themes, avatars, data APIs, and actions are unchanged.
- Passed: production build; 20 existing component checks (including keyboard carousel navigation, long-name fixtures, themes, save/retry/undo, Skye focus/Escape); static typography/font contract; WOFF2 decoding, 400/500/600 axis coverage, representative long-name glyph coverage; production preview HTTP 200 with font/woff2 MIME and exact asset bytes, plus preload/install-page checks.
- Not completed: browser font activation/computed styles, rendered mobile/desktop long-name layout, 200% zoom, and live deployment checks. Browser access remains blocked because the administrator-enforced policy cannot be verified. Static/source and HTTP checks do not establish rendered appearance. The pre-existing installed React type declaration issue still blocks full TypeScript verification.
