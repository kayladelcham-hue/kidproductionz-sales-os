# Manual prospects and follow-ups

Use **Add Prospect** from the header or navigation. Choose the campaign first,
then enter a name and phone or email. Notes are optional. The prospect is stored
in the existing campaign prospect table as `CONTACTED` with queue `RESEARCH`:
meeting someone does not automatically qualify them for the scored daily queue.
Intake uses the existing generated-prospect dedupe rules, including normalized
phone and email matching within the selected campaign. Duplicates are reported
without overwriting the existing record.

The **Follow-Up / Schedule Hub** is available from navigation and the mobile
bottom bar. It includes Contacted, Replied, Follow Up, Consultation Set, and
prospects with stored consultations or a dated next action. Records are ordered
by their next action date, falling back to their latest consultation date.
Status filters include closed prospects that still have consultation records.

Next-action dates are entered in the browser's timezone and saved in UTC in
existing sales action metadata. Saving updates status, notes, and the activity
timestamp without moving the prospect's queue. Clearing the date removes its
next-action reminder. Consultation history remains visible.

Open prospect details to use the existing consultation creation flow. Reschedule
uses the stored Google event ID in the primary calendar, previews dates, then
requires explicit confirmation. The existing Calendar enable flag and connected
Google credentials remain required. A provider failure leaves stored times
unchanged. Calendar edits made directly in Google are not imported into the hub;
the hub uses the application's stored consultation records.

No database migration is required. No automatic emails, calendar events, or
HubSpot writes are introduced. Cloud routes retain session and CSRF protection.

Validation: production Vite build; sales hub intake/dedupe, campaign scope,
next-action timezone, rescheduling preview/gates/failure/success, cloud auth/CSRF;
existing calendar datetime, queue, queue artifact, and fresh database tests.
