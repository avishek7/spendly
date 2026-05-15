import os
from flask import Flask, render_template, request, session, redirect, url_for, abort
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from database.db import (
    init_db,
    seed_db,
    create_user,
    get_user_by_email,
    get_user_by_id,
    get_expenses_by_user,
    get_stats_by_user,
    get_categories_by_user,
    add_expense as db_add_expense,
    get_expense_by_id,
    update_expense as db_update_expense,
)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-only-fallback-not-for-prod")

VALID_CATEGORIES = [
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
]


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #


@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
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
        email = request.form.get("email", "").strip()
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
        "name": db_user["name"],
        "email": db_user["email"],
        "initials": initials,
        "member_since": member_since,
    }

    period = request.args.get("period", "all")
    raw_from = request.args.get("from", "").strip()
    raw_to = request.args.get("to", "").strip()

    today = datetime.today().date()

    date_from = date_to = None
    if raw_from and raw_to:
        try:
            date_from = datetime.strptime(raw_from, "%Y-%m-%d").date()
            date_to = datetime.strptime(raw_to, "%Y-%m-%d").date()
        except ValueError:
            date_from = date_to = None

    if date_from and date_to:
        df_str = date_from.strftime("%Y-%m-%d")
        dt_str = date_to.strftime("%Y-%m-%d")
        filter_label = (
            f"{date_from.strftime('%d %b %Y')} – {date_to.strftime('%d %b %Y')}"
        )
        active_period = "custom"
    else:
        if period not in ("7d", "30d", "month", "all"):
            period = "all"
        if period == "7d":
            df_str = (today - timedelta(days=6)).strftime("%Y-%m-%d")
            dt_str = today.strftime("%Y-%m-%d")
            filter_label = "Last 7 days"
            active_period = "7d"
        elif period == "30d":
            df_str = (today - timedelta(days=29)).strftime("%Y-%m-%d")
            dt_str = today.strftime("%Y-%m-%d")
            filter_label = "Last 30 days"
            active_period = "30d"
        elif period == "month":
            df_str = today.replace(day=1).strftime("%Y-%m-%d")
            dt_str = today.strftime("%Y-%m-%d")
            filter_label = "This month"
            active_period = "month"
        else:
            df_str = dt_str = None
            filter_label = "All time"
            active_period = "all"

    raw_stats = get_stats_by_user(session["user_id"], date_from=df_str, date_to=dt_str)
    stats = {
        "total_spent": f"₹{raw_stats['total_spent']:,.2f}",
        "transaction_count": raw_stats["transaction_count"],
        "top_category": raw_stats["top_category"],
    }

    raw_transactions = get_expenses_by_user(
        session["user_id"], date_from=df_str, date_to=dt_str
    )
    transactions = [
        {
            "id": tx["id"],
            "date": tx["date"],
            "description": tx["description"],
            "category": tx["category"],
            "category_key": tx["category_key"],
            "amount": f"₹{tx['amount']:,.2f}",
        }
        for tx in raw_transactions
    ]

    raw_categories = get_categories_by_user(
        session["user_id"], date_from=df_str, date_to=dt_str
    )
    categories = [
        {
            "name": cat["name"],
            "key": cat["key"],
            "amount": f"₹{cat['amount']:,.2f}",
            "percent": cat["percent"],
        }
        for cat in raw_categories
    ]

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
        filter_label=filter_label,
        active_period=active_period,
        raw_from=raw_from,
        raw_to=raw_to,
    )


@app.route("/analytics")
def analytics():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("analytics.html")


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    if request.method == "POST":
        amount_raw = request.form.get("amount", "").strip()
        category = request.form.get("category", "").strip()
        date = request.form.get("date", "").strip()
        description_raw = request.form.get("description", "").strip()
        description = description_raw or None

        error = None
        amount = None

        try:
            amount = float(amount_raw)
            if amount <= 0:
                error = "Amount must be a positive number."
        except ValueError:
            error = "Amount must be a valid number."

        if not error and category not in VALID_CATEGORIES:
            error = "Please select a valid category."

        if not error:
            try:
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                error = "Please enter a valid date."

        if error:
            return render_template(
                "add_expense.html",
                error=error,
                categories=VALID_CATEGORIES,
                form={
                    "amount": amount_raw,
                    "category": category,
                    "date": date,
                    "description": description_raw,
                },
            )

        db_add_expense(session["user_id"], amount, category, date, description)
        return redirect(url_for("profile"))

    today = datetime.today().strftime("%Y-%m-%d")
    return render_template(
        "add_expense.html",
        categories=VALID_CATEGORIES,
        form={"amount": "", "category": "", "date": today, "description": ""},
    )


@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
def edit_expense(id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    expense = get_expense_by_id(id)
    if expense is None:
        abort(404)
    if expense["user_id"] != session["user_id"]:
        abort(403)

    if request.method == "POST":
        amount_raw = request.form.get("amount", "").strip()
        category = request.form.get("category", "").strip()
        date = request.form.get("date", "").strip()
        description_raw = request.form.get("description", "").strip()
        description = description_raw or None

        error = None
        amount = None

        try:
            amount = float(amount_raw)
            if amount <= 0:
                error = "Amount must be a positive number."
        except ValueError:
            error = "Amount must be a valid number."

        if not error and category not in VALID_CATEGORIES:
            error = "Please select a valid category."

        if not error:
            try:
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                error = "Please enter a valid date."

        if error:
            return render_template(
                "edit_expense.html",
                error=error,
                categories=VALID_CATEGORIES,
                expense_id=id,
                form={
                    "amount": amount_raw,
                    "category": category,
                    "date": date,
                    "description": description_raw,
                },
            )

        db_update_expense(id, session["user_id"], amount, category, date, description)
        return redirect(url_for("profile"))

    return render_template(
        "edit_expense.html",
        categories=VALID_CATEGORIES,
        expense_id=id,
        form={
            "amount": expense["amount"],
            "category": expense["category"],
            "date": expense["date"],
            "description": expense["description"] or "",
        },
    )


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    with app.app_context():
        init_db()
        seed_db()
    app.run(debug=os.getenv("FLASK_DEBUG", "false").lower() == "true", port=5001)
