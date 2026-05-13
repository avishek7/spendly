# Spec: Date Filter for Profile Page

## Overview
This feature adds date-range filtering to the profile page so users can narrow their
expense view to a specific period. A filter bar lets the user pick a preset period
(Last 7 days, Last 30 days, This month, All time) or supply custom from/to dates.
The selected range is passed as query-string parameters; the profile route re-queries
the database with those bounds and re-renders the page. Stats, the transaction list,
and the category breakdown all reflect the active filter — giving users a meaningful
snapshot of any period rather than always seeing their full history.

## Depends on
- Step 01 — database-setup (users and expenses tables, helper functions)
- Step 02 — registration
- Step 03 — login-and-logout
- Step 04 — profile-page (HTML structure)
- Step 05 — backend-profile-page-integration (real DB data on profile page)

## Routes
- `GET /profile` — modified to accept optional query params `period`, `from`, and `to`;
  returns filtered stats, transactions, and categories — logged-in only

No new routes.

## Database changes
No new tables or columns.

The following existing helper functions must be updated to accept optional
`date_from` and `date_to` parameters (both `str | None`, format `YYYY-MM-DD`).
When provided, a `WHERE date BETWEEN ? AND ?` clause is added to the query:

- `get_expenses_by_user(user_id, date_from=None, date_to=None)`
- `get_stats_by_user(user_id, date_from=None, date_to=None)`
- `get_categories_by_user(user_id, date_from=None, date_to=None)`

## Templates
- **Modify:** `templates/profile.html`
  - Add a filter bar above the transactions section containing:
    - Four preset buttons: "Last 7 days", "Last 30 days", "This month", "All time"
    - Two `<input type="date">` fields ("From" / "To") for a custom range
    - A "Apply" submit button for the custom range
  - The active preset button receives an `active` CSS class
  - Display the active date range label (e.g. "Showing: Last 30 days") near the stats

## Files to change
- `database/db.py` — update `get_expenses_by_user`, `get_stats_by_user`,
  `get_categories_by_user` to accept and apply `date_from` / `date_to`
- `app.py` — update the `profile` route to parse query params and pass
  date bounds to the DB helpers
- `templates/profile.html` — add filter bar UI
- `static/css/style.css` — add styles for the filter bar and active button state

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — use raw parameterized queries only (`?` placeholders)
- Never interpolate variables into SQL strings with f-strings
- Passwords hashed with werkzeug (unchanged)
- Use CSS variables from `style.css` — never hardcode hex values
- All templates extend `base.html`
- The `period` query param accepts exactly these values: `7d`, `30d`, `month`, `all`
  (default when absent: `all`)
- Custom range uses `from` and `to` query params (ISO date strings `YYYY-MM-DD`);
  when both are present they override `period`
- Compute preset date bounds in the route using Python's `datetime` module —
  no date arithmetic in SQL
- If `date_from` and `date_to` are both `None`, helpers return the unfiltered result
  (no `BETWEEN` clause) — preserving existing all-time behaviour
- Custom range: if only one of `from`/`to` is supplied, ignore both and fall back
  to the `period` param
- The filter form must use `GET` method so the filtered URL is bookmarkable
- Invalid date strings (unparseable) should silently fall back to `all` — use
  `abort()` is NOT appropriate here; just ignore bad input

## Definition of done
- [ ] Visiting `/profile` with no query params shows all expenses (unchanged behaviour)
- [ ] Visiting `/profile?period=7d` shows only expenses from the last 7 days; stats
  and category breakdown reflect that subset
- [ ] Visiting `/profile?period=30d` shows only expenses from the last 30 days
- [ ] Visiting `/profile?period=month` shows only expenses from the current calendar month
- [ ] Visiting `/profile?period=all` shows all expenses
- [ ] Visiting `/profile?from=2026-05-01&to=2026-05-07` shows only expenses in that range
- [ ] If only `from` or only `to` is provided, the filter falls back to the `period` param
- [ ] Unparseable date strings in `from`/`to` fall back to all-time silently
- [ ] The active preset button is visually highlighted on the profile page
- [ ] The active date range is shown as a human-readable label near the stats cards
- [ ] Filter bar renders correctly on mobile (no horizontal overflow)
- [ ] All DB queries remain parameterized — no f-string SQL
