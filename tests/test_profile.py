import re
import database.db as db_module


def _register(client):
    client.post("/register", data={
        "name": "Grace Hopper",
        "email": "grace@example.com",
        "password": "securepass",
    })


def _seed_expenses():
    conn = db_module.get_db()
    user_row = conn.execute(
        "SELECT id FROM users WHERE email = ?", ("grace@example.com",)
    ).fetchone()
    user_id = user_row["id"]
    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description)"
        " VALUES (?, ?, ?, ?, ?)",
        [
            (user_id, 22.40, "Food",          "2026-05-10", "Lunch at cafe"),
            (user_id, 65.99, "Shopping",      "2026-05-08", "New running shoes"),
            (user_id, 18.75, "Entertainment", "2026-05-07", "Cinema ticket"),
            (user_id, 30.00, "Health",        "2026-05-05", "Pharmacy vitamins"),
        ],
    )
    conn.commit()
    conn.close()


def test_profile_unauthenticated_redirects_to_login(client):
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/login"


def test_profile_authenticated_returns_200(client):
    _register(client)
    resp = client.get("/profile")
    assert resp.status_code == 200


def test_profile_contains_user_info_card(client):
    _register(client)
    resp = client.get("/profile")
    assert b"profile-avatar-initials" in resp.data
    assert b"profile-name" in resp.data
    assert b"profile-email" in resp.data
    assert b"Member since" in resp.data


def test_profile_contains_three_stats(client):
    _register(client)
    resp = client.get("/profile")
    assert resp.data.count(b"profile-stat-card") >= 3


def test_profile_contains_transaction_table_rows(client):
    _register(client)
    _seed_expenses()
    resp = client.get("/profile")
    assert resp.data.count(b"profile-td-date") >= 3


def test_profile_contains_category_breakdown(client):
    _register(client)
    _seed_expenses()
    resp = client.get("/profile")
    assert resp.data.count(b"profile-breakdown-row") >= 3


def test_profile_contains_category_badges(client):
    _register(client)
    _seed_expenses()
    resp = client.get("/profile")
    assert b"profile-badge" in resp.data


def test_profile_no_hex_colors_in_style_attrs(client):
    _register(client)
    resp = client.get("/profile")
    body = resp.data.decode("utf-8")
    hex_pattern = re.compile(r'#[0-9a-fA-F]{3,6}\b')
    for style_val in re.findall(r'style="([^"]*)"', body):
        assert not hex_pattern.search(style_val), \
            f"Hex colour found in inline style: {style_val}"


def test_profile_logout_link_present(client):
    _register(client)
    resp = client.get("/profile")
    assert b"/logout" in resp.data


def test_profile_session_cleared_then_redirect(client):
    _register(client)
    client.get("/logout")
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/login"
