import sqlite3
import os
from werkzeug.security import generate_password_hash


def get_db():
    db_path = os.path.join(os.path.dirname(__file__), "..", "spendly.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT    NOT NULL,
            email         TEXT    UNIQUE NOT NULL,
            password_hash TEXT    NOT NULL,
            created_at    TEXT    DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            amount      REAL    NOT NULL,
            category    TEXT    NOT NULL,
            date        TEXT    NOT NULL,
            description TEXT,
            created_at  TEXT    DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()


def seed_db():
    conn = get_db()
    row = conn.execute("SELECT COUNT(*) FROM users").fetchone()
    if row[0] > 0:
        conn.close()
        return

    hashed = generate_password_hash("demo123")
    conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Demo User", "demo@spendly.com", hashed),
    )
    conn.commit()

    user_id = conn.execute(
        "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
    ).fetchone()["id"]

    expenses = [
        (user_id, 12.50, "Food", "2026-05-01", "Morning coffee and pastry"),
        (user_id, 45.00, "Transport", "2026-05-02", "Monthly bus pass top-up"),
        (user_id, 120.00, "Bills", "2026-05-03", "Electricity bill"),
        (user_id, 30.00, "Health", "2026-05-05", "Pharmacy — vitamins"),
        (user_id, 18.75, "Entertainment", "2026-05-07", "Cinema ticket"),
        (user_id, 65.99, "Shopping", "2026-05-08", "New running shoes"),
        (user_id, 9.99, "Other", "2026-05-09", "Notebook and pens"),
        (user_id, 22.40, "Food", "2026-05-10", "Lunch at cafe"),
    ]
    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        expenses,
    )
    conn.commit()
    conn.close()


def get_categories_by_user(user_id, date_from=None, date_to=None):
    conn = get_db()

    sql = "SELECT COALESCE(SUM(amount), 0.0) AS total FROM expenses WHERE user_id = ?"
    params = (user_id,)
    if date_from and date_to:
        sql += " AND date BETWEEN ? AND ?"
        params += (date_from, date_to)
    total_row = conn.execute(sql, params).fetchone()
    total = total_row["total"]

    sql2 = "SELECT category, SUM(amount) AS cat_total FROM expenses WHERE user_id = ?"
    params2 = (user_id,)
    if date_from and date_to:
        sql2 += " AND date BETWEEN ? AND ?"
        params2 += (date_from, date_to)
    sql2 += " GROUP BY category ORDER BY cat_total DESC"
    rows = conn.execute(sql2, params2).fetchall()
    conn.close()

    result = []
    for row in rows:
        cat_total = row["cat_total"]
        percent = int(cat_total / total * 100) if total > 0 else 0
        result.append(
            {
                "name": row["category"],
                "key": row["category"].lower(),
                "amount": cat_total,
                "percent": percent,
            }
        )
    return result


def create_user(name, email, password_hash):
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name, email, password_hash),
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return user_id


def get_stats_by_user(user_id, date_from=None, date_to=None):
    conn = get_db()

    sql = (
        "SELECT COALESCE(SUM(amount), 0.0) AS total_spent,"
        " COUNT(*) AS transaction_count"
        " FROM expenses WHERE user_id = ?"
    )
    params = (user_id,)
    if date_from and date_to:
        sql += " AND date BETWEEN ? AND ?"
        params += (date_from, date_to)
    row = conn.execute(sql, params).fetchone()
    total_spent = row["total_spent"]
    transaction_count = row["transaction_count"]

    sql2 = "SELECT category, SUM(amount) AS cat_total FROM expenses WHERE user_id = ?"
    params2 = (user_id,)
    if date_from and date_to:
        sql2 += " AND date BETWEEN ? AND ?"
        params2 += (date_from, date_to)
    sql2 += " GROUP BY category ORDER BY cat_total DESC LIMIT 1"
    top_row = conn.execute(sql2, params2).fetchone()
    top_category = top_row["category"] if top_row else ""

    conn.close()
    return {
        "total_spent": total_spent,
        "transaction_count": transaction_count,
        "top_category": top_category,
    }


def add_expense(user_id, amount, category, expense_date, description):
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, expense_date, description),
    )
    conn.commit()
    expense_id = cursor.lastrowid
    conn.close()
    return expense_id


def get_expense_by_id(expense_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()
    conn.close()
    return row


def update_expense(expense_id, user_id, amount, category, expense_date, description):
    conn = get_db()
    cursor = conn.execute(
        "UPDATE expenses SET amount=?, category=?, date=?, description=?"
        " WHERE id=? AND user_id=?",
        (amount, category, expense_date, description, expense_id, user_id),
    )
    conn.commit()
    rows_affected = cursor.rowcount
    conn.close()
    return rows_affected


def get_user_by_email(email):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return row


def get_user_by_id(user_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return row


def get_expenses_by_user(user_id, date_from=None, date_to=None):
    from datetime import datetime

    conn = get_db()

    sql = (
        "SELECT id, amount, category, date, description FROM expenses WHERE user_id = ?"
    )
    params = (user_id,)
    if date_from and date_to:
        sql += " AND date BETWEEN ? AND ?"
        params += (date_from, date_to)
    sql += " ORDER BY date DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    result = []
    for row in rows:
        dt = datetime.strptime(row["date"], "%Y-%m-%d")
        result.append(
            {
                "id": row["id"],
                "date": f"{dt.day} {dt.strftime('%b %Y')}",
                "description": row["description"] or "",
                "category": row["category"],
                "category_key": row["category"].lower(),
                "amount": row["amount"],
            }
        )
    return result
