# I implemented the core Flask app, routes, and database logic for Credo myself
# using concepts from CS50's Python, SQL, and web lectures. Some advanced features
# in this file (password reset tokens, rate limiting, monthly summary JSON export,
# and budget/report aggregation logic) were refined with suggestions from an AI
# assistant (Perplexity), then reviewed and integrated by me.

from flask import Flask, render_template, redirect, url_for, request, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy  # database helper
from flask_bcrypt import Bcrypt  # password hashing
import os  # paths
from datetime import date, timedelta, datetime
from dotenv import load_dotenv

# load variables from .env into environment
load_dotenv() # looks for .env in current folder

from sqlalchemy import func # for SUM() [web:184]
import csv
import io
from flask import Response
from flask_wtf.csrf import CSRFProtect # CSRF protection
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import json
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired  # token helper [web:145][web:164]

# create Flask app
app = Flask(__name__)

# ---- config from environment variables ----
# SECRET_KEY: used for sessions, flash, tokens (set in .env or hosting panel)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-change-this")  # default only for local dev

# DATABASE_URL: production (e.g. Postgres); fallback to local SQLite if not set
basedir = os.path.abspath(os.path.dirname(__file__))  # base project folder
db_dir = os.path.join(basedir, "instance")            # instance folder path
os.makedirs(db_dir, exist_ok=True)                    # create instance folder if missing

sqlite_path = os.path.join(db_dir, "credo.db")       # local SQLite file path
default_sqlite_uri = f"sqlite:///{sqlite_path}"       # SQLite URI

# Use Render Postgres if DATABASE_URL is set; otherwise use local SQLite
db_url = os.environ.get("DATABASE_URL")

if db_url:
    # Force psycopg3 dialect regardless of what scheme DATABASE_URL had
    if "://" in db_url:
        _, rest = db_url.split("://", 1)
    else:
        rest = db_url
    db_url = f"postgresql+psycopg://{rest}"
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = default_sqlite_uri

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

print("FINAL DB URI:", app.config["SQLALCHEMY_DATABASE_URI"])

def get_serializer():
    # serializer uses SECRET_KEY, so tokens change if key changes
    return URLSafeTimedSerializer(app.config["SECRET_KEY"])

csrf = CSRFProtect(app)  # enable CSRF protection for all POST forms

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[]  # no global default limit (specific routes can have limits)
)

# --- session security settings ---
app.permanent_session_lifetime = timedelta(minutes=30)  # session lifetime for logged-in users
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"          # helps mitigate CSRF on cookies
# app.config["SESSION_COOKIE_SECURE"] = True           # enable this when running behind HTTPS

# init extensions
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

# ===== Database models =====
class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)          # full name
    email = db.Column(db.String(120), unique=True, nullable=False)  # login email
    password_hash = db.Column(db.String(255), nullable=False) # hashed password

    def set_password(self, password: str) -> None:
        # hash and store the password
        self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

    def check_password(self, password: str) -> bool:
        # verify a password against the stored hash
        return bcrypt.check_password_hash(self.password_hash, password)

    def generate_reset_token(self, expires_sec=1800):
        # create a signed reset token with user_id
        s = get_serializer()
        return s.dumps({"user_id": self.id})

    @staticmethod
    def verify_reset_token(token, max_age=1800):
        # verify a reset token and return the corresponding user or None
        s = get_serializer()
        try:
            data = s.loads(token, max_age=max_age)
        except (BadSignature, SignatureExpired):
            return None
        user_id = data.get("user_id")
        if not user_id:
            return None
        return User.query.get(user_id)

class Transaction(db.Model):
    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    description = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)

    # optional FK to Category
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True)
    category = db.relationship("Category", backref="transactions")

class Budget(db.Model):
    __tablename__ = "budgets"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    limit_amount = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Budget {self.category} ₹{self.limit_amount}>"

class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(50), nullable=False)

    def __repr__(self):
        # nice display in debugging / shell
        return f"<Category {self.name}>"

# ===== Routes =====
from datetime import date

@app.route("/")
def home():
    if "user_id" not in session:
        flash("Please log in to access your Credo.", "error")
        return redirect(url_for("login"))

    user_id = session["user_id"]

    # read filter from query string: ?period=all|this_month|last_month
    period = request.args.get("period", "all")  # default = all [web:269][web:279]

    today = date.today()
    start = None
    end = None

    if period == "this_month":
        start = date(today.year, today.month, 1)
        if today.month == 12:
            end = date(today.year + 1, 1, 1)
        else:
            end = date(today.year, today.month + 1, 1)
    elif period == "last_month":
        if today.month == 1:
            year = today.year - 1
            month = 12
        else:
            year = today.year
            month = today.month - 1
        start = date(year, month, 1)
        if month == 12:
            end = date(year + 1, 1, 1)
        else:
            end = date(year, month + 1, 1)

    # base query: this user's transactions
    base_q = Transaction.query.filter_by(user_id=user_id)

    # apply date range if selected [web:255][web:277]
    if start and end:
        base_q = base_q.filter(Transaction.date >= start, Transaction.date < end)

    txns = (
        base_q.order_by(Transaction.id.desc())
        .limit(10)
        .all()
    )

    # totals using same filter
    from sqlalchemy import func

    income_q = db.session.query(func.coalesce(func.sum(Transaction.amount), 0.0)) \
        .filter(Transaction.user_id == user_id, Transaction.amount > 0)
    expense_q = db.session.query(func.coalesce(func.sum(Transaction.amount), 0.0)) \
        .filter(Transaction.user_id == user_id, Transaction.amount < 0)

    if start and end:
        income_q = income_q.filter(Transaction.date >= start, Transaction.date < end)
        expense_q = expense_q.filter(Transaction.date >= start, Transaction.date < end)

    total_income = income_q.scalar()
    total_expense = expense_q.scalar()
    net = total_income + total_expense

    return render_template(
        "dashboard.html",
        transactions=txns,
        total_income=total_income,
        total_expense=total_expense,
        net=net,
        period=period,
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":  # form submitted
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        # basic validation
        if not name or not email or not password:
            flash("Please fill in all fields.", "error")
            return redirect(url_for("register"))

        # check if email already used
        existing = User.query.filter_by(email=email).first()
        if existing:
            flash("Email already registered. Please log in.", "error")
            return redirect(url_for("login"))

        # create user and save
        user = User(name=name, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash("Account created successfully. Please log in.", "success")
        return redirect(url_for("login"))

    # GET request → show form
    return render_template("auth/register.html")

# Login rate limiting was added with the help from an AI assistant (Perplexity)
# to improve security, then configured and understand by me.

@limiter.limit("5 per minute") # at most 5 login attempts per IP per minute
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            # store user info in session so we know they are logged in
            session["user_id"] = user.id
            session["user_name"] = user.name  # for greeting in UI
            session.permanent = True
            flash("Welcome back to Credo.", "success")
            return redirect(url_for("home"))
        else:
            flash("Invalid email or password.", "error")
            return redirect(url_for("login"))

    return render_template("auth/login.html")

# The password reset flow (generating reset links with tokens and validating them)
# was designed with the help of an AI assistant (Perplexity) and then reviewed
# and adapted by me for Credo.

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        if not email:
            flash("Please enter your email.", "error")
            return redirect(url_for("forgot_password"))

        user = User.query.filter_by(email=email).first()
        if not user:
            flash("If this email exists, a reset link has been generated.", "info")
            return redirect(url_for("login"))

        token = user.generate_reset_token()
        reset_url = url_for("reset_password", token=token, _external=True)

        # For now, just print the link to terminal instead of real email. [web:143][web:166]
        print("\n=== PASSWORD RESET LINK ===")
        print(reset_url)
        print("===========================\n")

        flash("Password reset link has been generated. Check the server console.", "success")
        return redirect(url_for("login"))

    return render_template("auth/forgot_password.html")

# Password reset token helpers belowe were implemented with guidance
# from an AI assistant (Perplexity) and then adapted and understood by me.

@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    user = User.verify_reset_token(token)
    if not user:
        flash("Reset link is invalid or has expired.", "error")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not password or not confirm:
            flash("Please fill in both password fields.", "error")
            return redirect(url_for("reset_password", token=token))

        if password != confirm:
            flash("Passwords do not match.", "error")
            return redirect(url_for("reset_password", token=token))

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return redirect(url_for("reset_password", token=token))

        user.set_password(password)
        db.session.commit()

        flash("Your password has been reset. You can now log in.", "success")
        return redirect(url_for("login"))

    return render_template("auth/reset_password.html")


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("user_name", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))

@app.route("/add-transaction", methods=["GET", "POST"])
def add_transaction():
    if "user_id" not in session:
        flash("Please log in to add a transaction.", "error")
        return redirect(url_for("login"))

    user_id = session["user_id"]

    if request.method == "POST":
        t_date = request.form.get("date")
        desc = request.form.get("description", "").strip()
        cat_name = request.form.get("category", "").strip()
        amount_raw = request.form.get("amount")

        if not t_date or not desc or not amount_raw:
            flash("Please fill in all fields.", "error")
            return redirect(url_for("add_transaction"))

        try:
            amt = float(amount_raw)
        except ValueError:
            flash("Amount must be a number.", "error")
            return redirect(url_for("add_transaction"))

        if abs(amt) > 10_00_000:
            flash("Amount is too large.", "error")
            return redirect(url_for("add_transaction"))

        # limit text length
        desc = desc[:100]

        # map category name -> Category row (optional)
        category_id = None
        if cat_name:
            cat_name = cat_name[:50]
            cat = Category.query.filter_by(user_id=user_id, name=cat_name).first()
            if not cat:
                # auto-create category if it does not exist
                cat = Category(user_id=user_id, name=cat_name)
                db.session.add(cat)
                db.session.flush()  # get cat.id without full commit
            category_id = cat.id

        txn = Transaction(
            user_id=user_id,
            date=date.fromisoformat(t_date),
            description=desc,
            amount=amt,
            category_id=category_id,
        )
        db.session.add(txn)
        db.session.commit()

        flash("Transaction added.", "success")
        return redirect(url_for("home"))

    # GET: need categories list for dropdown
    categories = Category.query.filter_by(user_id=session["user_id"]).order_by(Category.name.asc()).all()
    return render_template("transactions/add.html", categories=categories)

@app.route("/delete-transaction/<int:txn_id>", methods=["POST"])
def delete_transaction(txn_id):
    if "user_id" not in session:
        flash("Please log in to manage transactions.", "error")
        return redirect(url_for("login"))
    
    txn = Transaction.query.filter_by(id=txn_id, user_id=session["user_id"]).first()
    if not txn:
        flash("Transaction not found.", "error")
        return redirect(url_for("home"))
    
    db.session.delete(txn) # delete row [web:214][web:216]
    db.session.commit()

    flash("Transaction deleted.", "success")
    return redirect(url_for("home"))

@app.route("/edit-transaction/<int:txn_id>", methods=["GET", "POST"])
def edit_transaction(txn_id):
    if "user_id" not in session:
        flash("Please log in to edit transactions.", "error")
        return redirect(url_for("login"))

    user_id = session["user_id"]
    txn = Transaction.query.filter_by(id=txn_id, user_id=user_id).first()
    if not txn:
        flash("Transaction not found.", "error")
        return redirect(url_for("home"))

    if request.method == "POST":
        t_date = request.form.get("date")
        desc = request.form.get("description", "").strip()
        cat_name = request.form.get("category", "").strip()
        amount_raw = request.form.get("amount")

        if not t_date or not desc or not amount_raw:
            flash("Please fill in all fields.", "error")
            return redirect(url_for("edit_transaction", txn_id=txn_id))

        try:
            amt = float(amount_raw)
        except ValueError:
            flash("Amount must be a valid number.", "error")
            return redirect(url_for("edit_transaction", txn_id=txn_id))

        if abs(amt) > 10_00_000:
            flash("Amount is too large.", "error")
            return redirect(url_for("edit_transaction", txn_id=txn_id))

        # limit text length
        desc = desc[:100]

        # map category name -> Category row (optional)
        category_id = None
        if cat_name:
            cat_name = cat_name[:50]
            cat = Category.query.filter_by(user_id=user_id, name=cat_name).first()
            if not cat:
                cat = Category(user_id=user_id, name=cat_name)
                db.session.add(cat)
                db.session.flush()
            category_id = cat.id

        # Update existing row
        txn.date = date.fromisoformat(t_date)
        txn.description = desc
        txn.amount = amt
        txn.category_id = category_id
        db.session.commit()

        flash("Transaction updated.", "success")
        return redirect(url_for("home"))

    # GET: show form with current values + categories list
    categories = Category.query.filter_by(user_id=user_id).order_by(Category.name.asc()).all()
    return render_template("transactions/edit.html", txn=txn, categories=categories)

@app.route("/transactions")
def transactions_page():
    if "user_id" not in session:
        flash("Please log in to view your transactions.", "error")
        return redirect(url_for("login"))

    user_id = session["user_id"]

    # filters from query string
    period = request.args.get("period", "all")          # all | this_month | last_month
    category_filter = request.args.get("category", "all")  # all or category id as string

    today = date.today()
    start = None
    end = None

    if period == "this_month":
        start = date(today.year, today.month, 1)
        if today.month == 12:
            end = date(today.year + 1, 1, 1)
        else:
            end = date(today.year, today.month + 1, 1)
    elif period == "last_month":
        if today.month == 1:
            year = today.year - 1
            month = 12
        else:
            year = today.year
            month = today.month - 1
        start = date(year, month, 1)
        if month == 12:
            end = date(year + 1, 1, 1)
        else:
            end = date(year, month + 1, 1)

    base_q = Transaction.query.filter_by(user_id=user_id)

    # apply date range
    if start and end:
        base_q = base_q.filter(Transaction.date >= start, Transaction.date < end)

    # apply category filter by category_id
    if category_filter != "all":
        try:
            cat_id = int(category_filter)
            base_q = base_q.filter(Transaction.category_id == cat_id)
        except ValueError:
            pass  # ignore bad value

    txns = base_q.order_by(Transaction.date.desc(), Transaction.id.desc()).all()

    # categories for dropdown
    categories = Category.query.filter_by(user_id=user_id).order_by(Category.name.asc()).all()

    return render_template(
        "transactions/index.html",
        transactions=txns,
        period=period,
        category_filter=category_filter,
        categories=categories,  # pass full objects now
    )

@app.route("/transactions/export/csv")
def export_transactions_csv():
    if "user_id" not in session:
        flash("Please log in to export your data.", "error")
        return redirect(url_for("login"))
    
    user_id = session["user_id"]

    # get all this user's transactions, newest first
    txns = (
        Transaction.query
        .filter_by(user_id=user_id)
        .order_by(Transaction.id.desc())
        .all()
    )

    if not txns:
        flash("No transactions to export.", "info")
        return redirect(url_for("transactions_page"))
    
    # create in-memory CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # header row
    writer.writerow(["DAte", "Description", "Category", "Amount"])

    # data rows
    for t in txns:
    # Agar transaction ki koi category hai toh uska naam lein, nahi toh '-'
        cat_name = t.category.name if t.category else '-'
        writer.writerow([t.date.isoformat(), t.description, cat_name, f"{t.amount:.2f}"])

    # go back to start of buffer
    csv_data = output.getvalue()
    output.close()

    # build response so browser downloads it
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=transactions.csv"
        },
    )

# The reports logic below (totals_for_range helper, monthly/yearly aggregation,
# and building chart_data for all 12 months) was refined with suggestions from
# an AI assistant (Perplexity), then reviewed and integrated by me.

@app.route("/reports")
def reports_page():
    if "user_id" not in session:
        flash("Please log in to view reports.", "error")
        return redirect(url_for("login"))

    user_id = session["user_id"]
    today = date.today()

    # month range
    month_start = date(today.year, today.month, 1)
    if today.month == 12:
        month_end = date(today.year + 1, 1, 1)
    else:
        month_end = date(today.year, today.month + 1, 1)

    # year range
    year_start = date(today.year, 1, 1)
    year_end = date(today.year + 1, 1, 1)

    # helper to compute totals for a given range
    def totals_for_range(start, end):
        income_q = db.session.query(func.coalesce(func.sum(Transaction.amount), 0.0)) \
            .filter(
                Transaction.user_id == user_id,
                Transaction.amount > 0,
                Transaction.date >= start,
                Transaction.date < end,
            )

        expense_q = db.session.query(func.coalesce(func.sum(Transaction.amount), 0.0)) \
            .filter(
                Transaction.user_id == user_id,
                Transaction.amount < 0,
                Transaction.date >= start,
                Transaction.date < end,
            )

        total_income = float(income_q.scalar() or 0.0)
        total_expense = float(expense_q.scalar() or 0.0)
        net = total_income + total_expense
        return total_income, total_expense, net

    month_income, month_expense, month_net = totals_for_range(month_start, month_end)
    year_income, year_expense, year_net = totals_for_range(year_start, year_end)

    # Build chart data for all 12 months
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    chart_data = []
    
    for month_num in range(1, 13):
        m_start = date(today.year, month_num, 1)
        if month_num == 12:
            m_end = date(today.year + 1, 1, 1)
        else:
            m_end = date(today.year, month_num + 1, 1)
        
        m_income, m_expense, m_net = totals_for_range(m_start, m_end)
        chart_data.append({
            "month": month_names[month_num - 1],
            "income": float(m_income),
            "expense": float(-m_expense),  # make positive for display
        })

    chart_data_json = json.dumps(chart_data)

    return render_template(
        "reports/index.html",
        month_income=month_income,
        month_expense=month_expense,
        month_net=month_net,
        year_income=year_income,
        year_expense=year_expense,
        year_net=year_net,
        chart_data=chart_data_json,
        year=today.year,
    )

# The budgeting calculations below (combining budgets with this month's expenses
# per category to compute used and remaining amounts) were refined with the help from
# an AI assistant (Perplexity), then understood and integrated by me.

@app.route("/budgets", methods=["GET", "POST"])
def budgets_page():
    if "user_id" not in session:
        flash("Please log in to view budgets.", "error")
        return redirect(url_for("login"))

    user_id = session["user_id"]
    today = date.today()

    # current month range
    month_start = date(today.year, today.month, 1)
    if today.month == 12:
        month_end = date(today.year + 1, 1, 1)
    else:
        month_end = date(today.year, today.month + 1, 1)

    # Handle add / update budget
    if request.method == "POST":
        category = request.form.get("category", "").strip()
        amount_raw = request.form.get("limit_amount")

        if not category or not amount_raw:
            flash("Please fill in both category and amount.", "error")
            return redirect(url_for("budgets_page"))

        try:
            limit_amount = float(amount_raw)
        except ValueError:
            flash("Budget amount must be a number.", "error")
            return redirect(url_for("budgets_page"))

        if limit_amount <= 0:
            flash("Budget amount must be positive.", "error")
            return redirect(url_for("budgets_page"))

        category = category[:50]

        existing = Budget.query.filter_by(user_id=user_id, category=category).first()
        if existing:
            existing.limit_amount = limit_amount
            flash("Budget updated for this category.", "success")
        else:
            b = Budget(user_id=user_id, category=category, limit_amount=limit_amount)
            db.session.add(b)
            flash("Budget added.", "success")

        db.session.commit()
        return redirect(url_for("budgets_page"))

    # Build rows: Budget + used this month + remaining
    budgets = Budget.query.filter_by(user_id=user_id).order_by(Budget.category.asc()).all()

    budget_rows = []
    for b in budgets:
        used_q = (
            db.session.query(func.coalesce(func.sum(Transaction.amount), 0.0))
            .filter(
                Transaction.user_id == user_id,
                Transaction.amount < 0,                      # expenses only
                Transaction.category.has(name=b.category),   # match Category.name
                Transaction.date >= month_start,
                Transaction.date < month_end,
            )
        )
        used_amount = float(used_q.scalar() or 0.0)
        used_abs = -used_amount  # make positive
        remaining = b.limit_amount - used_abs

        budget_rows.append(
            {
                "id": b.id,
                "category": b.category,
                "limit_amount": b.limit_amount,
                "used_amount": used_abs,
                "remaining": remaining,
            }
        )

    categories = Category.query.filter_by(user_id=user_id).order_by(Category.name.asc()).all()
    return render_template("budgets/index.html", budget_rows=budget_rows, categories=categories)

@app.route("/budget/add", methods=["POST"])
def add_budget():
    if "user_id" not in session:
        flash("Please log in.", "error")
        return redirect(url_for("login"))

    category = request.form.get("category", "").strip()
    limit_raw = request.form.get("limit_amount")

    if not category or not limit_raw:
        flash("Please fill in all fields.", "error")
        return redirect(url_for("budgets_page"))

    try:
        limit = float(limit_raw)
        if limit <= 0:
            flash("Budget must be greater than 0.", "error")
            return redirect(url_for("budgets_page"))
    except ValueError:
        flash("Budget must be a valid number.", "error")
        return redirect(url_for("budgets_page"))

    # check if budget already exists for this category
    existing = Budget.query.filter_by(user_id=session["user_id"], category=category).first()
    if existing:
        flash(f"Budget for {category} already exists.", "error")
        return redirect(url_for("budgets_page"))

    budget = Budget(
        user_id=session["user_id"],
        category=category,
        limit_amount=limit,
    )
    db.session.add(budget)
    db.session.commit()

    flash(f"Budget for {category} added.", "success")
    return redirect(url_for("budgets_page"))


@app.route("/budget/<int:budget_id>/edit", methods=["POST"])
def edit_budget(budget_id):
    if "user_id" not in session:
        flash("Please log in.", "error")
        return redirect(url_for("login"))

    budget = Budget.query.filter_by(id=budget_id, user_id=session["user_id"]).first()
    if not budget:
        flash("Budget not found.", "error")
        return redirect(url_for("budgets_page"))

    limit_raw = request.form.get("limit_amount")

    if not limit_raw:
        flash("Please enter a budget amount.", "error")
        return redirect(url_for("budgets_page"))

    try:
        limit = float(limit_raw)
        if limit <= 0:
            flash("Budget must be greater than 0.", "error")
            return redirect(url_for("budgets_page"))
    except ValueError:
        flash("Budget must be a valid number.", "error")
        return redirect(url_for("budgets_page"))

    budget.limit_amount = limit
    db.session.commit()

    flash(f"Budget for {budget.category} updated.", "success")
    return redirect(url_for("budgets_page"))


@app.route("/budget/<int:budget_id>/delete", methods=["POST"])
def delete_budget(budget_id):
    if "user_id" not in session:
        flash("Please log in.", "error")
        return redirect(url_for("login"))

    budget = Budget.query.filter_by(id=budget_id, user_id=session["user_id"]).first()
    if not budget:
        flash("Budget not found.", "error")
        return redirect(url_for("budgets_page"))

    category = budget.category
    db.session.delete(budget)
    db.session.commit()

    flash(f"Budget for {category} deleted.", "success")
    return redirect(url_for("budgets_page"))

# List + add categories
@app.route("/categories", methods=["GET", "POST"])
def categories_page():
    if "user_id" not in session:
        flash("Please log in to manage categories.", "error")
        return redirect(url_for("login"))

    user_id = session["user_id"]

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Category name is required.", "error")
        elif len(name) > 50:
            flash("Category name is too long.", "error")
        else:
            existing = Category.query.filter_by(user_id=user_id, name=name).first()
            if existing:
                flash("Category with this name already exists.", "error")
            else:
                cat = Category(user_id=user_id, name=name)
                db.session.add(cat)
                db.session.commit()
                flash("Category added.", "success")
        return redirect(url_for("categories_page"))

    categories = Category.query.filter_by(user_id=user_id).order_by(Category.name.asc()).all()
    return render_template("categories/index.html", categories=categories)


# Edit category
@app.route("/categories/<int:cat_id>/edit", methods=["GET", "POST"])
def edit_category(cat_id):
    if "user_id" not in session:
        flash("Please log in to manage categories.", "error")
        return redirect(url_for("login"))

    user_id = session["user_id"]
    cat = Category.query.filter_by(id=cat_id, user_id=user_id).first_or_404()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Category name is required.", "error")
        elif len(name) > 50:
            flash("Category name is too long.", "error")
        else:
            other = Category.query.filter(
                Category.user_id == user_id,
                Category.id != cat.id,
                Category.name == name,
            ).first()
            if other:
                flash("Another category with this name already exists.", "error")
            else:
                cat.name = name
                db.session.commit()
                flash("Category updated.", "success")
                return redirect(url_for("categories_page"))

    return render_template("categories/edit.html", cat=cat)


# Delete category (only if no transactions using it, to keep it simple)
@app.route("/categories/<int:cat_id>/delete", methods=["POST"])
def delete_category(cat_id):
    if "user_id" not in session:
        flash("Please log in to manage categories.", "error")
        return redirect(url_for("login"))

    user_id = session["user_id"]
    cat = Category.query.filter_by(id=cat_id, user_id=user_id).first_or_404()

    attached_txn = Transaction.query.filter_by(user_id=user_id, category_id=cat.id).first()
    if attached_txn:
        flash("Cannot delete category that is used by transactions.", "error")
        return redirect(url_for("categories_page"))

    db.session.delete(cat)
    db.session.commit()
    flash("Category deleted.", "success")
    return redirect(url_for("categories_page"))

@app.route("/export/json")
def export_json():
    if "user_id" not in session:
        return jsonify({"error": "unauthorized"}), 401  # JSON 401 if not logged in [web:68][web:102]

    user_id = session["user_id"]

    txns = (
        Transaction.query
        .filter_by(user_id=user_id)
        .order_by(Transaction.date.desc(), Transaction.id.desc())
        .all()
    )

    data = []
    for t in txns:
        data.append({
            "id": t.id,
            "date": t.date.isoformat(),
            "description": t.description,
            "amount": float(t.amount),
            "category": t.category.name if getattr(t, "category", None) else None,
        })

    # jsonify sets Content-Type: application/json automatically [web:102][web:111]
    return jsonify({"transactions": data})

# The monthly-summary JSON aggregation (using strftime, CASE expressions,
# and grouping by year-month) was developed with the help from an AI assistant
# (Perplexity) and then reviewed and adapted by me.

@app.route("/export/monthly-summary.json")
def export_monthly_summary():
    if "user_id" not in session:
        return jsonify({"error": "unauthorized"}), 401

    user_id = session["user_id"]

    # Group by year-month string like "2025-01" using SQLite strftime [web:107][web:118]
    ym = func.strftime("%Y-%m", Transaction.date)

    income_case = func.case((Transaction.amount > 0, Transaction.amount), else_=0.0)
    expense_case = func.case((Transaction.amount < 0, Transaction.amount), else_=0.0)

    rows = (
        db.session.query(
            ym.label("ym"),
            func.sum(income_case).label("income"),
            func.sum(expense_case).label("expense"),
        )
        .filter(Transaction.user_id == user_id)
        .group_by("ym")
        .order_by("ym")
        .all()
    )

    summary = []
    for r in rows:
        ym_str = r.ym or ""
        year, month = ym_str.split("-") if "-" in ym_str else (None, None)
        income = float(r.income or 0.0)
        expense = float(r.expense or 0.0)
        net = income + expense  # expense is negative

        summary.append({
            "year": int(year) if year else None,
            "month": int(month) if month else None,
            "income": income,
            "expense": expense,
            "net": net,
        })

    return jsonify({"monthly_summary": summary})

@app.route("/about")
def about_page():
    return render_template("static_pages/about.html")


@app.route("/help")
def help_page():
    return render_template("static_pages/help.html")


@app.route("/privacy")
def privacy_page():
    return render_template("static_pages/privacy.html")


@app.route("/terms")
def terms_page():
    return render_template("static_pages/terms.html")

@app.errorhandler(404)
def page_not_found(e):
    # Custom 404 page [web:177][web:183]
    return render_template("errors/404.html")

@app.errorhandler(500)
def internal_error(e):
    # Custom 500 page [web:180][web:186]
    return render_template("errors/500.html"), 500

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    # create tables if they do not exist yet
    with app.app_context():
        db.create_all()  # creates User and Transaction tables [web:89][web:121]
    app.run(debug=True)

# Custom handler for too many requests (HTTP 429) was set up with AI (Perplexity)
# suggestions and then integrated by me.

@app.errorhandler(429)
def ratelimit_handler(e):
    flash("Too many login attempts. Please wait a moment and try again.", "error")
    return redirect(url_for("login"))