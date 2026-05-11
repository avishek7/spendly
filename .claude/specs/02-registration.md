# Spec: Registration

## Overview

Wire up the existing `register.html` and `login.html` forms to real POST handlers so users can create accounts and sign in. Flask's built-in signed cookie session is used to persist identity across requests. This is the authentication foundation that every subsequent logged-in feature depends on.

## Depends on

Step 1 — Database Setup. The `users` table, `get_db()`, and `werkzeug.security` must all be in place before this step can be implemented.

## Routes

- `POST /register` — validate form input, hash password, insert user, set session, redirect to `/profile` — public
- `POST /login` — validate credentials against DB, set session, redirect to `/profile` — public

Existing `GET /register` and `GET /login` routes remain unchanged.

## Database changes

No new tables or columns. Two new helper functions are added to `database/db.py`:

- `create_user(name, email, password_hash)` → inserts a row into `users`, returns the new `user_id`
- `get_user_by_email(email)` → returns the `sqlite3.Row` for that email, or `None`

Both must use `?` placeholders — no f-strings in SQL.

## Templates

- **Modify:** `templates/register.html` — already has `{% if error %}<div class="auth-error">{{ error }}</div>{% endif %}` block; no changes needed
- **Modify:** `templates/login.html` — must have the same `{% if error %}` error block; verify it exists or add it

## Files to change

- `database/db.py` — add `create_user` and `get_user_by_email`
- `app.py` — add imports (`request`, `session`, `redirect`, `url_for`, `generate_password_hash`, `check_password_hash`, `create_user`, `get_user_by_email`), add `app.secret_key`, expand `register` and `login` routes to handle POST

## Files to create

- `tests/__init__.py` — empty, makes `tests/` a package for pytest
- `tests/conftest.py` — app + client fixtures using monkeypatched `get_db` with `tmp_path` SQLite DB
- `tests/test_auth.py` — 7 tests (see Definition of done)

## New dependencies

No new pip packages. `werkzeug.security` is already in `requirements.txt`.

## Rules for implementation

- No SQLAlchemy or ORMs
- Parameterised queries only (`?` placeholders, never f-strings in SQL)
- Passwords hashed with `werkzeug.security.generate_password_hash`; verified with `check_password_hash`
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- All DB logic in `database/db.py` — never inline in route functions
- `app.secret_key` must be set before any route uses `session`
- Login error must use a single generic message for both unknown email and wrong password — no email enumeration
- Use `url_for()` for the redirect target, not a hardcoded string

## Error messages (exact — tests assert on these)

| Scenario | Message |
|---|---|
| Any register field blank | `"All fields are required."` |
| Password fewer than 8 characters | `"Password must be at least 8 characters."` |
| Email already in `users` table | `"An account with that email already exists."` |
| Login fields blank | `"Email and password are required."` |
| Wrong password or unknown email | `"Invalid email or password."` |

## Out of scope for this step

- `GET /logout` — Step 3
- `GET /profile` — Step 4 (redirect target exists as a stub; do not touch it)
- "Remember me" / persistent sessions
- Email verification
- Password reset
- CSRF protection

## Definition of done

- [ ] `POST /register` with valid data redirects (302) to `/profile` and sets `session["user_id"]`
- [ ] `POST /register` with a blank field returns 200 with `"All fields are required."`
- [ ] `POST /register` with a password shorter than 8 characters returns 200 with `"Password must be at least 8 characters."`
- [ ] `POST /register` with a duplicate email returns 200 with `"An account with that email already exists."`
- [ ] `POST /login` with valid credentials redirects (302) to `/profile` and sets `session["user_id"]`
- [ ] `POST /login` with wrong password returns 200 with `"Invalid email or password."`
- [ ] `POST /login` with unknown email returns 200 with `"Invalid email or password."`
- [ ] All 7 pytest tests in `tests/test_auth.py` pass
- [ ] `GET /register` and `GET /login` still render correctly (no regression)
