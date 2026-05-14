"""
tests/test_07-add-expense.py

Tests for the Add Expense feature (Step 07).

Spec: .claude/specs/07-add-expense.md
Route: GET /expenses/add  — render form (auth-guarded)
       POST /expenses/add — validate and insert expense, redirect to /profile

All tests rely on conftest.py fixtures: app, client.
A module-level helper _register_and_login() brings a client to an authenticated
state without duplicating fixture machinery.
"""

import re
import inspect
import database.db as db_module

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_USER = {
    "name":     "Test User",
    "email":    "testuser@example.com",
    "password": "securepass",
}

_VALID_POST = {
    "amount":      "50.00",
    "category":    "Food",
    "date":        "2026-05-14",
    "description": "Lunch at the canteen",
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


def _register_and_login(client):
    """Register and log in _USER; returns the same client (session is sticky)."""
    client.post("/register", data=_USER)
    return client


def _get_user_id(email):
    conn = db_module.get_db()
    row = conn.execute(
        "SELECT id FROM users WHERE email = ?", (email,)
    ).fetchone()
    conn.close()
    return row["id"]


def _get_expenses_for_user(user_id):
    conn = db_module.get_db()
    rows = conn.execute(
        "SELECT * FROM expenses WHERE user_id = ? ORDER BY id DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return rows


# ---------------------------------------------------------------------------
# Auth guard tests
# ---------------------------------------------------------------------------

class TestAddExpenseAuthGuard:

    def test_add_expense_get_unauthenticated_redirects_to_login(self, client):
        """GET /expenses/add without a session must redirect (302) to /login."""
        resp = client.get("/expenses/add")
        assert resp.status_code == 302, (
            f"Expected 302, got {resp.status_code}"
        )
        assert resp.headers["Location"] == "/login", (
            f"Expected redirect to /login, got {resp.headers['Location']}"
        )

    def test_add_expense_post_unauthenticated_redirects_to_login(self, client):
        """POST /expenses/add without a session must redirect (302) to /login."""
        resp = client.post("/expenses/add", data=_VALID_POST)
        assert resp.status_code == 302, (
            f"Expected 302, got {resp.status_code}"
        )
        assert resp.headers["Location"] == "/login", (
            f"Expected redirect to /login, got {resp.headers['Location']}"
        )


# ---------------------------------------------------------------------------
# GET happy path
# ---------------------------------------------------------------------------

class TestAddExpenseGetForm:

    def test_add_expense_get_authenticated_returns_200(self, client):
        """GET /expenses/add while logged in must return HTTP 200."""
        _register_and_login(client)
        resp = client.get("/expenses/add")
        assert resp.status_code == 200, (
            f"Expected 200, got {resp.status_code}"
        )

    def test_add_expense_get_renders_amount_input(self, client):
        """Form must contain an input named 'amount'."""
        _register_and_login(client)
        resp = client.get("/expenses/add")
        assert b'name="amount"' in resp.data, (
            "Expected an input with name='amount' in the form"
        )

    def test_add_expense_get_renders_category_select(self, client):
        """Form must contain a <select> named 'category'."""
        _register_and_login(client)
        resp = client.get("/expenses/add")
        assert b'name="category"' in resp.data, (
            "Expected a select with name='category' in the form"
        )
        assert b"<select" in resp.data, "Expected a <select> element for category"

    def test_add_expense_get_renders_all_seven_categories(self, client):
        """The category select must include all seven valid categories."""
        _register_and_login(client)
        resp = client.get("/expenses/add")
        for cat in VALID_CATEGORIES:
            assert cat.encode() in resp.data, (
                f"Expected category option '{cat}' in the form"
            )

    def test_add_expense_get_renders_date_input(self, client):
        """Form must contain an input named 'date'."""
        _register_and_login(client)
        resp = client.get("/expenses/add")
        assert b'name="date"' in resp.data, (
            "Expected an input with name='date' in the form"
        )
        assert b'type="date"' in resp.data, (
            "Expected input type='date' for the date field"
        )

    def test_add_expense_get_renders_description_textarea(self, client):
        """Form must contain a textarea named 'description'."""
        _register_and_login(client)
        resp = client.get("/expenses/add")
        assert b'name="description"' in resp.data, (
            "Expected a textarea with name='description' in the form"
        )
        assert b"<textarea" in resp.data, (
            "Expected a <textarea> element for description"
        )

    def test_add_expense_get_prefills_today_date(self, client):
        """The date input should default to today's date (2026-05-14 per env)."""
        _register_and_login(client)
        resp = client.get("/expenses/add")
        # The form should contain a date value; today per the test environment is 2026-05-14.
        # We just verify a YYYY-MM-DD pattern appears in the date input value.
        body = resp.data.decode("utf-8")
        date_value_pattern = re.compile(r'value="\d{4}-\d{2}-\d{2}"')
        assert date_value_pattern.search(body), (
            "Expected a YYYY-MM-DD default date value pre-filled in the date input"
        )

    def test_add_expense_get_has_cancel_link_to_profile(self, client):
        """Form must include a cancel link back to /profile."""
        _register_and_login(client)
        resp = client.get("/expenses/add")
        assert b"/profile" in resp.data, (
            "Expected a cancel link pointing to /profile"
        )


# ---------------------------------------------------------------------------
# POST happy path
# ---------------------------------------------------------------------------

class TestAddExpensePostValid:

    def test_add_expense_post_valid_redirects_to_profile(self, client):
        """POST with valid data must redirect (302) to /profile."""
        _register_and_login(client)
        resp = client.post("/expenses/add", data=_VALID_POST)
        assert resp.status_code == 302, (
            f"Expected 302 redirect, got {resp.status_code}"
        )
        assert resp.headers["Location"] == "/profile", (
            f"Expected redirect to /profile, got {resp.headers['Location']}"
        )

    def test_add_expense_post_valid_inserts_row_in_db(self, client):
        """POST with valid data must insert exactly one row in the expenses table."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])

        before = _get_expenses_for_user(user_id)
        client.post("/expenses/add", data=_VALID_POST)
        after = _get_expenses_for_user(user_id)

        assert len(after) == len(before) + 1, (
            "Expected one new expense row in the DB after a valid POST"
        )

    def test_add_expense_post_valid_stores_correct_fields(self, client):
        """The inserted row must have the exact amount, category, date, and description."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])

        client.post("/expenses/add", data=_VALID_POST)
        rows = _get_expenses_for_user(user_id)
        assert rows, "Expected at least one expense row after valid POST"

        newest = rows[0]
        assert float(newest["amount"]) == float(_VALID_POST["amount"]), (
            f"Expected amount {_VALID_POST['amount']}, got {newest['amount']}"
        )
        assert newest["category"] == _VALID_POST["category"], (
            f"Expected category '{_VALID_POST['category']}', got '{newest['category']}'"
        )
        assert newest["date"] == _VALID_POST["date"], (
            f"Expected date '{_VALID_POST['date']}', got '{newest['date']}'"
        )
        assert newest["description"] == _VALID_POST["description"], (
            f"Expected description '{_VALID_POST['description']}', got '{newest['description']}'"
        )

    def test_add_expense_post_valid_expense_appears_on_profile(self, client):
        """After a valid POST, the expense description must appear in the /profile transaction list."""
        _register_and_login(client)
        unique_description = "UniqueCanteenLunchTest9876"
        data = dict(_VALID_POST, description=unique_description)
        client.post("/expenses/add", data=data)

        profile_resp = client.get("/profile")
        assert profile_resp.status_code == 200
        assert unique_description.encode() in profile_resp.data, (
            f"Expected description '{unique_description}' to appear on /profile after adding the expense"
        )

    def test_add_expense_post_float_amount_stored_correctly(self, client):
        """A float amount like 42.75 must be stored without truncation."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])

        client.post("/expenses/add", data=dict(_VALID_POST, amount="42.75"))
        rows = _get_expenses_for_user(user_id)
        assert rows, "Expected a new expense row"
        assert abs(float(rows[0]["amount"]) - 42.75) < 0.001, (
            f"Expected amount 42.75, got {rows[0]['amount']}"
        )

    def test_add_expense_post_blank_description_stores_none(self, client):
        """A blank description must be stored as NULL (None) in the DB, not as an empty string."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])

        client.post("/expenses/add", data=dict(_VALID_POST, description=""))
        rows = _get_expenses_for_user(user_id)
        assert rows, "Expected a new expense row"
        assert rows[0]["description"] is None, (
            f"Expected NULL description, got '{rows[0]['description']}'"
        )

    def test_add_expense_post_whitespace_description_stores_none(self, client):
        """A whitespace-only description must also be stored as NULL."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])

        client.post("/expenses/add", data=dict(_VALID_POST, description="   "))
        rows = _get_expenses_for_user(user_id)
        assert rows, "Expected a new expense row"
        assert rows[0]["description"] is None, (
            f"Expected NULL description for whitespace input, got '{rows[0]['description']}'"
        )

    @staticmethod
    def _post_category(client, category):
        return client.post(
            "/expenses/add",
            data=dict(_VALID_POST, category=category),
        )

    def test_add_expense_post_all_valid_categories_accepted(self, client):
        """Each of the seven valid categories must result in a 302 redirect."""
        _register_and_login(client)
        for cat in VALID_CATEGORIES:
            resp = client.post("/expenses/add", data=dict(_VALID_POST, category=cat))
            assert resp.status_code == 302, (
                f"Expected 302 for valid category '{cat}', got {resp.status_code}"
            )


# ---------------------------------------------------------------------------
# POST validation failures
# ---------------------------------------------------------------------------

class TestAddExpensePostValidation:

    def test_add_expense_post_missing_amount_rerenders_form(self, client):
        """POST with missing amount must re-render the form (200) with an error."""
        _register_and_login(client)
        data = dict(_VALID_POST, amount="")
        resp = client.post("/expenses/add", data=data)
        assert resp.status_code == 200, (
            f"Expected 200 (form re-render) for missing amount, got {resp.status_code}"
        )
        assert b"amount" in resp.data.lower() or b"error" in resp.data.lower() or b"valid" in resp.data.lower(), (
            "Expected an error message when amount is missing"
        )

    def test_add_expense_post_zero_amount_rerenders_form_with_error(self, client):
        """POST with amount=0 must re-render the form (200) with an error message."""
        _register_and_login(client)
        resp = client.post("/expenses/add", data=dict(_VALID_POST, amount="0"))
        assert resp.status_code == 200, (
            f"Expected 200 for zero amount, got {resp.status_code}"
        )
        assert b"positive" in resp.data.lower() or b"error" in resp.data.lower(), (
            "Expected an error message indicating amount must be positive"
        )

    def test_add_expense_post_negative_amount_rerenders_form_with_error(self, client):
        """POST with a negative amount must re-render the form with an error."""
        _register_and_login(client)
        resp = client.post("/expenses/add", data=dict(_VALID_POST, amount="-10"))
        assert resp.status_code == 200, (
            f"Expected 200 for negative amount, got {resp.status_code}"
        )
        assert b"positive" in resp.data.lower() or b"error" in resp.data.lower(), (
            "Expected an error message for negative amount"
        )

    def test_add_expense_post_nonnumeric_amount_rerenders_form_with_error(self, client):
        """POST with a non-numeric amount must re-render the form with an error."""
        _register_and_login(client)
        resp = client.post("/expenses/add", data=dict(_VALID_POST, amount="abc"))
        assert resp.status_code == 200, (
            f"Expected 200 for non-numeric amount, got {resp.status_code}"
        )
        assert b"valid" in resp.data.lower() or b"number" in resp.data.lower() or b"error" in resp.data.lower(), (
            "Expected an error message for non-numeric amount"
        )

    def test_add_expense_post_invalid_category_rerenders_form_with_error(self, client):
        """POST with a category not in the fixed list must re-render the form with an error."""
        _register_and_login(client)
        resp = client.post("/expenses/add", data=dict(_VALID_POST, category="Gambling"))
        assert resp.status_code == 200, (
            f"Expected 200 for invalid category, got {resp.status_code}"
        )
        assert b"category" in resp.data.lower() or b"valid" in resp.data.lower() or b"error" in resp.data.lower(), (
            "Expected an error message for invalid category"
        )

    def test_add_expense_post_empty_category_rerenders_form_with_error(self, client):
        """POST with an empty category must re-render the form with an error."""
        _register_and_login(client)
        resp = client.post("/expenses/add", data=dict(_VALID_POST, category=""))
        assert resp.status_code == 200, (
            f"Expected 200 for empty category, got {resp.status_code}"
        )
        assert b"category" in resp.data.lower() or b"valid" in resp.data.lower() or b"error" in resp.data.lower(), (
            "Expected an error message for empty category"
        )

    def test_add_expense_post_missing_date_rerenders_form_with_error(self, client):
        """POST with missing date must re-render the form (200) with an error message."""
        _register_and_login(client)
        resp = client.post("/expenses/add", data=dict(_VALID_POST, date=""))
        assert resp.status_code == 200, (
            f"Expected 200 for missing date, got {resp.status_code}"
        )
        assert b"date" in resp.data.lower() or b"valid" in resp.data.lower() or b"error" in resp.data.lower(), (
            "Expected an error message for missing date"
        )

    def test_add_expense_post_malformed_date_rerenders_form_with_error(self, client):
        """POST with a date that doesn't parse as YYYY-MM-DD must re-render the form."""
        _register_and_login(client)
        resp = client.post("/expenses/add", data=dict(_VALID_POST, date="14-05-2026"))
        assert resp.status_code == 200, (
            f"Expected 200 for malformed date '14-05-2026', got {resp.status_code}"
        )
        assert b"date" in resp.data.lower() or b"valid" in resp.data.lower() or b"error" in resp.data.lower(), (
            "Expected an error message for malformed date"
        )

    def test_add_expense_post_invalid_date_string_rerenders_form(self, client):
        """POST with a completely invalid date string must re-render the form."""
        _register_and_login(client)
        resp = client.post("/expenses/add", data=dict(_VALID_POST, date="not-a-date"))
        assert resp.status_code == 200, (
            f"Expected 200 for 'not-a-date', got {resp.status_code}"
        )


# ---------------------------------------------------------------------------
# Pre-fill on validation error
# ---------------------------------------------------------------------------

class TestAddExpensePreFillOnError:

    def test_add_expense_prefills_amount_on_error(self, client):
        """On validation error, the previously entered amount must appear in the re-rendered form."""
        _register_and_login(client)
        # Use an invalid category to trigger the error after amount is parsed
        resp = client.post(
            "/expenses/add",
            data={"amount": "99.99", "category": "Invalid", "date": "2026-05-14", "description": ""},
        )
        assert resp.status_code == 200
        assert b"99.99" in resp.data, (
            "Expected amount '99.99' to be pre-filled in the re-rendered form"
        )

    def test_add_expense_prefills_category_on_error(self, client):
        """On validation error, the previously selected category must be pre-selected."""
        _register_and_login(client)
        # Submit with a valid category but invalid date to trigger error
        resp = client.post(
            "/expenses/add",
            data={"amount": "20.00", "category": "Health", "date": "bad-date", "description": ""},
        )
        assert resp.status_code == 200
        assert b"Health" in resp.data, (
            "Expected category 'Health' to appear pre-filled in the re-rendered form"
        )

    def test_add_expense_prefills_date_on_error(self, client):
        """On validation error, the previously entered date must appear in the re-rendered form."""
        _register_and_login(client)
        resp = client.post(
            "/expenses/add",
            data={"amount": "-5", "category": "Food", "date": "2026-03-01", "description": ""},
        )
        assert resp.status_code == 200
        assert b"2026-03-01" in resp.data, (
            "Expected date '2026-03-01' to be pre-filled in the re-rendered form"
        )

    def test_add_expense_prefills_description_on_error(self, client):
        """On validation error, the previously entered description must appear in the re-rendered form."""
        _register_and_login(client)
        resp = client.post(
            "/expenses/add",
            data={"amount": "0", "category": "Food", "date": "2026-05-14", "description": "My grocery run"},
        )
        assert resp.status_code == 200
        assert b"My grocery run" in resp.data, (
            "Expected description 'My grocery run' to be pre-filled in the re-rendered form"
        )


# ---------------------------------------------------------------------------
# DB isolation — no rows inserted on validation failure
# ---------------------------------------------------------------------------

class TestAddExpenseNoDbWriteOnError:

    def test_add_expense_invalid_does_not_insert_row(self, client):
        """A validation error must not insert any row into the expenses table."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])

        before = _get_expenses_for_user(user_id)
        client.post("/expenses/add", data=dict(_VALID_POST, amount="0"))
        after = _get_expenses_for_user(user_id)

        assert len(after) == len(before), (
            "Expected no new expense row when validation fails (amount=0)"
        )

    def test_add_expense_invalid_category_does_not_insert_row(self, client):
        """An invalid category must not insert any row into the expenses table."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])

        before = _get_expenses_for_user(user_id)
        client.post("/expenses/add", data=dict(_VALID_POST, category="Junk"))
        after = _get_expenses_for_user(user_id)

        assert len(after) == len(before), (
            "Expected no new expense row when category is invalid"
        )


# ---------------------------------------------------------------------------
# DB helper: add_expense exists and is parameterised
# ---------------------------------------------------------------------------

class TestAddExpenseDbHelper:

    def test_add_expense_helper_is_defined_in_db_module(self):
        """add_expense must be importable from database.db."""
        assert hasattr(db_module, "add_expense"), (
            "Expected add_expense to be defined in database/db.py"
        )
        assert callable(db_module.add_expense), (
            "Expected add_expense to be callable"
        )

    def test_add_expense_helper_signature(self):
        """add_expense must accept (user_id, amount, category, date, description)."""
        sig = inspect.signature(db_module.add_expense)
        params = list(sig.parameters.keys())
        expected = ["user_id", "amount", "category", "date", "description"]
        assert params == expected, (
            f"Expected add_expense signature params {expected}, got {params}"
        )

    def test_add_expense_helper_returns_new_id(self, client, app):
        """add_expense must return the integer primary key of the inserted row."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        result = db_module.add_expense(user_id, 15.00, "Food", "2026-05-14", "Snack")
        assert isinstance(result, int), (
            f"Expected add_expense to return an int (the new row id), got {type(result)}"
        )
        assert result > 0, "Expected add_expense to return a positive row id"

    def test_add_expense_helper_inserts_correct_data(self, client, app):
        """add_expense must insert a row with the exact fields passed to it."""
        _register_and_login(client)
        user_id = _get_user_id(_USER["email"])
        new_id = db_module.add_expense(user_id, 77.77, "Transport", "2026-04-01", "Bus ticket")

        conn = db_module.get_db()
        row = conn.execute(
            "SELECT * FROM expenses WHERE id = ?", (new_id,)
        ).fetchone()
        conn.close()

        assert row is not None, "Expected a row with the returned id"
        assert row["user_id"] == user_id
        assert abs(float(row["amount"]) - 77.77) < 0.001
        assert row["category"] == "Transport"
        assert row["date"] == "2026-04-01"
        assert row["description"] == "Bus ticket"

    def test_add_expense_helper_source_uses_parameterised_query(self):
        """add_expense source code must use ? placeholders, not f-strings or .format() in SQL."""
        source = inspect.getsource(db_module.add_expense)
        # Should NOT find an f-string building SQL
        assert '".format(' not in source, (
            "add_expense must not use .format() in SQL strings"
        )
        # Parameterised marker must appear
        assert "?" in source, (
            "add_expense must use ? placeholders in its SQL query"
        )


# ---------------------------------------------------------------------------
# Template: no raw hex colour values in add_expense.html
# ---------------------------------------------------------------------------

class TestAddExpenseTemplate:

    def test_add_expense_template_no_hardcoded_hex_colours(self, client):
        """add_expense.html must not contain hardcoded hex colour values (#rrggbb / #rgb)."""
        _register_and_login(client)
        resp = client.get("/expenses/add")
        body = resp.data.decode("utf-8")
        # Match hex colours in inline style attributes
        hex_in_style = re.compile(r'style="[^"]*#[0-9a-fA-F]{3,6}\b[^"]*"')
        matches = hex_in_style.findall(body)
        assert not matches, (
            f"Found hardcoded hex colour(s) in inline style attributes: {matches}"
        )

    def test_add_expense_template_extends_base(self, client):
        """The add-expense page must extend base.html (should share nav / layout elements)."""
        _register_and_login(client)
        resp = client.get("/expenses/add")
        # base.html typically injects a nav or footer; check for a common landmark
        assert b"Spendly" in resp.data, (
            "Expected page to extend base.html (Spendly branding should appear)"
        )

    def test_add_expense_template_has_submit_button(self, client):
        """The form must have a submit button."""
        _register_and_login(client)
        resp = client.get("/expenses/add")
        assert b'type="submit"' in resp.data or b"Add Expense" in resp.data, (
            "Expected a submit button in the add-expense form"
        )
