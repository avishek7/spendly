from flask import Flask, render_template, request, session, redirect, url_for, abort
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from database.db import get_db, init_db, seed_db, create_user, get_user_by_email, \
    get_user_by_id, get_expenses_by_user, get_stats_by_user, get_categories_by_user

app = Flask(__name__)
app.secret_key = "dev-secret-change-in-prod"


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name     = request.form.get("name", "").strip()
        email    = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        if not name or not email or not password:
            error = "All fields are required."
        elif len(password) < 8:
            error = "Password must be at least 8 characters."
        elif get_user_by_email(email) is not None:
            error = "An account with that email already exists."
        else:
            error = None

        if error:
            return render_template("register.html", error=error)

        password_hash = generate_password_hash(password)
        user_id = create_user(name, email, password_hash)
        session["user_id"] = user_id
        return redirect(url_for("profile"))

    if session.get("user_id"):
        return redirect(url_for("profile"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email    = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        error = None
        if not email or not password:
            error = "Email and password are required."
        else:
            user = get_user_by_email(email)
            if user is None or not check_password_hash(user["password_hash"], password):
                error = "Invalid email or password."

        if error:
            return render_template("login.html", error=error)

        session["user_id"] = user["id"]
        return redirect(url_for("profile"))

    if session.get("user_id"):
        return redirect(url_for("profile"))
    return render_template("login.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/logout")
def logout():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    db_user = get_user_by_id(session["user_id"])
    if db_user is None:
        abort(404)

    created_at = datetime.strptime(db_user["created_at"][:19], "%Y-%m-%d %H:%M:%S")
    member_since = created_at.strftime("%B %Y")
    initials = "".join(word[0].upper() for word in db_user["name"].split() if word)

    user = {
        "name":         db_user["name"],
        "email":        db_user["email"],
        "initials":     initials,
        "member_since": member_since,
    }

    raw_stats = get_stats_by_user(session["user_id"])
    stats = {
        "total_spent":       f"₹{raw_stats['total_spent']:,.2f}",
        "transaction_count": raw_stats["transaction_count"],
        "top_category":      raw_stats["top_category"],
    }

    raw_transactions = get_expenses_by_user(session["user_id"])
    transactions = [
        {
            "date":         tx["date"],
            "description":  tx["description"],
            "category":     tx["category"],
            "category_key": tx["category_key"],
            "amount":       f"₹{tx['amount']:,.2f}",
        }
        for tx in raw_transactions
    ]

    raw_categories = get_categories_by_user(session["user_id"])
    categories = [
        {
            "name":    cat["name"],
            "key":     cat["key"],
            "amount":  f"₹{cat['amount']:,.2f}",
            "percent": cat["percent"],
        }
        for cat in raw_categories
    ]

    return render_template("profile.html", user=user, stats=stats,
                           transactions=transactions, categories=categories)


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    with app.app_context():
        init_db()
        seed_db()
    app.run(debug=True, port=5001)
