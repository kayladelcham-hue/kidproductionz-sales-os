# Business swipe discovery — implementation and verification

## Changed
- The focused review card physically follows horizontal PointerEvents from mouse or touch, rotates gently, and shows a lime fit stamp or a not-fit stamp. Release requires at least 72 CSS pixels and horizontal displacement over 1.5 times vertical displacement. Short drags snap back; canceled gestures do not decide. Vertical scrolling and pinch zoom remain allowed.
- Drag motion has no easing while held. Existing reduced-motion rules remove transition/animation. A movement over 8 pixels suppresses the following synthetic click, preventing accidental flips. F remains a keyboard flip shortcut.
- The next actual business peeks behind the active card in review mode and is inert. Saved/setup carousels retain their existing layouts.
- Flip for details reveals existing qualification evidence, unknowns, sources and editable research notes. Decision controls remain outside both card faces.
- Gestures and labeled buttons call the same existing persisted review handler. The existing save lock, retry, undo, actual completion counts and backend duplicate prevention remain intact.
- Home has a visible New search shortcut that reopens the existing Skye setup. It also has a compact Ready to contact card for an actual saved, explicitly qualified business with usable listed channels and a saved prospect ID.
- The contact card reads recorded next actions from the existing follow-up API. View contact and Draft a message resolve the exact saved prospect in the current campaign, then open the existing outreach drawer. Draft focuses its editor. Contacts are labeled listed/unverified. Missing recipients remain empty; sending still requires the existing explicit Confirm Send action. No automatic communication was added.
- Shared canonical design rules were edited in place; no override stylesheet, backend schema, authentication, ownership or integration changes.

## Passed
- 34 jsdom component checks: simulated mouse/touch PointerEvents, threshold/snap-back, drag feedback, cancellation and vertical movement, post-drag click suppression, flipping, keyboard handling/input exclusions, buttons, pending persistence, failed fit-save retry, undo, actual completion counts, saved carousel, theme preference persistence, Skye focus, recorded evidence and safe sources, qualified-contact eligibility, selected-record draft/view callbacks, retryable handoff errors, empty state and recorded next-action lookup.
- 65 backend tests across discovery workflow, ICP scoring, rescoring, managed discovery and beta readiness: persistent decisions/save/outreach preparation/undo, reloaded records, ownership and optimistic conflicts, concurrent duplicate prevention, existing-record preservation and source failure handling. One existing Starlette/httpx deprecation warning.
- Vite production build and local Manrope font/typography contract.

## Not verified
- Physical browser mouse/touch behavior, pointer capture, rendered desktop/mobile comparison with the mockup, long-name wrapping, both rendered themes, 200% zoom and reduced-motion appearance: browser access was denied because the tool could not verify the admin security policy. No alternate browser or indirect access was used to bypass it.
- Live authenticated save/reload and complete Home-to-outreach interaction in a browser; component callback and backend persistence checks are not a live end-to-end test.
- Render deployment completion/live build identity has not been checked.
- Full TypeScript checking remains blocked by the pre-existing missing React/JSX declaration dependencies in the shared node_modules. Vite/esbuild compilation passed.

These checks do not establish an exact rendered visual match or beta launch readiness.
