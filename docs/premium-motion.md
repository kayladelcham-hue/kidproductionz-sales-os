# Premium sales experience

The homepage retains its original Sales overview header, blue/purple banner and colorful metric cards at the top. The banner’s dominant Start selling action leads into the improved selling flow. Today’s saved mission and the highest-ranked eligible lead follow the metric cards; pipeline breakdown, planning tools, and calendar are disclosed on request. The KP logo, Bebas Neue display type, Skye, account data, integrations, and existing workflows remain in place.

## Motion contract

- Controls: 150 ms; tactile press, visible focus, honest disabled and saving states.
- Page entrance: 300 ms. Cards and panels: 280–360 ms. Mission progress: 350 ms.
- Grouped dashboard cards: 60 ms stagger. The original heading and selling action enter first; the mission and recommended lead follow the colorful metrics.
- Surface spring: sampled damped oscillator, mass 1, stiffness 320, damping 27; modest overshoot. A cubic-bezier fallback supports older engines.
- Transform and opacity carry entrances and confirmations; color communicates selection. No ambient animation loops or confetti. No animation delays a request, enables a control, or schedules a data mutation.
- A successful contact moves an inert, transient visual copy forward while the next real lead appears immediately. The visual contains no IDs and never intercepts input. Failed requests retain the original lead.
- Saved opportunity stage changes update the real pipeline destination, announce confirmation, highlight the moved card, and focus the next-action field. The opportunity editor exposes existing notes, timeline, consultation and value controls.
- Reduced motion removes entrances, spring transforms, hover travel, and progress transitions; text and destination confirmations remain.
- Dialogs trap focus, disable background interaction, support Escape and restore the trigger. Nested contact details suspend the opportunity dialog’s keyboard handling.

## Validation, October 5, 2026

- Production Vite build passed.
- TypeScript passed with React 19.3 type definitions supplied in an isolated validation directory. Those definitions are now explicit frontend development dependencies, with a `typecheck` script.
- 38 regression tests passed across lifecycle, momentum, sales hub and beta readiness. Tests use isolated databases.
- Isolated synthetic preview API checks passed: dashboard sources return 200, recording a contact persists CONTACTED and increments today’s mission, and moving a deal to PROPOSAL preserves its next action.
- No production leads, contacts, opportunities, credentials, or integration settings were modified during testing.

### Remaining release checks

Browser verification was blocked twice because the admin-enforced browser security policy could not be verified. No alternative browser mechanism was used to bypass that restriction. Desktop/mobile screenshots, scrolling, interactive focus behavior, reduced-motion rendering, and frame pacing still require browser verification. A 60 fps result has not been measured. Do not mark this revision production-ready or deploy it solely on the strength of build/API tests.
