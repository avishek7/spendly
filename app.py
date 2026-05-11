from flask import Flask, render_template, request, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import get_db, init_db, seed_db, create_user, get_user_by_email

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

    user = {
        "name":         "Nitish Kumar",
        "email":        "nitish@example.com",
        "initials":     "NK",
        "member_since": "January 2025",
    }

    stats = {
        "total_spent":       "₹18,450",
        "transaction_count": 34,
        "top_category":      "Food",
    }

    transactions = [
        {"date": "10 May 2026", "description": "Lunch at Cafe",      "category": "Food",          "category_key": "food",          "amount": "₹22.40"},
        {"date": "08 May 2026", "description": "New running shoes",   "category": "Shopping",      "category_key": "shopping",      "amount": "₹65.99"},
        {"date": "07 May 2026", "description": "Cinema ticket",       "category": "Entertainment", "category_key": "entertainment", "amount": "₹18.75"},
        {"date": "05 May 2026", "description": "Pharmacy — vitamins", "category": "Health",        "category_key": "health",        "amount": "₹30.00"},
        {"date": "03 May 2026", "description": "Electricity bill",    "category": "Bills",         "category_key": "bills",         "amount": "₹120.00"},
        {"date": "02 May 2026", "description": "Monthly bus pass",    "category": "Transport",     "category_key": "transport",     "amount": "₹45.00"},
    ]

    categories = [
        {"name": "Food",          "key": "food",          "amount": "₹6,240", "percent": 78},
        {"name": "Bills",         "key": "bills",         "amount": "₹4,800", "percent": 60},
        {"name": "Transport",     "key": "transport",     "amount": "₹3,600", "percent": 45},
        {"name": "Shopping",      "key": "shopping",      "amount": "₹2,200", "percent": 28},
        {"name": "Entertainment", "key": "entertainment", "amount": "₹1,610", "percent": 20},
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
