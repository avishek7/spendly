def test_logout_authenticated_redirects_to_landing(client):
    client.post("/register", data={
        "name": "Alice",
        "email": "alice@example.com",
        "password": "securepass",
    })
    resp = client.get("/logout")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/"


def test_logout_unauthenticated_redirects_to_login(client):
    resp = client.get("/logout")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/login"


def test_logout_clears_session(client):
    client.post("/register", data={
        "name": "Bob",
        "email": "bob@example.com",
        "password": "securepass",
    })
    with client.session_transaction() as sess:
        assert "user_id" in sess

    client.get("/logout")

    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_login_get_while_authenticated_redirects(client):
    client.post("/register", data={
        "name": "Carol",
        "email": "carol@example.com",
        "password": "securepass",
    })
    resp = client.get("/login")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/"


def test_register_get_while_authenticated_redirects(client):
    client.post("/register", data={
        "name": "Dan",
        "email": "dan@example.com",
        "password": "securepass",
    })
    resp = client.get("/register")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/"
