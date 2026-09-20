# Sales lifecycle migration

The rollout keeps `prospect` as the canonical contact table. Existing contact IDs,
campaign assignments, notes, queue state, email activity, external actions, and
calendar consultations remain attached to the same rows.

The upgrade adds four nullable/defaulted contact fields and a separate `deal`
table. Existing contacts are classified conservatively:

- `BOOKED` becomes a Customer with one Won deal.
- `REPLIED` and `CONSULTATION_SET` become Leads with one active deal.
- Every other status remains a Prospect.

`booked_value` seeds deal value for an existing booked contact. Collected revenue
starts at zero because the old schema did not prove that payment was received.
The seed is idempotent and will not create a second deal for a contact that already
has one.

## Release checks

1. Back up the production database using the hosting provider's normal snapshot.
2. Deploy the application. `init_db()` applies the same additive checks used by
   the migration, so existing beta installs can start safely.
3. Confirm the Home counts, one Prospect conversion, one consultation, one Won
   deal, and Sales & Revenue totals with a test account.
4. Confirm a second beta account cannot see the first account's contacts or deals.

The downgrade in the Alembic file is intentionally destructive and should not be
used as a normal rollback. Roll back the application version while leaving the
new columns and deal table in place; older application code ignores them.
