"""
tests/test_08-edit-expense.py

Tests for the Edit Expense feature (Step 08).

Spec: .claude/specs/08-edit-expense.md
Routes:
    GET  /expenses/<int:id>/edit  — render pre-filled form (auth + owner guarded)
    POST /expenses/<int:id>/edit  — validate, update row, redirect to /profile

All tests rely on conftest.py fixtures: app, client.
Module-level helpers register/login a user and manipulate the DB directly so
that each test is fully independent.
"""

import re
import inspect
import database.db as db_module

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_USER = {
    "name": "Edit Tester",
    "email": "edittester@example.com",
    "password": "securepass",
}

_OTHER_USER = {
    "name": "Other User",
    "email": "otheruser@example.com",
    "password": "otherpass1",
}

VALID_CATEGORIES = [
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
]

_ORIGINAL_EXPENSE = {
    "amount": 99.99,
    "category": "Food",
    "date": "2026-01-10",
    "description": "Original description",
}

_VALID_UPDATE = {
    "amount": "42.50",
    "category": "Transport",
    "date": "2026-03-15",
    "description": "Updated description",
}


# ---------------------------------------------------------------------------
# Test-database helpers
# ---------------------------------------------------------------------------


def _register_and_login(client, user=None):
    """Register (if needed) and log in; returns the same sticky-session client."""
    if user is None:
        user = _USER
    client.post("/register", data=user)
    return client


def _get_user_id(email):
    conn = db_module.get_db()
    row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return row["id"]


def _insert_expense(user_id, amount=None, category=None, date=None, description=None):
    """Insert an expense row directly into the DB; returns the new expense id."""
    amount = amount if amount is not None else _ORIGINAL_EXPENSE["amount"]
    category = category if category is not None else _ORIGINAL_EXPENSE["category"]
    date = date if date is not None else _ORIGINAL_EXPENSE["date"]
    description = (
        description if description is not None else _ORIGINAL_EXPENSE["description"]
    )

    conn = db_module.get_db()
    cursor = conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description)"
        " VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, date, description),
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id


def _fetch_expense(expense_id):
    """Fetch a single expense row directly from the DB."""
    conn = db_module.get_db()
    row = conn.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()
    conn.close()
    return row


# ---------------------------------------------------------------------------
# Auth guard tests
# ---------------------------------------------------------------------------


class TestEditExpenseAuthGuard:
    def test_get_edit_unauthenticated_redirects_to_login(self, client):
        """GET /expenses/<id>/edit without a session must redirect 302 to /login."""
        resp = client.get("/expenses/1/edit")
        assert resp.status_code == 302, (
            f"Expected 302 redirect for unauthenticated GET, got {resp.status_code}"
        )
        assert resp.headers["Location"] == "/login", (
            f"Expected redirect to /login, got '{resp.headers['Location']}'"
        )

    def test_post_edit_unauthenticated_redirects_to_login(self, client):
        """POST /expenses/<id>/edit without a session must redirect 302 to /login."""
        resp = client.post("/expenses/1/edit", data=_VALID_UPDATE)
        assert resp.status_code == 302, (
            f"Expected 302 redirect for unauthenticated POST, got {resp.status_code}"
        )
        assert resp.headers["Location"] == "/login", (
            f"Expected redirect to /login, got '{resp.headers['Location']}'"
        )


# ---------------------------------------------------------------------------
# Not-found guard tests
# ---------------------------------------------------------------------------


class TestEditExpenseNotFound:
    def test_get_edit_nonexistent_expense_returns_404(self, client):
        """GET /expenses/<id>/edit for a non-existent id must return 404."""
        _register_and_login(client)
        resp = client.get("/expenses/99999/edit")
        assert resp.status_code == 404, (
            f"Expected 404 for a non-existent expense id, got {resp.status_code}"
        )

    def test_post_edit_nonexistent_expense_returns_404(self, client):
        """POST /expenses/<id>/edit for a non-existent id must return 404."""
        _register_and_login(client)
        resp = client.post("/expenses/99999/edit", data=_VALID_UPDATE)
        assert resp.status_code == 404, (
            f"Expected 404 for a non-existent expense id on POST, got {resp.status_code}"
        )


# ---------------------------------------------------------------------------
# Ownership guard tests
# ---------------------------------------------------------------------------


class TestEditExpenseOwnershipGuard:
    def test_get_edit_other_users_expense_returns_403(self, client):
        """GET /expenses/<id>/edit for another user's expense must return 403."""
        # Register owner and insert an expense
        _register_and_login(client, _OTHER_USER)
        owner_id = _get_user_id(_OTHER_USER["email"])
        expense_id = _insert_expense(owner_id)

        # Register and log in a different user
        client.get("/logout")
        _register_and_login(client, _USER)

        resp = client.get(f"/expenses/{expense_id}/edit")
        assert resp.status_code == 403, (
            f"Expected 403 when accessing another user's expense on GET, got {resp.status_code}"
        )

    def test_post_edit_other_users_expense_returns_403(self, client):
        """POST /expenses/<id>/edit for another user's expense must return 403."""
        # Register owner and insert an expense
        _register_and_login(client, _OTHER_USER)
        owner_id = _get_user_id(_OTHER_USER["email"])
        expense_id = _insert_expense(owner_id)

        # Register and log in a different user
        client.get("/logout")
        _register_and_login(client, _USER)

        resp = client.post(f"/expenses/{expense_id}/edit", data=_VALID_UPDATE)
        assert resp.status_code == 403, (
            f"Expected 403 when posting to another user's expense, got {resp.status_code}"
        )

    def test_post_edit_other_users_expense_does_not_update_db(self, client):
        """A 403 attempt must leave the DB row unchanged."""
        _register_and_login(client, _OTHER_USER)
        owner_id = _get_user_id(_OTHER_USER["email"])
        expense_id = _insert_expense(owner_id)

        client.get("/logout")
        _register_and_login(client, _USER)

        client.post(f"/expenses/{expense_id}/edit", data=_VALID_UPDATE)

        row = _fetch_expense(expense_id)
        assert abs(float(row["amount"]) - _ORIGINAL_EXPENSE["amount"]) < 0.001, (
            "Expense amount must not be changed after an unauthorised POST"
        )
        assert row["category"] == _ORIGINAL_EXPENSE["category"], (
            "Expense category must not be changed after an unauthorised POST"
        )


# ---------------------------------------------------------------------------
# GET happy path — form pre-filled with correct values
# ---------------------------------------------------------------------------


class TestEditExpenseGetForm:
    def test_get_edit_as_owner_returns_200(self, client):
        """GET /expenses/<id>/edit as the owner must return HTTP 200."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id)

        resp = client.get(f"/expenses/{expense_id}/edit")
        assert resp.status_code == 200, (
            f"Expected 200 for owner accessing edit form, got {resp.status_code}"
        )

    def test_get_edit_form_prefills_amount(self, client):
        """The edit form must display the expense's current amount pre-filled."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id, amount=123.45)

        resp = client.get(f"/expenses/{expense_id}/edit")
        assert b"123.45" in resp.data, (
            "Expected the current amount '123.45' to be pre-filled in the edit form"
        )

    def test_get_edit_form_prefills_category(self, client):
        """The edit form must pre-select the expense's current category."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id, category="Health")

        resp = client.get(f"/expenses/{expense_id}/edit")
        assert b"Health" in resp.data, (
            "Expected the current category 'Health' to appear pre-selected in the form"
        )

    def test_get_edit_form_prefills_date(self, client):
        """The edit form must display the expense's current date pre-filled."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id, date="2025-11-20")

        resp = client.get(f"/expenses/{expense_id}/edit")
        assert b"2025-11-20" in resp.data, (
            "Expected the current date '2025-11-20' to be pre-filled in the edit form"
        )

    def test_get_edit_form_prefills_description(self, client):
        """The edit form must display the expense's current description pre-filled."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id, description="Dinner with team")

        resp = client.get(f"/expenses/{expense_id}/edit")
        assert b"Dinner with team" in resp.data, (
            "Expected the current description to be pre-filled in the edit form"
        )

    def test_get_edit_form_has_amount_input(self, client):
        """Edit form must contain an input named 'amount'."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id)

        resp = client.get(f"/expenses/{expense_id}/edit")
        assert b'name="amount"' in resp.data, (
            "Expected an input with name='amount' in the edit form"
        )

    def test_get_edit_form_has_category_select(self, client):
        """Edit form must contain a <select> named 'category'."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id)

        resp = client.get(f"/expenses/{expense_id}/edit")
        assert b'name="category"' in resp.data, (
            "Expected a select with name='category' in the edit form"
        )
        assert b"<select" in resp.data, "Expected a <select> element for category"

    def test_get_edit_form_shows_all_seven_categories(self, client):
        """The category select must include all seven valid categories."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id)

        resp = client.get(f"/expenses/{expense_id}/edit")
        for cat in VALID_CATEGORIES:
            assert cat.encode() in resp.data, (
                f"Expected category option '{cat}' in the edit form"
            )

    def test_get_edit_form_has_date_input(self, client):
        """Edit form must contain a date input named 'date'."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id)

        resp = client.get(f"/expenses/{expense_id}/edit")
        assert b'name="date"' in resp.data, (
            "Expected an input with name='date' in the edit form"
        )
        assert b'type="date"' in resp.data, (
            "Expected input type='date' for the date field"
        )

    def test_get_edit_form_has_description_textarea(self, client):
        """Edit form must contain a textarea named 'description'."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id)

        resp = client.get(f"/expenses/{expense_id}/edit")
        assert b'name="description"' in resp.data, (
            "Expected a textarea with name='description' in the edit form"
        )
        assert b"<textarea" in resp.data, (
            "Expected a <textarea> element for description"
        )

    def test_get_edit_form_has_submit_button(self, client):
        """Edit form must have a submit button."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id)

        resp = client.get(f"/expenses/{expense_id}/edit")
        assert (
            b'type="submit"' in resp.data
            or b"Save" in resp.data
            or b"Update" in resp.data
        ), "Expected a submit button in the edit form"

    def test_get_edit_form_has_cancel_link_to_profile(self, client):
        """Edit form must include a cancel link back to /profile."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id)

        resp = client.get(f"/expenses/{expense_id}/edit")
        assert b"/profile" in resp.data, (
            "Expected a cancel link pointing to /profile in the edit form"
        )

    def test_get_edit_form_extends_base_html(self, client):
        """The edit-expense page must extend base.html (Spendly branding present)."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id)

        resp = client.get(f"/expenses/{expense_id}/edit")
        assert b"Spendly" in resp.data, (
            "Expected page to extend base.html — 'Spendly' branding should appear"
        )


# ---------------------------------------------------------------------------
# POST happy path — valid update
# ---------------------------------------------------------------------------


class TestEditExpensePostValid:
    def test_post_edit_valid_redirects_to_profile(self, client):
        """POST /expenses/<id>/edit with valid data must redirect (302) to /profile."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id)

        resp = client.post(f"/expenses/{expense_id}/edit", data=_VALID_UPDATE)
        assert resp.status_code == 302, (
            f"Expected 302 redirect on valid POST, got {resp.status_code}"
        )
        assert resp.headers["Location"] == "/profile", (
            f"Expected redirect to /profile, got '{resp.headers['Location']}'"
        )

    def test_post_edit_valid_updates_amount_in_db(self, client):
        """After a valid POST the expense row must have the updated amount."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id)

        client.post(f"/expenses/{expense_id}/edit", data=_VALID_UPDATE)

        row = _fetch_expense(expense_id)
        assert abs(float(row["amount"]) - float(_VALID_UPDATE["amount"])) < 0.001, (
            f"Expected updated amount {_VALID_UPDATE['amount']}, got {row['amount']}"
        )

    def test_post_edit_valid_updates_category_in_db(self, client):
        """After a valid POST the expense row must have the updated category."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id)

        client.post(f"/expenses/{expense_id}/edit", data=_VALID_UPDATE)

        row = _fetch_expense(expense_id)
        assert row["category"] == _VALID_UPDATE["category"], (
            f"Expected updated category '{_VALID_UPDATE['category']}', got '{row['category']}'"
        )

    def test_post_edit_valid_updates_date_in_db(self, client):
        """After a valid POST the expense row must have the updated date."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id)

        client.post(f"/expenses/{expense_id}/edit", data=_VALID_UPDATE)

        row = _fetch_expense(expense_id)
        assert row["date"] == _VALID_UPDATE["date"], (
            f"Expected updated date '{_VALID_UPDATE['date']}', got '{row['date']}'"
        )

    def test_post_edit_valid_updates_description_in_db(self, client):
        """After a valid POST the expense row must have the updated description."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id)

        client.post(f"/expenses/{expense_id}/edit", data=_VALID_UPDATE)

        row = _fetch_expense(expense_id)
        assert row["description"] == _VALID_UPDATE["description"], (
            f"Expected updated description '{_VALID_UPDATE['description']}', got '{row['description']}'"
        )

    def test_post_edit_blank_description_stores_none(self, client):
        """A blank description on a valid POST must store NULL in the DB."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id)

        data = dict(_VALID_UPDATE, description="")
        client.post(f"/expenses/{expense_id}/edit", data=data)

        row = _fetch_expense(expense_id)
        assert row["description"] is None, (
            f"Expected NULL description after blank submit, got '{row['description']}'"
        )

    def test_post_edit_whitespace_description_stores_none(self, client):
        """A whitespace-only description on a valid POST must store NULL in the DB."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id)

        data = dict(_VALID_UPDATE, description="   ")
        client.post(f"/expenses/{expense_id}/edit", data=data)

        row = _fetch_expense(expense_id)
        assert row["description"] is None, (
            f"Expected NULL description after whitespace-only submit, got '{row['description']}'"
        )

    def test_post_edit_valid_updated_values_visible_on_profile(self, client):
        """After a valid update the new description must appear in the /profile transaction list."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id)

        unique_description = "UniqueEditedDescriptionXYZ9012"
        data = dict(_VALID_UPDATE, description=unique_description)
        client.post(f"/expenses/{expense_id}/edit", data=data)

        profile_resp = client.get("/profile")
        assert profile_resp.status_code == 200
        assert unique_description.encode() in profile_resp.data, (
            f"Expected updated description '{unique_description}' to appear on /profile"
        )

    def test_post_edit_all_valid_categories_accepted(self, client):
        """Each of the seven valid categories must result in a 302 redirect on edit."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])

        for cat in VALID_CATEGORIES:
            expense_id = _insert_expense(user_id)
            resp = client.post(
                f"/expenses/{expense_id}/edit",
                data=dict(_VALID_UPDATE, category=cat),
            )
            assert resp.status_code == 302, (
                f"Expected 302 for valid category '{cat}' on edit, got {resp.status_code}"
            )


# ---------------------------------------------------------------------------
# POST validation failures — amount
# ---------------------------------------------------------------------------


class TestEditExpenseValidationAmount:
    def test_post_edit_zero_amount_rerenders_form_with_error(self, client):
        """POST with amount=0 must re-render the form (200) with an error."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id)

        resp = client.post(
            f"/expenses/{expense_id}/edit", data=dict(_VALID_UPDATE, amount="0")
        )
        assert resp.status_code == 200, (
            f"Expected 200 re-render for amount=0, got {resp.status_code}"
        )
        assert (
            b"positive" in resp.data.lower()
            or b"error" in resp.data.lower()
            or b"valid" in resp.data.lower()
        ), "Expected an error message when amount is zero"

    def test_post_edit_zero_amount_does_not_update_db(self, client):
        """A zero amount must not update the DB row."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id)

        client.post(
            f"/expenses/{expense_id}/edit", data=dict(_VALID_UPDATE, amount="0")
        )

        row = _fetch_expense(expense_id)
        assert abs(float(row["amount"]) - _ORIGINAL_EXPENSE["amount"]) < 0.001, (
            "Expense amount must not change when validation fails (amount=0)"
        )

    def test_post_edit_blank_amount_rerenders_form_with_error(self, client):
        """POST with blank amount must re-render the form (200) with an error."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id)

        resp = client.post(
            f"/expenses/{expense_id}/edit", data=dict(_VALID_UPDATE, amount="")
        )
        assert resp.status_code == 200, (
            f"Expected 200 re-render for missing amount, got {resp.status_code}"
        )
        assert (
            b"amount" in resp.data.lower()
            or b"error" in resp.data.lower()
            or b"valid" in resp.data.lower()
        ), "Expected an error message when amount is blank"

    def test_post_edit_blank_amount_does_not_update_db(self, client):
        """A blank amount must not update the DB row."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id)

        client.post(f"/expenses/{expense_id}/edit", data=dict(_VALID_UPDATE, amount=""))

        row = _fetch_expense(expense_id)
        assert abs(float(row["amount"]) - _ORIGINAL_EXPENSE["amount"]) < 0.001, (
            "Expense amount must not change when validation fails (blank amount)"
        )

    def test_post_edit_negative_amount_rerenders_form_with_error(self, client):
        """POST with a negative amount must re-render the form (200) with an error."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id)

        resp = client.post(
            f"/expenses/{expense_id}/edit", data=dict(_VALID_UPDATE, amount="-25")
        )
        assert resp.status_code == 200, (
            f"Expected 200 re-render for negative amount, got {resp.status_code}"
        )
        assert b"positive" in resp.data.lower() or b"error" in resp.data.lower(), (
            "Expected an error message for negative amount"
        )

    def test_post_edit_negative_amount_does_not_update_db(self, client):
        """A negative amount must not update the DB row."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id)

        client.post(
            f"/expenses/{expense_id}/edit", data=dict(_VALID_UPDATE, amount="-25")
        )

        row = _fetch_expense(expense_id)
        assert abs(float(row["amount"]) - _ORIGINAL_EXPENSE["amount"]) < 0.001, (
            "Expense amount must not change when validation fails (negative amount)"
        )

    def test_post_edit_nonnumeric_amount_rerenders_form_with_error(self, client):
        """POST with a non-numeric amount must re-render the form (200) with an error."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id)

        resp = client.post(
            f"/expenses/{expense_id}/edit", data=dict(_VALID_UPDATE, amount="abc")
        )
        assert resp.status_code == 200, (
            f"Expected 200 re-render for non-numeric amount, got {resp.status_code}"
        )
        assert (
            b"valid" in resp.data.lower()
            or b"number" in resp.data.lower()
            or b"error" in resp.data.lower()
        ), "Expected an error message for non-numeric amount"


# ---------------------------------------------------------------------------
# POST validation failures — category
# ---------------------------------------------------------------------------


class TestEditExpenseValidationCategory:
    def test_post_edit_invalid_category_rerenders_form_with_error(self, client):
        """POST with a category not in the fixed list must re-render the form (200) with an error."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id)

        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data=dict(_VALID_UPDATE, category="Gambling"),
        )
        assert resp.status_code == 200, (
            f"Expected 200 re-render for invalid category, got {resp.status_code}"
        )
        assert (
            b"category" in resp.data.lower()
            or b"valid" in resp.data.lower()
            or b"error" in resp.data.lower()
        ), "Expected an error message for invalid category"

    def test_post_edit_invalid_category_does_not_update_db(self, client):
        """An invalid category must not update the DB row."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id)

        client.post(
            f"/expenses/{expense_id}/edit",
            data=dict(_VALID_UPDATE, category="Gambling"),
        )

        row = _fetch_expense(expense_id)
        assert row["category"] == _ORIGINAL_EXPENSE["category"], (
            "Expense category must not change when validation fails (invalid category)"
        )

    def test_post_edit_empty_category_rerenders_form_with_error(self, client):
        """POST with an empty category must re-render the form (200) with an error."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id)

        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data=dict(_VALID_UPDATE, category=""),
        )
        assert resp.status_code == 200, (
            f"Expected 200 re-render for empty category, got {resp.status_code}"
        )
        assert (
            b"category" in resp.data.lower()
            or b"valid" in resp.data.lower()
            or b"error" in resp.data.lower()
        ), "Expected an error message for empty category"


# ---------------------------------------------------------------------------
# POST validation failures — date
# ---------------------------------------------------------------------------


class TestEditExpenseValidationDate:
    def test_post_edit_blank_date_rerenders_form_with_error(self, client):
        """POST with a missing/blank date must re-render the form (200) with an error."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id)

        resp = client.post(
            f"/expenses/{expense_id}/edit", data=dict(_VALID_UPDATE, date="")
        )
        assert resp.status_code == 200, (
            f"Expected 200 re-render for blank date, got {resp.status_code}"
        )
        assert (
            b"date" in resp.data.lower()
            or b"valid" in resp.data.lower()
            or b"error" in resp.data.lower()
        ), "Expected an error message for blank date"

    def test_post_edit_blank_date_does_not_update_db(self, client):
        """A blank date must not update the DB row."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id)

        client.post(f"/expenses/{expense_id}/edit", data=dict(_VALID_UPDATE, date=""))

        row = _fetch_expense(expense_id)
        assert row["date"] == _ORIGINAL_EXPENSE["date"], (
            "Expense date must not change when validation fails (blank date)"
        )

    def test_post_edit_malformed_date_rerenders_form_with_error(self, client):
        """POST with a date in wrong format must re-render the form (200) with an error."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id)

        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data=dict(_VALID_UPDATE, date="15-03-2026"),
        )
        assert resp.status_code == 200, (
            f"Expected 200 re-render for malformed date '15-03-2026', got {resp.status_code}"
        )
        assert (
            b"date" in resp.data.lower()
            or b"valid" in resp.data.lower()
            or b"error" in resp.data.lower()
        ), "Expected an error message for malformed date"

    def test_post_edit_invalid_date_string_rerenders_form(self, client):
        """POST with a completely invalid date string must re-render the form (200)."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id)

        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data=dict(_VALID_UPDATE, date="not-a-date"),
        )
        assert resp.status_code == 200, (
            f"Expected 200 re-render for 'not-a-date', got {resp.status_code}"
        )


# ---------------------------------------------------------------------------
# Pre-fill submitted values on validation failure
# ---------------------------------------------------------------------------


class TestEditExpensePreFillOnValidationError:
    def test_post_edit_prefills_submitted_amount_on_error(self, client):
        """On validation error the submitted amount (not the original) must appear in the form."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id)

        # Trigger error via invalid category; amount is parseable so it gets echoed
        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": "77.77",
                "category": "NotValid",
                "date": "2026-05-01",
                "description": "",
            },
        )
        assert resp.status_code == 200
        assert b"77.77" in resp.data, (
            "Expected submitted amount '77.77' pre-filled in the re-rendered form (not the original)"
        )

    def test_post_edit_prefills_submitted_category_on_error(self, client):
        """On validation error the submitted category must appear in the re-rendered form."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id)

        # Trigger error via bad date; category is valid so it gets echoed
        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": "10.00",
                "category": "Bills",
                "date": "bad-date",
                "description": "",
            },
        )
        assert resp.status_code == 200
        assert b"Bills" in resp.data, (
            "Expected submitted category 'Bills' to appear in the re-rendered form"
        )

    def test_post_edit_prefills_submitted_date_on_error(self, client):
        """On validation error the submitted date must appear in the re-rendered form."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id)

        # Trigger error via negative amount; date gets echoed as-is
        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": "-1",
                "category": "Food",
                "date": "2026-07-04",
                "description": "",
            },
        )
        assert resp.status_code == 200
        assert b"2026-07-04" in resp.data, (
            "Expected submitted date '2026-07-04' to be pre-filled in the re-rendered form"
        )

    def test_post_edit_prefills_submitted_description_on_error(self, client):
        """On validation error the submitted description must appear in the re-rendered form."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id)

        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": "0",
                "category": "Food",
                "date": "2026-05-14",
                "description": "My new note",
            },
        )
        assert resp.status_code == 200
        assert b"My new note" in resp.data, (
            "Expected submitted description 'My new note' to appear in the re-rendered form"
        )

    def test_post_edit_prefills_submitted_values_not_original_db_values(self, client):
        """On validation failure the form must echo submitted values, not original DB values."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(
            user_id, amount=99.99, description="Original description"
        )

        # Submit completely different values but trigger error via zero amount
        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": "0",
                "category": "Shopping",
                "date": "2026-06-01",
                "description": "Submitted description",
            },
        )
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")
        # The submitted description should be present
        assert "Submitted description" in body, (
            "Expected the submitted description to appear in the re-rendered form"
        )
        # The original description should NOT be present (it was replaced by the submitted value)
        assert "Original description" not in body, (
            "The original DB description must not override the submitted value on re-render"
        )


# ---------------------------------------------------------------------------
# Profile page: Edit link for each transaction
# ---------------------------------------------------------------------------


class TestProfileEditLinks:
    def test_profile_has_edit_link_for_each_transaction(self, client):
        """Each transaction row on /profile must contain an 'Edit' link."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        _insert_expense(user_id)

        resp = client.get("/profile")
        assert resp.status_code == 200
        assert b"Edit" in resp.data, (
            "Expected at least one 'Edit' link on the /profile page"
        )

    def test_profile_edit_link_points_to_correct_url(self, client):
        """The Edit link on /profile must point to /expenses/<id>/edit for the transaction."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id)

        resp = client.get("/profile")
        assert resp.status_code == 200
        expected_url = f"/expenses/{expense_id}/edit".encode()
        assert expected_url in resp.data, (
            f"Expected href '{expected_url.decode()}' to appear in /profile page HTML"
        )

    def test_profile_edit_link_is_functional(self, client):
        """Following the Edit link from /profile must return 200 for the edit form."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id)

        resp = client.get(f"/expenses/{expense_id}/edit")
        assert resp.status_code == 200, (
            f"Expected 200 when following the edit link for expense {expense_id}"
        )

    def test_profile_multiple_transactions_each_have_edit_link(self, client):
        """Multiple transactions on /profile must each carry their own correct edit link."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])

        id_a = _insert_expense(user_id, description="Expense A")
        id_b = _insert_expense(user_id, description="Expense B")

        resp = client.get("/profile")
        assert resp.status_code == 200

        for eid in (id_a, id_b):
            expected_url = f"/expenses/{eid}/edit".encode()
            assert expected_url in resp.data, (
                f"Expected edit link for expense id={eid} to appear on /profile"
            )


# ---------------------------------------------------------------------------
# DB helper: get_expense_by_id
# ---------------------------------------------------------------------------


class TestGetExpenseByIdHelper:
    def test_get_expense_by_id_is_defined(self):
        """get_expense_by_id must be importable from database.db."""
        assert hasattr(db_module, "get_expense_by_id"), (
            "Expected get_expense_by_id to be defined in database/db.py"
        )
        assert callable(db_module.get_expense_by_id), (
            "Expected get_expense_by_id to be callable"
        )

    def test_get_expense_by_id_returns_row_for_existing_id(self, client, app):
        """get_expense_by_id must return a row when the id exists."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id)

        row = db_module.get_expense_by_id(expense_id)
        assert row is not None, (
            f"Expected get_expense_by_id to return a row for id={expense_id}"
        )

    def test_get_expense_by_id_returns_none_for_missing_id(self, client, app):
        """get_expense_by_id must return None when the id does not exist."""
        _register_and_login(client)
        row = db_module.get_expense_by_id(99999)
        assert row is None, (
            "Expected get_expense_by_id to return None for a non-existent id"
        )

    def test_get_expense_by_id_returns_correct_data(self, client, app):
        """get_expense_by_id must return the correct expense data."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(
            user_id,
            amount=55.00,
            category="Bills",
            date="2026-02-28",
            description="Test bill",
        )

        row = db_module.get_expense_by_id(expense_id)
        assert row is not None
        assert abs(float(row["amount"]) - 55.00) < 0.001, (
            f"Expected amount 55.00, got {row['amount']}"
        )
        assert row["category"] == "Bills", (
            f"Expected category 'Bills', got '{row['category']}'"
        )
        assert row["date"] == "2026-02-28", (
            f"Expected date '2026-02-28', got '{row['date']}'"
        )
        assert row["description"] == "Test bill", (
            f"Expected description 'Test bill', got '{row['description']}'"
        )

    def test_get_expense_by_id_uses_parameterised_query(self):
        """get_expense_by_id source must use ? placeholders, not f-strings or .format() in SQL."""
        source = inspect.getsource(db_module.get_expense_by_id)
        assert '".format(' not in source, (
            "get_expense_by_id must not use .format() in SQL strings"
        )
        assert 'f"' not in source or "?" in source, (
            "get_expense_by_id must not build SQL via f-strings without ? placeholders"
        )
        assert "?" in source, (
            "get_expense_by_id must use ? placeholders in its SQL query"
        )


# ---------------------------------------------------------------------------
# DB helper: update_expense
# ---------------------------------------------------------------------------


class TestUpdateExpenseHelper:
    def test_update_expense_is_defined(self):
        """update_expense must be importable from database.db."""
        assert hasattr(db_module, "update_expense"), (
            "Expected update_expense to be defined in database/db.py"
        )
        assert callable(db_module.update_expense), (
            "Expected update_expense to be callable"
        )

    def test_update_expense_updates_the_row(self, client, app):
        """update_expense must modify the matching row in the DB."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id)

        db_module.update_expense(
            expense_id, user_id, 200.00, "Entertainment", "2026-04-10", "Concert"
        )

        row = _fetch_expense(expense_id)
        assert abs(float(row["amount"]) - 200.00) < 0.001, (
            f"Expected amount 200.00 after update_expense, got {row['amount']}"
        )
        assert row["category"] == "Entertainment", (
            f"Expected category 'Entertainment' after update_expense, got '{row['category']}'"
        )
        assert row["date"] == "2026-04-10", (
            f"Expected date '2026-04-10' after update_expense, got '{row['date']}'"
        )
        assert row["description"] == "Concert", (
            f"Expected description 'Concert' after update_expense, got '{row['description']}'"
        )

    def test_update_expense_returns_rows_affected(self, client, app):
        """update_expense must return the number of rows affected (1 on success)."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id)

        result = db_module.update_expense(
            expense_id, user_id, 10.00, "Food", "2026-05-01", None
        )
        assert result == 1, (
            f"Expected update_expense to return 1 row affected, got {result}"
        )

    def test_update_expense_returns_zero_for_wrong_user(self, client, app):
        """update_expense must return 0 (and not modify the row) when user_id does not match."""
        _register_and_login(client, _OTHER_USER)
        owner_id = _get_user_id(_OTHER_USER["email"])
        expense_id = _insert_expense(owner_id)

        _register_and_login(client, _USER)
        attacker_id = _get_user_id(_USER["email"])

        result = db_module.update_expense(
            expense_id, attacker_id, 999.00, "Other", "2026-01-01", None
        )
        assert result == 0, (
            f"Expected update_expense to return 0 when user_id doesn't match, got {result}"
        )

        row = _fetch_expense(expense_id)
        assert abs(float(row["amount"]) - _ORIGINAL_EXPENSE["amount"]) < 0.001, (
            "Expense must not be modified when update_expense is called with a mismatched user_id"
        )

    def test_update_expense_filters_by_both_id_and_user_id(self):
        """update_expense source must filter by both id AND user_id in its WHERE clause."""
        source = inspect.getsource(db_module.update_expense)
        # Both id and user_id must appear in the WHERE portion
        assert "user_id" in source, (
            "update_expense SQL must reference user_id in the WHERE clause"
        )
        # The WHERE clause should include both conditions
        where_portion = source[source.lower().find("where") :]
        assert "id" in where_portion.lower(), (
            "update_expense SQL WHERE clause must reference the expense id"
        )
        assert "user_id" in where_portion.lower(), (
            "update_expense SQL WHERE clause must reference user_id"
        )

    def test_update_expense_uses_parameterised_query(self):
        """update_expense source must use ? placeholders, not f-strings or .format() in SQL."""
        source = inspect.getsource(db_module.update_expense)
        assert '".format(' not in source, (
            "update_expense must not use .format() in SQL strings"
        )
        assert "?" in source, "update_expense must use ? placeholders in its SQL query"

    def test_update_expense_signature(self):
        """update_expense must accept (expense_id, user_id, amount, category, expense_date, description)."""
        sig = inspect.signature(db_module.update_expense)
        params = list(sig.parameters.keys())
        expected = [
            "expense_id",
            "user_id",
            "amount",
            "category",
            "expense_date",
            "description",
        ]
        assert params == expected, (
            f"Expected update_expense signature {expected}, got {params}"
        )


# ---------------------------------------------------------------------------
# Template: no hardcoded hex colours in edit_expense.html
# ---------------------------------------------------------------------------


class TestEditExpenseTemplate:
    def test_edit_expense_template_no_hardcoded_hex_colours(self, client):
        """edit_expense.html must not contain hardcoded hex colour values in inline styles."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        expense_id = _insert_expense(user_id)

        resp = client.get(f"/expenses/{expense_id}/edit")
        body = resp.data.decode("utf-8")

        hex_in_style = re.compile(r'style="[^"]*#[0-9a-fA-F]{3,6}\b[^"]*"')
        matches = hex_in_style.findall(body)
        assert not matches, (
            f"Found hardcoded hex colour(s) in inline style attributes: {matches}"
        )
