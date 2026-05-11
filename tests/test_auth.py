import database.db as db_module


def test_register_creates_user(client, app):
    resp = client.post("/register", data={
        "name": "Alice",
        "email": "alice@example.com",
        "password": "securepass",
    })
    assert resp.status_code == 302

    with client.session_transaction() as sess:
        assert "user_id" in sess

    conn = db_module.get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE email = ?", ("alice@example.com",)
    ).fetchone()
    conn.close()
    assert user is not None
    assert user["name"] == "Alice"


def test_register_duplicate_email(client, app):
    data = {"name": "Bob", "email": "bob@example.com", "password": "securepass"}
    client.post("/register", data=data)
    resp = client.post("/register", data=data)
    assert resp.status_code == 200
    assert b"An account with that email already exists." in resp.data


def test_register_short_password(client):
    resp = client.post("/register", data={
        "name": "Carol",
        "email": "carol@example.com",
        "password": "short1",
    })
    assert resp.status_code == 200
    assert b"Password must be at least 8 characters." in resp.data


def test_register_missing_field(client):
    resp = client.post("/register", data={
        "name": "",
        "email": "dan@example.com",
        "password": "securepass",
    })
    assert resp.status_code == 200
    assert b"All fields are required." in resp.data


def test_login_success(client, app):
    client.post("/register", data={
        "name": "Eve",
        "email": "eve@example.com",
        "password": "securepass",
    })
    with client.session_transaction() as sess:
        sess.clear()

    resp = client.post("/login", data={
        "email": "eve@example.com",
        "password": "securepass",
    })
    assert resp.status_code == 302

    with client.session_transaction() as sess:
        assert "user_id" in sess


def test_login_wrong_password(client, app):
    client.post("/register", data={
        "name": "Frank",
        "email": "frank@example.com",
        "password": "securepass",
    })
    with client.session_transaction() as sess:
        sess.clear()

    resp = client.post("/login", data={
        "email": "frank@example.com",
        "password": "wrongpass",
    })
    assert resp.status_code == 200
    assert b"Invalid email or password." in resp.data


def test_login_unknown_email(client):
    resp = client.post("/login", data={
        "email": "ghost@example.com",
        "password": "securepass",
    })
    assert resp.status_code == 200
    assert b"Invalid email or password." in resp.data
