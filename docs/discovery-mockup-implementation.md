# October 8 discovery mockup implementation

The attached two-phone mockup is the visual target. The implementation uses actual records; Juniper Café and other mockup businesses are not added to production.

## Composition and behavior

- Compact KP branding, profile control, Find customers heading, and actual review-progress dots. One sharp active card with inert, dimmed, blurred adjacent business previews. Responsive composition retains the existing condensed font for major titles and Manrope for all other text.
- `DiscoveryCard` has separately mounted front/back faces. Front: reliable recorded logo or reusable industry artwork, identity/location, no more than two recorded matches, actionable contact-information icons, and Tap to flip. Back: thumbnail, recorded reasons, unknowns including unconfirmed buying interest, explicitly listed/unverified contact paths, source links, and expandable criteria, source freshness, notes, and Skye research. Alternate artwork has explicit accessible text distinguishing it from branding.
- Horizontal pointer gestures and focused-card keyboard choices call the same qualification handlers as the labeled X / question / lime check controls. Vertical/canceled gestures, interactive descendants, modifier keys, and pending-save states do not assign decisions. Buttons retain labels. Navigation arrows browse without qualifying. A fit awaits both decision persistence and saving; failed saves remain on the card with retry. Undo and actual reviewed/saved counts remain backed by existing APIs.
- Discover, Saved, and Profile are the primary navigation. Outreach, pipeline, calendar, settings, campaigns, and advanced tools remain in secondary navigation. Saved records reuse the flip card and preserve their existing detail/outreach actions.
- Profile reads/writes existing discovery target and ideal-customer APIs: offer, primary target industry, city and two-letter state. Other targeting characteristics, weights, secondary markets, and exclusions are retained. Partial two-API save failure is explicit and retryable. Profile help opens the existing Skye-led setup questions.
- Skye remains a transparent floating avatar above navigation; the focused discovery record feeds its context independently from requests to open a business detail. Discovery workspace bottom spacing reserves room for the launcher. Light mode uses contrasting controls/progress indicators; reduced motion removes card transitions and animations.

## Artwork

The built-in image_gen tool generated a reference-guided generic steaming coffee cup and cyan platform. It has no business name, branding, face, or logo. Its transparent RGBA PNG was losslessly converted to WebP; all RGBA pixels were verified identical. Existing artwork is retained alongside the versioned asset.

Final asset: `app/frontend/public/avatars/cafe-discovery-v2.webp` (1,050,164 bytes). The final built-in prompt is saved in `docs/hero-asset-prompts.json`, entry `cafe-discovery-v2`. The image was visually inspected against the illustration in the supplied reference; this does not verify the rendered app layout.

## Verification and exact limitations

- Production Vite build passed.
- 28 jsdom component checks passed: front highlight limits, face flipping, source/uncertainty display, collapsed research, horizontal swipes, vertical/canceled gestures, focused-card keyboard actions, form-input exclusion, pending-state guards, fit-save failure/retry/undo, actual completion totals, swipe-to-persistence integration, focus/Skye context publication, primary navigation, and profile preservation/partial-error handling. Existing theme and Skye focus/Escape checks also pass. Long-name fixtures are exercised functionally, not visually.
- 65 backend regression tests passed, including owner isolation, qualification/notes reload persistence, undo, duplicate-save prevention, outreach preparation, search failures/partial results, scoring, managed discovery, and beta readiness. These use isolated test databases, not production records.
- The typography/WOFF2 contract, canonical stylesheet parsing, and git diff whitespace checks passed. The new art's alpha and lossless pixel preservation were checked.
- Browser access was attempted against the existing app tab on October 8 and denied because the administrator-enforced security policy could not be verified. No alternate browser or indirect workaround was used. Therefore rendered desktop/mobile layout, physical-device swiping, 200% zoom, visual long-name wrapping, touch-target overlap, light-mode appearance, live reload persistence, and screenshot comparison to the mockup are **not verified**. No exact visual match is claimed.
- Existing discovery evidence does not provide independently verified contact identities or buying-interest data. Listed paths are explicitly unverified; unknown buying interest is retained. Service-area setup uses the backend's supported industry/city/two-letter-state criteria. No unsupported verification or geography controls were invented.
- The pre-existing missing installed React type declarations still block full TypeScript checking. Vite and component checks do not replace that check.
