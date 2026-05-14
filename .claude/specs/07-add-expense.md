# Spec: Add Expense

## Overview
This feature implements the `GET /expenses/add` and `POST /expenses/add` routes so logged-in users can submit a new expense through a form. The form collects the required fields (amount, category, date, and an optional description) and inserts a new row into the `expenses` table. On success the user is redirected back to `/profile`. This is the first write path in the Spendly expense lifecycle and is a prerequisite for editing and deleting expenses in Steps 8 and 9.

## Depends on
- Step 01 — database-setup (`expenses` table, `get_db()`)
- Step 02 — registration (user accounts)
- Step 03 — login-and-logout (session `user_id`)
- Step 05 — backend-profile-page-integration (`get_expenses_by_user` and related helpers must work)

## Routes
- `GET /expenses/add` — render the add-expense form — logged-in only
- `POST /expenses/add` — validate and insert a new expense row, then redirect to `/profile` — logged-in only

## Database changes
No new tables or columns. The existing `expenses` schema (`id`, `user_id`, `amount`, `category`, `date`, `description`, `created_at`) covers all fields. One new helper function is added to `database/db.py`:

- `add_expense(user_id, amount, category, date, description)` — inserts one row into `expenses`, returns the new `id`

## Templates
- **Create:** `templates/add_expense.html` — form page extending `base.html` with:
  - `amount` — numeric input (positive, required)
  - `category` — `<select>` with the fixed category list: Food, Transport, Bills, Health, Entertainment, Shopping, Other
  - `date` — `<input type="date">` defaulting to today (required)
  - `description` — `<textarea>` (optional)
  - Error display block for validation errors
  - Submit button and a cancel link back to `/profile`

## Files to change
- `app.py` — replace the `add_expense` stub with a real view handling both GET and POST; add `add_expense` to the import from `database.db`
- `database/db.py` — add `add_expense(user_id, amount, category, date, description)` helper

## Files to create
- `templates/add_expense.html` — the add-expense form template

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — use raw `sqlite3` via `get_db()` only
- Parameterised queries only — never use f-strings or `.format()` in SQL
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Authentication guard: if `session.get("user_id")` is absent, `redirect(url_for("login"))`
- `amount` must be validated as a positive float; reject zero and negative values
- `category` must be one of the seven fixed values — reject anything else
- `date` must parse as a valid `YYYY-MM-DD` string; reject malformed input
- `description` is optional — store `None` if blank
- All DB logic belongs in `database/db.py`; the route only fetches, validates, calls helpers, and renders
- On validation error, re-render the form with the error message and the user's previously entered values pre-filled
- On success, redirect to `/profile` using `url_for("profile")`
- Use `abort(400)` only for truly unrecoverable bad requests; use the form error pattern for normal validation failures

## Definition of done
- [ ] `GET /expenses/add` without a session redirects (302) to `/login`
- [ ] `GET /expenses/add` while logged in returns HTTP 200 and renders the form
- [ ] The form contains inputs for amount, category (select), date, and description
- [ ] `POST /expenses/add` with valid data inserts a row into `expenses` and redirects (302) to `/profile`
- [ ] The newly added expense appears in the transaction list on `/profile`
- [ ] `POST /expenses/add` with a missing or zero amount re-renders the form with an error message
- [ ] `POST /expenses/add` with an invalid category re-renders the form with an error message
- [ ] `POST /expenses/add` with a missing date re-renders the form with an error message
- [ ] On validation failure, previously entered values are pre-filled in the form
- [ ] `add_expense` is defined in `database/db.py` and uses a parameterised query
- [ ] No hex colour values appear in `add_expense.html` — only CSS variables
