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
