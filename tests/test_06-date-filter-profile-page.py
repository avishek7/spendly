"""
tests/test_06-date-filter-profile-page.py

Tests for the date-filter feature on the /profile route (Step 06).

Spec: .claude/specs/06-date-filter-profile-page.md

Coverage:
- Auth guard (bare, with period param, with custom range)
- Default (no params) → all-time view
- ?period=all → all-time view
- ?period=7d → last-7-days window
- ?period=30d → last-30-days window
- ?period=month → current calendar month
- Unknown/invalid period value → falls back to all-time
- Custom range (?from=&to=) → only expenses in that range
- Only ?from supplied (no ?to) → falls back to period param
- Only ?to supplied (no ?from) → falls back to period param
- Unparseable date strings → silently fall back to all-time
- DB-level filtering correctness (different periods return different counts)
- Template: filter bar elements rendered (all 4 preset labels, date inputs, Apply button)
- Template: filter form uses GET method
- Template: active preset button carries `active` CSS class
- Template: filter-custom form carries `active` class when custom range is active
- Template: filter label displayed in filter-label-text span
"""

import re
import sqlite3
from datetime import date, timedelta

import pytest
import database.db as db_module
from database.db import init_db
from app import app as flask_app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app(monkeypatch, tmp_path):
    """Isolated app instance backed by a per-test temp-file SQLite DB."""
    db_path = str(tmp_path / "test.db")

    def _test_get_db():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    monkeypatch.setattr(db_module, "get_db", _test_get_db)

    flask_app.config.update({
        "TESTING": True,
        "SECRET_KEY": "dev-secret-change-in-prod",
    })
    with flask_app.app_context():
        init_db()
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_client(client):
    """Test client with a registered and logged-in user."""
    client.post("/register", data={
        "name": "Test User",
        "email": "testuser@example.com",
        "password": "testpassword",
    })
    return client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_user_id(email="testuser@example.com"):
    conn = db_module.get_db()
    row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return row["id"]


def _seed_spread_expenses(user_id):
    """
    Insert expenses across a wide date range so different filter windows
    yield different non-overlapping subsets:

      - 2 expenses older than 30 days  → visible only under "All time"
      - 2 expenses between 8 and 29 days ago → in last-30d but NOT last-7d
      - 2 expenses within the last 6 days    → in last-7d, last-30d, and this-month
      - 1 expense today                      → in every window

    Total = 7 expenses.
    Dates are computed relative to today so tests remain correct on any run date.
    """
    today = date.today()
    rows = [
        # Old — only "All time"
        (user_id, 500.00, "Bills",         (today - timedelta(days=60)).isoformat(), "Old rent"),
        (user_id, 200.00, "Food",          (today - timedelta(days=45)).isoformat(), "Old groceries"),
        # Last-30d but NOT last-7d
        (user_id,  50.00, "Transport",     (today - timedelta(days=20)).isoformat(), "Bus pass"),
        (user_id,  30.00, "Health",        (today - timedelta(days=10)).isoformat(), "Pharmacy"),
        # Last-7d (days -5 and -3)
        (user_id,  15.00, "Entertainment", (today - timedelta(days=5)).isoformat(),  "Cinema"),
        (user_id,  25.00, "Shopping",      (today - timedelta(days=3)).isoformat(),  "Books"),
        # Today
        (user_id,  10.00, "Food",          today.isoformat(),                        "Coffee"),
    ]
    conn = db_module.get_db()
    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description)"
        " VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()


def _count_transactions_in_response(response_data: bytes) -> int:
    """
    Count transaction rows by the CSS class used on the date column cell.
    Matches the template: <td class="profile-td-date">
    """
    return response_data.count(b"profile-td-date")


def _get_filter_label_text(html: str) -> str:
    """
    Extract the text content from the filter-label-text span.
    Template renders: <span class="filter-label-text">Showing: {{ filter_label }}</span>
    Returns the full inner text including the "Showing: " prefix.
    """
    match = re.search(r'class="filter-label-text"[^>]*>\s*(.*?)\s*<', html, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

class TestAuthGuard:
    def test_unauthenticated_redirects_to_login(self, client):
        resp = client.get("/profile")
        assert resp.status_code == 302, "Expected redirect for unauthenticated user"
        assert "/login" in resp.headers["Location"], "Expected redirect target to be /login"

    def test_unauthenticated_with_period_param_redirects_to_login(self, client):
        resp = client.get("/profile?period=7d")
        assert resp.status_code == 302, "Auth guard must apply even when query params are present"
        assert "/login" in resp.headers["Location"], "Expected redirect to /login"

    def test_unauthenticated_with_custom_range_redirects_to_login(self, client):
        resp = client.get("/profile?from=2026-05-01&to=2026-05-07")
        assert resp.status_code == 302, "Auth guard must apply for custom date range requests"
        assert "/login" in resp.headers["Location"], "Expected redirect to /login"


# ---------------------------------------------------------------------------
# Default behaviour (no query params) → all-time
# ---------------------------------------------------------------------------

class TestDefaultAllTime:
    def test_no_params_returns_200(self, auth_client):
        resp = auth_client.get("/profile")
        assert resp.status_code == 200, "Profile page must return 200 for authenticated user"

    def test_no_params_shows_all_time_label(self, auth_client):
        user_id = _get_user_id()
        _seed_spread_expenses(user_id)
        resp = auth_client.get("/profile")
        label = _get_filter_label_text(resp.data.decode("utf-8"))
        assert "All time" in label, (
            f"Default view must display 'All time' in filter-label-text, got: '{label}'"
        )

    def test_no_params_shows_all_expenses(self, auth_client):
        user_id = _get_user_id()
        _seed_spread_expenses(user_id)
        resp = auth_client.get("/profile")
        count = _count_transactions_in_response(resp.data)
        assert count == 7, f"Expected 7 transactions for all-time view, got {count}"

    def test_no_params_active_period_is_all(self, auth_client):
        resp = auth_client.get("/profile")
        html = resp.data.decode("utf-8")
        # The "All time" anchor must carry the active class
        idx = html.find("All time")
        assert idx != -1, "All time button must be present in the page"
        surrounding = html[max(0, idx - 300): idx + 50]
        assert "active" in surrounding, (
            "The 'All time' button must carry the 'active' CSS class by default"
        )


# ---------------------------------------------------------------------------
# ?period=all explicit
# ---------------------------------------------------------------------------

class TestPeriodAll:
    def test_period_all_returns_200(self, auth_client):
        resp = auth_client.get("/profile?period=all")
        assert resp.status_code == 200, "?period=all must return 200"

    def test_period_all_shows_all_time_label(self, auth_client):
        user_id = _get_user_id()
        _seed_spread_expenses(user_id)
        resp = auth_client.get("/profile?period=all")
        label = _get_filter_label_text(resp.data.decode("utf-8"))
        assert "All time" in label, f"?period=all must display 'All time' label, got: '{label}'"

    def test_period_all_shows_all_expenses(self, auth_client):
        user_id = _get_user_id()
        _seed_spread_expenses(user_id)
        resp = auth_client.get("/profile?period=all")
        count = _count_transactions_in_response(resp.data)
        assert count == 7, f"?period=all must show all 7 expenses, got {count}"

    def test_period_all_active_class_on_all_button(self, auth_client):
        resp = auth_client.get("/profile?period=all")
        html = resp.data.decode("utf-8")
        idx = html.find("All time")
        assert idx != -1, "'All time' button must be in the page"
        surrounding = html[max(0, idx - 300): idx + 50]
        assert "active" in surrounding, (
            "The 'All time' button must carry the 'active' CSS class for ?period=all"
        )


# ---------------------------------------------------------------------------
# ?period=7d
# ---------------------------------------------------------------------------

class TestPeriodLast7Days:
    def test_period_7d_returns_200(self, auth_client):
        resp = auth_client.get("/profile?period=7d")
        assert resp.status_code == 200, "?period=7d must return 200"

    def test_period_7d_shows_last_7_days_label(self, auth_client):
        resp = auth_client.get("/profile?period=7d")
        label = _get_filter_label_text(resp.data.decode("utf-8"))
        assert "Last 7 days" in label, (
            f"?period=7d must display 'Last 7 days' label, got: '{label}'"
        )

    def test_period_7d_excludes_old_expenses(self, auth_client):
        user_id = _get_user_id()
        _seed_spread_expenses(user_id)
        resp = auth_client.get("/profile?period=7d")
        # Expenses within last 7 days: days -5, -3, today = 3 rows
        count = _count_transactions_in_response(resp.data)
        assert count == 3, (
            f"?period=7d must show only the 3 recent expenses, got {count}"
        )

    def test_period_7d_fewer_than_all_time(self, auth_client):
        user_id = _get_user_id()
        _seed_spread_expenses(user_id)
        all_resp = auth_client.get("/profile?period=all")
        week_resp = auth_client.get("/profile?period=7d")
        all_count = _count_transactions_in_response(all_resp.data)
        week_count = _count_transactions_in_response(week_resp.data)
        assert week_count < all_count, (
            "7-day filter must return fewer rows than all-time when older expenses exist"
        )

    def test_period_7d_stats_reflect_filtered_subset(self, auth_client):
        user_id = _get_user_id()
        _seed_spread_expenses(user_id)
        resp = auth_client.get("/profile?period=7d")
        # 3 expenses in last 7 days: 15 + 25 + 10 = 50.00
        assert b"50.00" in resp.data, (
            "Stats total must reflect only expenses within the last 7 days (expected 50.00)"
        )

    def test_period_7d_active_class_on_7d_button(self, auth_client):
        resp = auth_client.get("/profile?period=7d")
        html = resp.data.decode("utf-8")
        idx = html.find("Last 7 days")
        assert idx != -1, "'Last 7 days' button must be in the page"
        surrounding = html[max(0, idx - 300): idx + 50]
        assert "active" in surrounding, (
            "The 'Last 7 days' button must carry the 'active' CSS class when period=7d"
        )


# ---------------------------------------------------------------------------
# ?period=30d
# ---------------------------------------------------------------------------

class TestPeriodLast30Days:
    def test_period_30d_returns_200(self, auth_client):
        resp = auth_client.get("/profile?period=30d")
        assert resp.status_code == 200, "?period=30d must return 200"

    def test_period_30d_shows_last_30_days_label(self, auth_client):
        resp = auth_client.get("/profile?period=30d")
        label = _get_filter_label_text(resp.data.decode("utf-8"))
        assert "Last 30 days" in label, (
            f"?period=30d must display 'Last 30 days' label, got: '{label}'"
        )

    def test_period_30d_includes_more_than_7d(self, auth_client):
        user_id = _get_user_id()
        _seed_spread_expenses(user_id)
        resp_30d = auth_client.get("/profile?period=30d")
        resp_7d = auth_client.get("/profile?period=7d")
        count_30d = _count_transactions_in_response(resp_30d.data)
        count_7d = _count_transactions_in_response(resp_7d.data)
        assert count_30d > count_7d, (
            "30-day filter must include more expenses than 7-day filter"
        )

    def test_period_30d_excludes_60_day_old_expenses(self, auth_client):
        user_id = _get_user_id()
        _seed_spread_expenses(user_id)
        resp = auth_client.get("/profile?period=30d")
        # Seeded 5 expenses within 30 days (days -20, -10, -5, -3, today)
        count = _count_transactions_in_response(resp.data)
        assert count == 5, (
            f"?period=30d must show 5 expenses (excluding the 2 older than 30 days), got {count}"
        )

    def test_period_30d_active_class_on_30d_button(self, auth_client):
        resp = auth_client.get("/profile?period=30d")
        html = resp.data.decode("utf-8")
        idx = html.find("Last 30 days")
        assert idx != -1, "'Last 30 days' button must be in the page"
        surrounding = html[max(0, idx - 300): idx + 50]
        assert "active" in surrounding, (
            "The 'Last 30 days' button must carry the 'active' CSS class when period=30d"
        )


# ---------------------------------------------------------------------------
# ?period=month
# ---------------------------------------------------------------------------

class TestPeriodThisMonth:
    def test_period_month_returns_200(self, auth_client):
        resp = auth_client.get("/profile?period=month")
        assert resp.status_code == 200, "?period=month must return 200"

    def test_period_month_shows_this_month_label(self, auth_client):
        resp = auth_client.get("/profile?period=month")
        label = _get_filter_label_text(resp.data.decode("utf-8"))
        assert "This month" in label, (
            f"?period=month must display 'This month' label, got: '{label}'"
        )

    def test_period_month_excludes_expenses_before_month_start(self, auth_client):
        """
        Seed one expense on the first day of the current month and one on
        the day before the month started; only the current-month one should appear.
        """
        user_id = _get_user_id()
        today = date.today()
        first_of_month = today.replace(day=1)
        day_before_month = first_of_month - timedelta(days=1)

        conn = db_module.get_db()
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description)"
            " VALUES (?, ?, ?, ?, ?)",
            [
                (user_id, 10.00, "Food", first_of_month.isoformat(), "In month"),
                (user_id, 20.00, "Food", day_before_month.isoformat(), "Before month"),
            ],
        )
        conn.commit()
        conn.close()

        resp = auth_client.get("/profile?period=month")
        count = _count_transactions_in_response(resp.data)
        assert count == 1, (
            f"'This month' filter must exclude the pre-month expense; got {count} rows"
        )

    def test_period_month_active_class_on_month_button(self, auth_client):
        resp = auth_client.get("/profile?period=month")
        html = resp.data.decode("utf-8")
        idx = html.find("This month")
        assert idx != -1, "'This month' button must be in the page"
        surrounding = html[max(0, idx - 300): idx + 50]
        assert "active" in surrounding, (
            "The 'This month' button must carry the 'active' CSS class when period=month"
        )


# ---------------------------------------------------------------------------
# Unknown / invalid period value → falls back to all-time
# ---------------------------------------------------------------------------

class TestUnknownPeriodFallback:
    @pytest.mark.parametrize("bad_period", [
        "week", "ytd", "1y", "LAST7", "'; DROP TABLE expenses; --",
    ])
    def test_unknown_period_returns_200(self, auth_client, bad_period):
        resp = auth_client.get(f"/profile?period={bad_period}")
        assert resp.status_code == 200, (
            f"Unknown period '{bad_period}' must not crash the server"
        )

    @pytest.mark.parametrize("bad_period", [
        "week", "ytd", "1y", "LAST7", "'; DROP TABLE expenses; --",
    ])
    def test_unknown_period_falls_back_to_all_time_label(self, auth_client, bad_period):
        resp = auth_client.get(f"/profile?period={bad_period}")
        label = _get_filter_label_text(resp.data.decode("utf-8"))
        assert "All time" in label, (
            f"Unknown period '{bad_period}' must silently fall back to 'All time', got: '{label}'"
        )

    @pytest.mark.parametrize("bad_period", [
        "week", "ytd", "1y", "LAST7",
    ])
    def test_unknown_period_falls_back_shows_all_expenses(self, auth_client, bad_period):
        user_id = _get_user_id()
        _seed_spread_expenses(user_id)
        resp = auth_client.get(f"/profile?period={bad_period}")
        count = _count_transactions_in_response(resp.data)
        assert count == 7, (
            f"Unknown period '{bad_period}' must show all 7 expenses (got {count})"
        )

    def test_empty_period_falls_back_to_all_time(self, auth_client):
        """Empty string for period (i.e. ?period=) must fall back to all-time."""
        user_id = _get_user_id()
        _seed_spread_expenses(user_id)
        resp = auth_client.get("/profile?period=")
        assert resp.status_code == 200
        label = _get_filter_label_text(resp.data.decode("utf-8"))
        assert "All time" in label, (
            f"?period= (empty) must fall back to 'All time', got: '{label}'"
        )


# ---------------------------------------------------------------------------
# Custom date range (?from=&to=)
# ---------------------------------------------------------------------------

class TestCustomDateRange:
    def test_custom_range_returns_200(self, auth_client):
        today = date.today()
        date_from = (today - timedelta(days=5)).isoformat()
        date_to = today.isoformat()
        resp = auth_client.get(f"/profile?from={date_from}&to={date_to}")
        assert resp.status_code == 200, "Custom date range request must return 200"

    def test_custom_range_filter_label_text_is_not_a_preset_name(self, auth_client):
        """
        When a custom range is active, the filter-label-text span must show a
        human-readable date range (not one of the 4 preset labels).
        Checked against only the filter-label-text span to avoid false positives
        from preset navigation buttons always rendered on the page.
        """
        user_id = _get_user_id()
        _seed_spread_expenses(user_id)
        today = date.today()
        date_from = (today - timedelta(days=5)).isoformat()
        date_to = today.isoformat()
        resp = auth_client.get(f"/profile?from={date_from}&to={date_to}")
        label = _get_filter_label_text(resp.data.decode("utf-8"))

        assert label != "", "filter-label-text element must be present and non-empty"
        preset_labels = {"Showing: Last 7 days", "Showing: Last 30 days",
                         "Showing: This month", "Showing: All time"}
        assert label not in preset_labels, (
            f"Custom range must show a date-range label, not a preset name. Got: '{label}'"
        )

    def test_custom_range_filters_correctly_includes_in_range(self, auth_client):
        user_id = _get_user_id()
        today = date.today()
        inside_date = (today - timedelta(days=2)).isoformat()
        outside_date = (today - timedelta(days=50)).isoformat()

        conn = db_module.get_db()
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description)"
            " VALUES (?, ?, ?, ?, ?)",
            [
                (user_id, 111.11, "Food", inside_date,  "Inside range"),
                (user_id, 222.22, "Food", outside_date, "Outside range"),
            ],
        )
        conn.commit()
        conn.close()

        date_from = (today - timedelta(days=5)).isoformat()
        date_to = today.isoformat()
        resp = auth_client.get(f"/profile?from={date_from}&to={date_to}")
        assert b"Inside range" in resp.data, "Expense inside custom range must appear"

    def test_custom_range_filters_correctly_excludes_out_of_range(self, auth_client):
        user_id = _get_user_id()
        today = date.today()
        inside_date = (today - timedelta(days=2)).isoformat()
        outside_date = (today - timedelta(days=50)).isoformat()

        conn = db_module.get_db()
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description)"
            " VALUES (?, ?, ?, ?, ?)",
            [
                (user_id, 111.11, "Food", inside_date,  "Inside range"),
                (user_id, 222.22, "Food", outside_date, "Outside range"),
            ],
        )
        conn.commit()
        conn.close()

        date_from = (today - timedelta(days=5)).isoformat()
        date_to = today.isoformat()
        resp = auth_client.get(f"/profile?from={date_from}&to={date_to}")
        assert b"Outside range" not in resp.data, "Expense outside custom range must be excluded"

    def test_custom_range_active_period_sets_custom_class_on_form(self, auth_client):
        """
        When a custom range is active (both from and to supplied and parseable),
        the filter-custom form element must carry the 'active' CSS class:
          <form class="filter-custom active" ...>
        """
        today = date.today()
        date_from = (today - timedelta(days=5)).isoformat()
        date_to = today.isoformat()
        resp = auth_client.get(f"/profile?from={date_from}&to={date_to}")
        assert b"filter-custom active" in resp.data, (
            "When a custom range is active the filter-custom form must carry the 'active' class"
        )

    def test_custom_range_preset_buttons_do_not_carry_active_class(self, auth_client):
        """
        When active_period == 'custom', none of the four preset anchor buttons
        should carry the 'active' CSS class.  The template emits:
          class="filter-btn{% if active_period == '7d' %} active{% endif %}"
        so 'filter-btn active' must not appear in the response.
        """
        today = date.today()
        date_from = (today - timedelta(days=5)).isoformat()
        date_to = today.isoformat()
        resp = auth_client.get(f"/profile?from={date_from}&to={date_to}")
        assert b"filter-btn active" not in resp.data, (
            "No preset button should carry 'active' class when a custom range is active"
        )

    def test_custom_range_stats_reflect_filtered_subset(self, auth_client):
        user_id = _get_user_id()
        today = date.today()
        inside_date = (today - timedelta(days=2)).isoformat()
        outside_date = (today - timedelta(days=50)).isoformat()

        conn = db_module.get_db()
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description)"
            " VALUES (?, ?, ?, ?, ?)",
            [
                (user_id, 77.77, "Food", inside_date,  "Range expense"),
                (user_id, 99.99, "Food", outside_date, "Old expense"),
            ],
        )
        conn.commit()
        conn.close()

        date_from = (today - timedelta(days=5)).isoformat()
        date_to = today.isoformat()
        resp = auth_client.get(f"/profile?from={date_from}&to={date_to}")

        assert b"77.77" in resp.data, "Stats must reflect only expenses within custom range"
        assert b"99.99" not in resp.data, "Old expense amount must not appear in filtered stats"


# ---------------------------------------------------------------------------
# Partial custom range (only from OR only to) → falls back to period
# ---------------------------------------------------------------------------

class TestPartialCustomRange:
    def test_only_from_with_period_all_falls_back_to_all_time(self, auth_client):
        """
        When only ?from is supplied without ?to, custom range is ignored and
        the route falls back to the period param.
        """
        user_id = _get_user_id()
        _seed_spread_expenses(user_id)
        today = date.today()
        date_from = (today - timedelta(days=5)).isoformat()

        resp = auth_client.get(f"/profile?from={date_from}&period=all")
        assert resp.status_code == 200, "Only ?from (no ?to) must not crash"
        label = _get_filter_label_text(resp.data.decode("utf-8"))
        assert "All time" in label, (
            f"Only ?from (no ?to) must fall back to period=all ('All time'), got: '{label}'"
        )
        count = _count_transactions_in_response(resp.data)
        assert count == 7, f"Partial range with period=all must show all expenses, got {count}"

    def test_only_to_with_period_7d_falls_back_to_7d(self, auth_client):
        """
        When only ?to is supplied without ?from, custom range is ignored and
        the route falls back to the period param (?period=7d).
        """
        user_id = _get_user_id()
        _seed_spread_expenses(user_id)
        today = date.today()
        date_to = today.isoformat()

        resp = auth_client.get(f"/profile?to={date_to}&period=7d")
        assert resp.status_code == 200, "Only ?to (no ?from) must not crash"
        label = _get_filter_label_text(resp.data.decode("utf-8"))
        assert "Last 7 days" in label, (
            f"Only ?to (no ?from) must fall back to period=7d ('Last 7 days'), got: '{label}'"
        )
        count = _count_transactions_in_response(resp.data)
        assert count == 3, f"Expected 3 rows for 7d fallback, got {count}"

    def test_only_from_no_period_falls_back_to_all_time(self, auth_client):
        """
        Only ?from with no ?to and no ?period param must default to all-time.
        """
        user_id = _get_user_id()
        _seed_spread_expenses(user_id)
        today = date.today()
        date_from = (today - timedelta(days=5)).isoformat()

        resp = auth_client.get(f"/profile?from={date_from}")
        assert resp.status_code == 200
        label = _get_filter_label_text(resp.data.decode("utf-8"))
        assert "All time" in label, (
            f"Only ?from with no ?to and no ?period must fall back to all-time, got: '{label}'"
        )

    def test_only_to_no_period_falls_back_to_all_time(self, auth_client):
        """
        Only ?to with no ?from and no ?period param must default to all-time.
        """
        user_id = _get_user_id()
        _seed_spread_expenses(user_id)
        today = date.today()
        date_to = today.isoformat()

        resp = auth_client.get(f"/profile?to={date_to}")
        assert resp.status_code == 200
        label = _get_filter_label_text(resp.data.decode("utf-8"))
        assert "All time" in label, (
            f"Only ?to with no ?from and no ?period must fall back to all-time, got: '{label}'"
        )

    def test_only_from_no_period_shows_all_expenses(self, auth_client):
        user_id = _get_user_id()
        _seed_spread_expenses(user_id)
        today = date.today()
        date_from = (today - timedelta(days=5)).isoformat()

        resp = auth_client.get(f"/profile?from={date_from}")
        count = _count_transactions_in_response(resp.data)
        assert count == 7, (
            f"Partial range (from only) with no period must show all 7 expenses, got {count}"
        )


# ---------------------------------------------------------------------------
# Unparseable date strings → silent fallback to all-time
# ---------------------------------------------------------------------------

class TestUnparseableDates:
    @pytest.mark.parametrize("bad_from,bad_to", [
        ("not-a-date", "2026-05-10"),
        ("2026-05-01", "not-a-date"),
        ("not-a-date", "not-a-date"),
        ("05/01/2026", "05/10/2026"),   # wrong format — MM/DD/YYYY not accepted
        ("2026-13-01", "2026-12-31"),   # invalid month 13
    ])
    def test_unparseable_dates_do_not_crash(self, auth_client, bad_from, bad_to):
        resp = auth_client.get(f"/profile?from={bad_from}&to={bad_to}")
        assert resp.status_code == 200, (
            f"Unparseable dates from='{bad_from}' to='{bad_to}' must not cause a 5xx error"
        )

    @pytest.mark.parametrize("bad_from,bad_to", [
        ("not-a-date", "2026-05-10"),
        ("2026-05-01", "not-a-date"),
        ("not-a-date", "not-a-date"),
        ("05/01/2026", "05/10/2026"),
        ("2026-13-01", "2026-12-31"),
    ])
    def test_unparseable_dates_fall_back_to_all_time(self, auth_client, bad_from, bad_to):
        user_id = _get_user_id()
        _seed_spread_expenses(user_id)
        resp = auth_client.get(f"/profile?from={bad_from}&to={bad_to}")
        label = _get_filter_label_text(resp.data.decode("utf-8"))
        assert "All time" in label, (
            f"Unparseable dates from='{bad_from}' to='{bad_to}' must show 'All time', got: '{label}'"
        )

    @pytest.mark.parametrize("bad_from,bad_to", [
        ("not-a-date", "2026-05-10"),
        ("2026-05-01", "not-a-date"),
        ("not-a-date", "not-a-date"),
        ("05/01/2026", "05/10/2026"),
        ("2026-13-01", "2026-12-31"),
    ])
    def test_unparseable_dates_show_all_expenses(self, auth_client, bad_from, bad_to):
        user_id = _get_user_id()
        _seed_spread_expenses(user_id)
        resp = auth_client.get(f"/profile?from={bad_from}&to={bad_to}")
        count = _count_transactions_in_response(resp.data)
        assert count == 7, (
            f"Unparseable date fallback must show all 7 expenses, got {count} "
            f"(from='{bad_from}' to='{bad_to}')"
        )


# ---------------------------------------------------------------------------
# Template: filter bar elements rendered
# ---------------------------------------------------------------------------

class TestFilterBarTemplate:
    def test_filter_bar_contains_last_7_days_preset(self, auth_client):
        resp = auth_client.get("/profile")
        assert b"Last 7 days" in resp.data, "Filter bar must contain 'Last 7 days' preset"

    def test_filter_bar_contains_last_30_days_preset(self, auth_client):
        resp = auth_client.get("/profile")
        assert b"Last 30 days" in resp.data, "Filter bar must contain 'Last 30 days' preset"

    def test_filter_bar_contains_this_month_preset(self, auth_client):
        resp = auth_client.get("/profile")
        assert b"This month" in resp.data, "Filter bar must contain 'This month' preset"

    def test_filter_bar_contains_all_time_preset(self, auth_client):
        resp = auth_client.get("/profile")
        assert b"All time" in resp.data, "Filter bar must contain 'All time' preset"

    def test_filter_bar_all_four_presets_always_rendered(self, auth_client):
        """
        All 4 preset navigation labels must be present in the page regardless of the
        active period — the filter bar is always rendered in full.
        """
        today = date.today()
        date_from = (today - timedelta(days=5)).isoformat()
        date_to = today.isoformat()
        resp = auth_client.get(f"/profile?from={date_from}&to={date_to}")
        # All preset labels must still appear as navigation anchor text
        for label in [b"Last 7 days", b"Last 30 days", b"This month", b"All time"]:
            assert label in resp.data, (
                f"Preset label '{label.decode()}' must always render in the filter bar"
            )

    def test_filter_bar_contains_two_date_inputs(self, auth_client):
        resp = auth_client.get("/profile")
        # Template uses type="date" with double quotes
        count = resp.data.count(b'type="date"')
        assert count >= 2, (
            f"Filter bar must contain at least 2 date inputs (from/to), found {count}"
        )

    def test_filter_bar_contains_apply_button(self, auth_client):
        resp = auth_client.get("/profile")
        assert b"Apply" in resp.data, "Filter bar must contain an 'Apply' submit button"

    def test_filter_form_uses_get_method(self, auth_client):
        resp = auth_client.get("/profile")
        html = resp.data.decode("utf-8")
        # The filter form must declare method="GET" or method="get"
        assert 'method="get"' in html.lower() or "method='get'" in html.lower(), (
            "Filter form must use GET method so filtered URLs are bookmarkable"
        )

    def test_filter_label_text_element_present(self, auth_client):
        resp = auth_client.get("/profile")
        assert b"filter-label-text" in resp.data, (
            "The filter-label-text element must be present on the profile page"
        )

    def test_filter_label_shows_showing_prefix(self, auth_client):
        resp = auth_client.get("/profile")
        assert b"Showing:" in resp.data, (
            "The filter label must include a 'Showing:' prefix near the stats"
        )

    def test_filter_label_shows_period_30d_label(self, auth_client):
        user_id = _get_user_id()
        _seed_spread_expenses(user_id)
        resp = auth_client.get("/profile?period=30d")
        label = _get_filter_label_text(resp.data.decode("utf-8"))
        assert "Last 30 days" in label, (
            f"Active date range label must show 'Last 30 days' for period=30d, got: '{label}'"
        )

    def test_filter_bar_wrapper_element_present(self, auth_client):
        resp = auth_client.get("/profile")
        assert b"filter-bar" in resp.data, "The filter-bar wrapper element must be present"

    def test_filter_presets_wrapper_element_present(self, auth_client):
        resp = auth_client.get("/profile")
        assert b"filter-presets" in resp.data, "The filter-presets wrapper must be present"


# ---------------------------------------------------------------------------
# DB-level filtering correctness
# ---------------------------------------------------------------------------

class TestDBLevelFiltering:
    def test_db_filtering_7d_vs_all_returns_different_counts(self, auth_client):
        user_id = _get_user_id()
        _seed_spread_expenses(user_id)
        resp_all = auth_client.get("/profile?period=all")
        resp_7d = auth_client.get("/profile?period=7d")
        all_count = _count_transactions_in_response(resp_all.data)
        wk_count = _count_transactions_in_response(resp_7d.data)
        assert all_count != wk_count, (
            "DB must return different row counts for 'all' vs '7d' filters"
        )

    def test_db_filtering_30d_vs_7d_returns_different_counts(self, auth_client):
        user_id = _get_user_id()
        _seed_spread_expenses(user_id)
        resp_30d = auth_client.get("/profile?period=30d")
        resp_7d = auth_client.get("/profile?period=7d")
        count_30d = _count_transactions_in_response(resp_30d.data)
        count_7d = _count_transactions_in_response(resp_7d.data)
        assert count_30d != count_7d, (
            "DB must return different row counts for '30d' vs '7d' filters"
        )

    def test_db_filtering_custom_range_returns_exact_count(self, auth_client):
        """
        Seed expenses at two deterministic in-range dates and two out-of-range;
        verify the custom range returns exactly the 2 in-range rows.
        """
        user_id = _get_user_id()
        today = date.today()
        dates_in_range = [
            (today - timedelta(days=2)).isoformat(),
            (today - timedelta(days=1)).isoformat(),
        ]
        dates_out_of_range = [
            (today - timedelta(days=40)).isoformat(),
            (today - timedelta(days=50)).isoformat(),
        ]

        conn = db_module.get_db()
        rows = (
            [(user_id, 10.0, "Food", d, "In range") for d in dates_in_range]
            + [(user_id, 20.0, "Food", d, "Out of range") for d in dates_out_of_range]
        )
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description)"
            " VALUES (?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
        conn.close()

        date_from = (today - timedelta(days=5)).isoformat()
        date_to = today.isoformat()
        resp = auth_client.get(f"/profile?from={date_from}&to={date_to}")
        count = _count_transactions_in_response(resp.data)
        assert count == 2, (
            f"Custom range must return exactly 2 in-range expenses, got {count}"
        )

    def test_db_filtering_category_breakdown_reflects_active_filter(self, auth_client):
        """
        With a narrow custom range containing only 'Entertainment', the category
        breakdown must show Entertainment and must not show the out-of-range category 'Bills'.
        """
        user_id = _get_user_id()
        today = date.today()
        inside_date = (today - timedelta(days=1)).isoformat()
        outside_date = (today - timedelta(days=40)).isoformat()

        conn = db_module.get_db()
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description)"
            " VALUES (?, ?, ?, ?, ?)",
            [
                (user_id, 55.00, "Entertainment", inside_date,  "Concert inside range"),
                (user_id, 99.00, "Bills",          outside_date, "Bills outside range"),
            ],
        )
        conn.commit()
        conn.close()

        date_from = (today - timedelta(days=3)).isoformat()
        date_to = today.isoformat()
        resp = auth_client.get(f"/profile?from={date_from}&to={date_to}")

        assert b"Entertainment" in resp.data, (
            "Category breakdown must include 'Entertainment' (in-range category)"
        )
        assert b"Bills" not in resp.data, (
            "Category breakdown must NOT include 'Bills' (out-of-range category)"
        )

    def test_stats_transaction_count_matches_visible_rows(self, auth_client):
        """
        The transaction_count stat card value must equal the number of table rows
        rendered for the same active filter period.
        """
        user_id = _get_user_id()
        _seed_spread_expenses(user_id)
        resp = auth_client.get("/profile?period=7d")
        html = resp.data.decode("utf-8")
        visible_rows = _count_transactions_in_response(resp.data)
        # 3 expenses in last 7 days — the stat card must show "3"
        assert str(visible_rows) in html, (
            f"The transaction count stat must show {visible_rows} to match visible rows"
        )

    def test_stats_total_spent_is_zero_for_empty_filter_window(self, auth_client):
        """
        When no expenses fall within the custom range, the total_spent stat
        must render as 0.00, not crash or show stale data.
        """
        user_id = _get_user_id()
        today = date.today()
        # Seed one old expense (outside the narrow range we will query)
        conn = db_module.get_db()
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description)"
            " VALUES (?, ?, ?, ?, ?)",
            (user_id, 500.00, "Bills", (today - timedelta(days=90)).isoformat(), "Old bill"),
        )
        conn.commit()
        conn.close()

        # Query a future window guaranteed to have zero expenses
        date_from = (today + timedelta(days=10)).isoformat()
        date_to = (today + timedelta(days=20)).isoformat()
        resp = auth_client.get(f"/profile?from={date_from}&to={date_to}")
        assert resp.status_code == 200, "Empty filter window must not crash the server"
        assert b"0.00" in resp.data, (
            "Total spent must show 0.00 when no expenses fall within the filter window"
        )
