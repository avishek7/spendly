import sqlite3
import pytest
import database.db as db_module
from database.db import init_db
from app import app as flask_app


@pytest.fixture
def app(monkeypatch, tmp_path):
    db_path = str(tmp_path / "test.db")

    def _test_get_db():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    monkeypatch.setattr(db_module, "get_db", _test_get_db)

    flask_app.config.update({"TESTING": True, "SECRET_KEY": "test"})
    with flask_app.app_context():
        init_db()
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()
