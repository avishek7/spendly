# Spec: Backend Profile Page Integration

## Overview
This feature replaces the hardcoded stub data in the `/profile` route with real database queries. Step 4 built the full profile page UI using static Python dicts; Step 5 wires that same template to live data from the `users` and `expenses` tables. The result is a profile page that reflects each logged-in user's actual name, email, join date, expense history, summary stats, and category breakdown — all queried via parameterised SQL through `database/db.py`.

## Depends on
- Step 1: Database setup (`users` and `expenses` tables must exist)
- Step 2: Registration (real user rows must be creatable)
- Step 3: Login + Logout (session must contain a valid `user_id`)
- Step 4: Profile page UI (the `profile.html` template must already exist with its four sections)

## Routes
No new routes. The existing `GET /profile` route is modified in place.

## Database changes
No new tables or columns. The existing `users` and `expenses` tables have all the data needed. New helper functions are added to `database/db.py` to query that data.

## Templates
- **Modify:** `templates/profile.html` — no structural changes required; the template already uses `{{ user.name }}`, `{{ user.email }}`, etc. Verify that all context keys rendered in the template exactly match the keys returned by the new DB helpers. Fix any mismatches found.

## Files to change
- `app.py`
  - Import any new helpers added to `database/db.py`
  - Replace the hardcoded `user`, `stats`, `transactions`, and `categories` dicts/lists in the `/profile` route with real DB calls
  - Derive `user.initials` (first letter of each word in `name`, uppercased) in the route function, not in the template
  - Derive `user.member_since` by formatting `created_at` from the `users` row as `"Month YYYY"` (e.g. `"January 2025"`)
  - Format amounts as `"₹{amount:,.2f}"` strings before passing to the template
- `database/db.py`
  - Add `get_user_by_id(user_id)` — returns the matching `users` row or `None`
  - Add `get_expenses_by_user(user_id)` — returns all expenses for that user ordered by `date DESC`, with date formatted as `"DD Mon YYYY"` (e.g. `"10 May 2026"`)
  - Add `get_stats_by_user(user_id)` — returns a dict with:
    - `total_spent` — sum of `amount` for the user (float, unformatted; formatting done in route)
    - `transaction_count` — count of expense rows
    - `top_category` — the category with the highest total `amount`; empty string if no expenses
  - Add `get_categories_by_user(user_id)` — returns a list of dicts `{name, key, amount, percent}` where `key` is `name.lower()`, `amount` is the per-category sum (float), and `percent` is that category's share of total spend as an integer 0–100; ordered by `amount DESC`

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — use raw `sqlite3` via `get_db()` only
- Parameterised queries only — never use f-strings or `.format()` in SQL
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB helpers must close the connection before returning (use `conn.close()`)
- If `get_user_by_id` returns `None` (user row missing), call `abort(404)` in the route — do not crash
- `initials` and `member_since` are computed in the route function, not in DB helpers and not in the template
- Category `percent` must be 0 when `total_spent` is 0 (guard against division-by-zero)
- All amount formatting (₹ symbol, commas, 2 decimal places) happens in the route, not in DB helpers

## Definition of done
- [ ] Visiting `/profile` while logged in returns HTTP 200 with the real user's name and email (not "Nitish Kumar")
- [ ] The user info card shows the correct initials derived from the real user's name
- [ ] The member-since date reflects the `created_at` value from the `users` table
- [ ] The transaction history table shows only expenses belonging to the logged-in user, ordered newest first
- [ ] The summary stats (total spent, transaction count, top category) are computed from real DB data
- [ ] The category breakdown reflects actual expense categories for the logged-in user
- [ ] Logging in as a second user (e.g. the seed demo user) shows that user's own data, not another user's
- [ ] If the user has no expenses, the stats show ₹0.00 / 0 transactions / empty top category without crashing
- [ ] All DB queries use parameterised placeholders — no string-interpolated SQL
- [ ] `get_user_by_id`, `get_expenses_by_user`, `get_stats_by_user`, `get_categories_by_user` are all defined in `database/db.py`
