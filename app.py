"""Flask application: routes call the service layer; services own all SQL."""
import hmac
import logging
import secrets
import time
from datetime import timedelta
from decimal import Decimal

from dotenv import load_dotenv
from flask import (Flask, abort, flash, jsonify, redirect, render_template, request, session, url_for)

import config
from services import (categories, customers, database, employees, products, reports, sales, suppliers, users)
from services.errors import AppError

log = logging.getLogger("appliance_store")

# ---- access control (Review 3) ------------------------------------------------
PUBLIC_ENDPOINTS = {"login", "health", "static"}
# Default deny: a CASHIER may call only these endpoints; MANAGER may call everything.
CASHIER_ENDPOINTS = {"products_page", "customers_page", "customers_create", "customers_update",
                     "sales_new", "sales_create", "sales_page", "sale_detail", "logout", "account_password"}
LOGIN_MAX_FAILURES, LOGIN_WINDOW_SECONDS = 5, 300


def is_allowed(role, endpoint):
    return role == "MANAGER" or (role == "CASHIER" and endpoint in CASHIER_ENDPOINTS)


def safe_next(target, fallback):
    """Only same-site relative paths are accepted (prevents open redirects)."""
    if target and target.startswith("/") and not target.startswith("//") and "\\" not in target:
        return target
    return fallback


def create_app(test_config=None):
    app = Flask(__name__)
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)   # Flask default is 31 days
    if test_config is None:
        load_dotenv()
        app.config.update(config.load_flask_config())
    else:
        app.config.update(test_config)
    app.config.setdefault("CSRF_ENABLED", True)
    failures = {}   # ponytail: in-process login throttle; use a shared store if run with several workers

    def current_user():
        return session.get("user")

    # ---- security plumbing ------------------------------------------------
    def csrf_token():
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(32)
        return session["csrf"]

    @app.before_request
    def require_login():
        endpoint = request.endpoint
        if endpoint is None or endpoint in PUBLIC_ENDPOINTS:
            return None
        user = current_user()
        if not user:
            return redirect(url_for("login", next=request.full_path.rstrip("?") if request.method == "GET" else None), 302)
        if not is_allowed(user["role"], endpoint):
            abort(403, "Your role does not have permission to do this.")
        return None

    @app.before_request
    def protect_state_changes():
        if request.method in ("POST", "PUT", "PATCH", "DELETE") and app.config["CSRF_ENABLED"]:
            sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token") or ""
            if not hmac.compare_digest(sent, session.get("csrf", "")) or not session.get("csrf"):
                abort(400, "Security token missing or invalid. Reload the page and try again.")

    @app.after_request
    def security_headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "same-origin"
        resp.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'"
        return resp

    app.jinja_env.globals["csrf_token"] = csrf_token
    app.jinja_env.globals["current_user"] = current_user
    app.jinja_env.globals["allowed"] = lambda endpoint: bool(current_user()) and is_allowed(current_user()["role"], endpoint)
    app.jinja_env.filters["money"] = lambda x: "₹{:,.2f}".format(Decimal(str(x or 0)))

    # ---- error handling ---------------------------------------------------
    def show_error(message, status):
        return render_template("error.html", message=message, status=status), status

    @app.errorhandler(AppError)
    def app_error(exc):
        return show_error(str(exc), exc.status_code)

    @app.errorhandler(config.ConfigError)
    def config_error(exc):
        return show_error(str(exc), 503)

    @app.errorhandler(400)
    @app.errorhandler(404)
    @app.errorhandler(405)
    @app.errorhandler(403)
    @app.errorhandler(429)
    def http_error(exc):
        return show_error(exc.description, exc.code)

    @app.errorhandler(Exception)
    def unexpected(exc):
        if hasattr(exc, "code"):                      # other HTTP exceptions
            return show_error(getattr(exc, "description", "Request failed."), exc.code)
        log.exception("Unhandled error")
        return show_error("Unexpected server error. Details were written to the server log.", 500)

    # ---- helpers ----------------------------------------------------------
    def page_arg():
        try:
            return max(1, int(request.args.get("page", 1)))
        except ValueError:
            return 1

    def done(message, endpoint, **values):
        flash(message, "success")
        return redirect(url_for(endpoint, **values), 303)

    # ---- authentication ---------------------------------------------------
    def landing(user):
        return url_for("dashboard") if user["role"] == "MANAGER" else url_for("sales_new")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        target = request.values.get("next", "")
        if request.method == "GET":
            if current_user():
                return redirect(landing(current_user()))
            return render_template("login.html", next=target)
        name = (request.form.get("username") or "").strip().lower()
        key, now = (name, request.remote_addr), time.time()
        recent = [t for t in failures.get(key, []) if now - t < LOGIN_WINDOW_SECONDS]
        if len(recent) >= LOGIN_MAX_FAILURES:
            abort(429, "Too many failed sign-in attempts. Wait a few minutes and try again.")
        user = users.authenticate(name, request.form.get("password"))
        if not user:
            failures[key] = recent + [now]
            return render_template("login.html", next=target, error="Invalid username or password."), 401
        failures.pop(key, None)
        session.clear()                       # new session after login (prevents fixation)
        session["user"] = user
        session.permanent = True
        return redirect(safe_next(target, landing(user)), 303)

    @app.post("/logout")
    def logout():
        session.clear()
        flash("You have been signed out.", "success")
        return redirect(url_for("login"), 303)

    @app.route("/account/password", methods=["GET", "POST"])
    def account_password():
        if request.method == "POST":
            users.change_own_password(current_user()["id"], request.form)
            return done("Password changed.", "account_password")
        return render_template("account.html")

    # ---- health -----------------------------------------------------------
    @app.get("/health")
    def health():
        ok, message = database.health_check()
        return jsonify(app="ok", database="ok" if ok else "unavailable", detail=message), (200 if ok else 503)

    # ---- dashboard --------------------------------------------------------
    @app.get("/")
    def dashboard():
        return render_template("dashboard.html", **reports.dashboard())

    # ---- products ---------------------------------------------------------
    @app.get("/products")
    def products_page():
        q, cat = request.args.get("q", "").strip(), request.args.get("category_id", "").strip()
        low = request.args.get("low_stock") == "1"
        edit = products.get(request.args["edit"]) if request.args.get("edit") else None
        return render_template("products.html", data=products.list_page(q, cat, low, page_arg()), q=q,
                               category_id=cat, low_stock=low, edit=edit,
                               categories=categories.list_all(), suppliers=suppliers.list_all())

    @app.post("/products")
    def products_create():
        products.create(request.form)
        return done("Product added.", "products_page")

    @app.post("/products/<int:product_id>/update")
    def products_update(product_id):
        products.update(product_id, request.form)
        return done("Product updated.", "products_page")

    @app.post("/products/<int:product_id>/delete")
    def products_delete(product_id):
        products.delete(product_id)
        return done("Product deleted.", "products_page")

    @app.post("/products/<int:product_id>/restock")
    def products_restock(product_id):
        products.restock(product_id, request.form.get("quantity"))
        return done("Stock updated.", "products_page")

    # ---- categories / suppliers / customers (same shape) -------------------
    @app.get("/categories")
    def categories_page():
        q = request.args.get("q", "").strip()
        edit = categories.get(request.args["edit"]) if request.args.get("edit") else None
        return render_template("categories.html", rows=categories.list_all(q), q=q, edit=edit)

    @app.post("/categories")
    def categories_create():
        categories.create(request.form)
        return done("Category added.", "categories_page")

    @app.post("/categories/<int:item_id>/update")
    def categories_update(item_id):
        categories.update(item_id, request.form)
        return done("Category updated.", "categories_page")

    @app.post("/categories/<int:item_id>/delete")
    def categories_delete(item_id):
        categories.delete(item_id)
        return done("Category deleted.", "categories_page")

    @app.get("/suppliers")
    def suppliers_page():
        q = request.args.get("q", "").strip()
        edit = suppliers.get(request.args["edit"]) if request.args.get("edit") else None
        return render_template("suppliers.html", rows=suppliers.list_all(q), q=q, edit=edit)

    @app.post("/suppliers")
    def suppliers_create():
        suppliers.create(request.form)
        return done("Supplier added.", "suppliers_page")

    @app.post("/suppliers/<int:item_id>/update")
    def suppliers_update(item_id):
        suppliers.update(item_id, request.form)
        return done("Supplier updated.", "suppliers_page")

    @app.post("/suppliers/<int:item_id>/delete")
    def suppliers_delete(item_id):
        suppliers.delete(item_id)
        return done("Supplier deleted.", "suppliers_page")

    @app.get("/customers")
    def customers_page():
        q = request.args.get("q", "").strip()
        edit = customers.get(request.args["edit"]) if request.args.get("edit") else None
        return render_template("customers.html", data=customers.list_page(q, page_arg()), q=q, edit=edit)

    @app.post("/customers")
    def customers_create():
        customers.create(request.form)
        return done("Customer added.", "customers_page")

    @app.post("/customers/<int:item_id>/update")
    def customers_update(item_id):
        customers.update(item_id, request.form)
        return done("Customer updated.", "customers_page")

    @app.post("/customers/<int:item_id>/delete")
    def customers_delete(item_id):
        customers.delete(item_id)
        return done("Customer deleted.", "customers_page")

    # ---- sales ------------------------------------------------------------
    @app.get("/sales")
    def sales_page():
        q = request.args.get("q", "").strip()
        return render_template("sales.html", data=sales.list_page(q, page_arg()), q=q)

    @app.get("/sales/new")
    def sales_new():
        return render_template("sale_new.html", customers=customers.list_all(),
                               products=products.list_for_sale(), payment_methods=sales.PAYMENT_METHODS)

    @app.post("/sales/new")
    def sales_create():
        items = sales.parse_items(request.form.getlist("product_id"), request.form.getlist("quantity"))
        result = sales.create_sale(request.form.get("customer_id"), current_user()["employee_id"],
                                   request.form.get("payment_method"), items)
        return done(f"Sale {result['invoice_no']} recorded. Total {result['total']}.",
                    "sale_detail", sale_id=result["sale_id"])

    @app.get("/sales/<int:sale_id>")
    def sale_detail(sale_id):
        return render_template("sale_detail.html", **sales.get(sale_id))

    # ---- employees (manager) ------------------------------------------------
    @app.get("/employees")
    def employees_page():
        q = request.args.get("q", "").strip()
        edit = employees.get(request.args["edit"]) if request.args.get("edit") else None
        return render_template("employees.html", data=employees.list_page(q, page_arg()), q=q, edit=edit)

    @app.post("/employees")
    def employees_create():
        employees.create(request.form)
        return done("Employee added.", "employees_page")

    @app.post("/employees/<int:item_id>/update")
    def employees_update(item_id):
        employees.update(item_id, request.form)
        return done("Employee updated.", "employees_page")

    @app.post("/employees/<int:item_id>/delete")
    def employees_delete(item_id):
        employees.delete(item_id)
        return done("Employee deleted.", "employees_page")

    # ---- user accounts (manager) ------------------------------------------
    @app.get("/users")
    def users_page():
        return render_template("users.html", rows=users.list_all(), candidates=employees.list_without_user(),
                               roles=users.ROLES)

    @app.post("/users")
    def users_create():
        users.create(request.form)
        return done("User account created.", "users_page")

    @app.post("/users/<int:item_id>/password")
    def users_reset_password(item_id):
        users.reset_password(item_id, request.form)
        return done("Password reset.", "users_page")

    @app.post("/users/<int:item_id>/delete")
    def users_delete(item_id):
        users.delete(item_id, current_user()["id"])
        return done("User account deleted.", "users_page")

    # ---- reports ----------------------------------------------------------
    @app.get("/reports")
    def reports_page():
        return render_template("reports.html", inventory=reports.inventory(), monthly=reports.sales_by_month(),
                               top=reports.top_products(), by_category=reports.category_revenue(),
                               customers=reports.customer_summary())

    return app


if __name__ == "__main__":
    application = create_app()
    application.run(host="127.0.0.1", port=5000, debug=application.config["DEBUG"])
