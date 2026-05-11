import re


def _register(client):
    client.post("/register", data={
        "name": "Grace Hopper",
        "email": "grace@example.com",
        "password": "securepass",
    })


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
    resp = client.get("/profile")
    assert resp.data.count(b"profile-td-date") >= 3


def test_profile_contains_category_breakdown(client):
    _register(client)
    resp = client.get("/profile")
    assert resp.data.count(b"profile-breakdown-row") >= 3


def test_profile_contains_category_badges(client):
    _register(client)
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
