# Spec: Login and Logout

## Overview

Implement the `GET /logout` route so authenticated users can end their session, and harden the authentication flow by redirecting users who are already logged in away from the login and register pages. This step completes the full authentication loop: register → login → use app → logout → back to landing. It is a prerequisite for any route that requires a logged-in user.

## Depends on

Step 1 — Database Setup (`users` table, `get_db()`).
Step 2 — Registration (POST `/register`, POST `/login`, `session["user_id"]`, `app.secret_key`).

## Routes

- `GET /logout` — clear `session["user_id"]`, redirect to `/` — logged-in only (unauthenticated requests redirect to `/login`)

No other new routes. Existing `GET /login` and `GET /register` will gain an authenticated-user redirect (to `/` if `session["user_id"]` is already set). Successful `POST /login` and `POST /register` also redirect to `/`.

## Database changes

No database changes.

## Templates

- **Modify:** `templates/base.html` — add a "Logout" nav link using `url_for('logout')` that is only rendered when `session.get("user_id")` is set; hide Login / Register links for authenticated users

## Files to change

- `app.py` — implement `logout()` route; add auth-guard redirect to `login()` and `register()` GET branches
- `templates/base.html` — conditional nav links based on session state

## Files to create

- `tests/test_logout.py` — pytest tests covering the scenarios in Definition of done

## New dependencies

No new dependencies.

## Rules for implementation

- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (unchanged — no password logic here)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Clear the session with `session.clear()` or `session.pop("user_id", None)` — never delete the session file manually
- Use `url_for()` for all redirects — never hardcode paths
- Unauthenticated `GET /logout` must redirect to `/login`, not raise an error
- Already-authenticated users hitting `GET /login` or `GET /register` must redirect to `/`
- Successful login and registration redirect to `/`, not `/profile`

## Definition of done

- [ ] `GET /logout` with a valid session clears `session["user_id"]` and redirects (302) to `/`
- [ ] `GET /logout` without a session (unauthenticated) redirects (302) to `/login`
- [ ] After logout, revisiting a protected URL does not restore the session
- [ ] `POST /login` with valid credentials redirects (302) to `/`
- [ ] `POST /register` with valid data redirects (302) to `/`
- [ ] `GET /login` while already authenticated redirects (302) to `/`
- [ ] `GET /register` while already authenticated redirects (302) to `/`
- [ ] `base.html` shows "Logout" link only when the user is logged in
- [ ] `base.html` shows "Login" and "Register" links only when the user is not logged in
- [ ] All pytest tests in `tests/test_logout.py` pass
- [ ] Existing tests in `tests/test_auth.py` continue to pass (no regression)
