# Spec: Edit Expense

## Overview
This feature implements the `GET /expenses/<id>/edit` and `POST /expenses/<id>/edit` routes so logged-in users can correct or update an existing expense. The form pre-fills with the expense's current values and, on a valid submission, updates the corresponding row in the `expenses` table before redirecting to `/profile`. Only the owner of an expense may edit it — attempting to edit another user's expense returns a 403. This step also threads the expense `id` through `get_expenses_by_user` and `profile.html` so that each transaction row carries an edit link.

## Depends on
- Step 01 — database-setup (`expenses` table, `get_db()`)
- Step 02 — registration (user accounts)
- Step 03 — login-and-logout (session `user_id`)
- Step 04 / 05 — profile page and backend integration (`profile.html`, `get_expenses_by_user`)
- Step 07 — add-expense (`add_expense` helper, `VALID_CATEGORIES` list, `add_expense.html` as style reference)

## Routes
- `GET /expenses/<int:id>/edit` — render the edit form pre-filled with the expense's current values — logged-in only
- `POST /expenses/<int:id>/edit` — validate and update the expense row, then redirect to `/profile` — logged-in only

## Database changes
No new tables or columns. Two new helper functions are added to `database/db.py`:

- `get_expense_by_id(expense_id)` — fetches one row from `expenses` by `id`; returns a `sqlite3.Row` or `None`
- `update_expense(expense_id, user_id, amount, category, expense_date, description)` — updates `amount`, `category`, `date`, and `description` for the row matching `id = expense_id AND user_id = user_id`; returns the number of rows affected

`get_expenses_by_user` must also be updated to include the `id` field in each result dict so that `profile.html` can build edit/delete links.

## Templates
- **Create:** `templates/edit_expense.html` — edit form extending `base.html` with:
  - `amount` — numeric input (positive, required), pre-filled
  - `category` — `<select>` with the same seven fixed categories as the add form, pre-selected
  - `date` — `<input type="date">` pre-filled with the current date value (required)
  - `description` — `<textarea>` (optional), pre-filled
  - Error display block for validation errors
  - Submit button and a cancel link back to `/profile`
- **Modify:** `templates/profile.html` — add an "Edit" link (using `url_for("edit_expense", id=tx.id)`) to each row in the transaction list; requires the `id` key to be present in each transaction dict

## Files to change
- `app.py` — replace the `edit_expense` stub with a real view handling GET and POST; add `get_expense_by_id` and `update_expense` to the import from `database.db`; accept both GET and POST methods on the route
- `database/db.py` — add `get_expense_by_id(expense_id)` and `update_expense(expense_id, user_id, amount, category, expense_date, description)`; update `get_expenses_by_user` to include `id` in each result dict

## Files to create
- `templates/edit_expense.html` — the edit-expense form template

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — use raw `sqlite3` via `get_db()` only
- Parameterised queries only — never use f-strings or `.format()` in SQL
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Authentication guard: if `session.get("user_id")` is absent, `redirect(url_for("login"))`
- Ownership guard: after fetching the expense, if `expense["user_id"] != session["user_id"]`, call `abort(403)`
- Not-found guard: if `get_expense_by_id` returns `None`, call `abort(404)`
- `amount` must be validated as a positive float; reject zero and negative values
- `category` must be one of the seven fixed values — reject anything else
- `date` must parse as a valid `YYYY-MM-DD` string; reject malformed input
- `description` is optional — store `None` if blank
- All DB logic belongs in `database/db.py`; the route only fetches, validates, calls helpers, and renders
- On validation error, re-render the form with the error message and the user's previously submitted values (not the original DB values)
- On success, redirect to `/profile` using `url_for("profile")`
- `update_expense` must filter by both `id` and `user_id` in the `WHERE` clause as a second ownership layer
- Style the edit form consistently with `add_expense.html` — reuse existing CSS classes where possible

## Definition of done
- [ ] `GET /expenses/<id>/edit` without a session redirects (302) to `/login`
- [ ] `GET /expenses/<id>/edit` for a non-existent expense returns 404
- [ ] `GET /expenses/<id>/edit` for an expense owned by another user returns 403
- [ ] `GET /expenses/<id>/edit` while logged in as the owner returns HTTP 200 with the form pre-filled
- [ ] The form shows the existing amount, category, date, and description values
- [ ] `POST /expenses/<id>/edit` with valid data updates the row and redirects (302) to `/profile`
- [ ] The updated values are visible in the transaction list on `/profile`
- [ ] `POST /expenses/<id>/edit` with a missing or zero amount re-renders the form with an error message
- [ ] `POST /expenses/<id>/edit` with an invalid category re-renders the form with an error message
- [ ] `POST /expenses/<id>/edit` with a missing date re-renders the form with an error message
- [ ] On validation failure, the user's submitted (not original) values are pre-filled in the form
- [ ] `POST /expenses/<id>/edit` for an expense owned by another user returns 403
- [ ] Each transaction row on `/profile` has a working "Edit" link pointing to the correct edit URL
- [ ] `get_expense_by_id` and `update_expense` are defined in `database/db.py` and use parameterised queries
- [ ] No hex colour values appear in `edit_expense.html` — only CSS variables
