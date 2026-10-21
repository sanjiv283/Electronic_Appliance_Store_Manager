"""Review 3: login, roles (MANAGER / CASHIER), user accounts and employee CRUD.
Unit tests only - fake DB connection and stubbed services (no Oracle)."""
import datetime
import re
from decimal import Decimal

import oracledb
import pytest
from werkzeug.security import check_password_hash, generate_password_hash

import app as app_module
from services import categories, customers, employees, products, reports, sales, users
from services.errors import ConflictError, ValidationError

MANAGER = {"id": 1, "username": "meera", "role": "MANAGER", "employee_id": 9, "name": "Meera Nair"}
CASHIER = {"id": 2, "username": "karan", "role": "CASHIER", "employee_id": 4, "name": "Karan Shetty"}


@pytest.fixture
def application():
    return app_module.create_app({"SECRET_KEY": "test-key-not-secret", "TESTING": True})


@pytest.fixture
def anon(application):
    return application.test_client()


def signed_in(application, user):
    c = application.test_client()
    with c.session_transaction() as s:
        s["user"] = user
    return c


def csrf(client):
    html = client.get("/login").get_data(as_text=True)
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


# ------------------------------------------------------------------ gate
def test_every_protected_route_requires_login(application, anon):
    """Every non-public route requested without signing in | 302 redirect to /login (default deny)"""
    checked = 0
    for rule in application.url_map.iter_rules():
        if rule.endpoint in app_module.PUBLIC_ENDPOINTS:
            continue
        url = re.sub(r"<[^>]+>", "1", rule.rule)
        method = "POST" if "POST" in rule.methods else "GET"
        resp = anon.open(url, method=method)
        assert resp.status_code == 302 and "/login" in resp.headers["Location"], (rule.rule, resp.status_code)
        checked += 1
    assert checked >= 25


def test_unauthenticated_post_never_reaches_service(anon, monkeypatch):
    """POST to a write route without login | redirected, service not called"""
    called = []
    monkeypatch.setattr(products, "delete", lambda i: called.append(i))
    assert anon.post("/products/1/delete").status_code == 302 and called == []


def test_role_table_matches_policy(application):
    """is_allowed over every endpoint | manager: all; cashier: only the documented list"""
    for rule in application.url_map.iter_rules():
        if rule.endpoint in app_module.PUBLIC_ENDPOINTS:
            continue
        assert app_module.is_allowed("MANAGER", rule.endpoint)
        assert app_module.is_allowed("CASHIER", rule.endpoint) == (rule.endpoint in app_module.CASHIER_ENDPOINTS)
    assert not app_module.is_allowed("INTRUDER", "dashboard")


@pytest.mark.parametrize("method,url", [("GET", "/reports"), ("GET", "/categories"), ("GET", "/suppliers"),
                                        ("GET", "/employees"), ("GET", "/users"), ("GET", "/"),
                                        ("POST", "/products"), ("POST", "/products/1/delete"),
                                        ("POST", "/products/1/restock"), ("POST", "/customers/1/delete"),
                                        ("POST", "/users"), ("POST", "/employees/1/delete")])
def test_cashier_is_forbidden_from_manager_functions(application, monkeypatch, method, url):
    """Cashier calling manager-only pages/actions | HTTP 403 and no service call"""
    boom = lambda *a, **k: pytest.fail("service must not run for a forbidden role")
    for mod, name in ((products, "delete"), (products, "create"), (products, "restock"), (customers, "delete"),
                      (users, "create"), (employees, "delete"), (reports, "inventory"), (reports, "dashboard")):
        monkeypatch.setattr(mod, name, boom)
    c = signed_in(application, CASHIER)
    with c.session_transaction() as s:
        s["csrf"] = "tok"
    resp = c.open(url, method=method, data={"csrf_token": "tok"} if method == "POST" else None)
    assert resp.status_code == 403


def test_cashier_can_use_sales_and_customers(application, monkeypatch):
    """Cashier opens New Sale, Sales History, Products (read), Customers | HTTP 200"""
    monkeypatch.setattr(customers, "list_all", lambda: [{"customer_id": 1, "full_name": "N"}])
    monkeypatch.setattr(products, "list_for_sale", lambda: [{"product_id": 1, "product_name": "P", "model_no": "M", "unit_price": Decimal("5"), "stock_qty": 3}])
    page = {"rows": [], "page": 1, "pages": 1, "total": 0}
    monkeypatch.setattr(sales, "list_page", lambda *a: page)
    monkeypatch.setattr(customers, "list_page", lambda *a: page)
    monkeypatch.setattr(products, "list_page", lambda *a: page)
    monkeypatch.setattr(categories, "list_all", lambda q=None: [])
    from services import suppliers
    monkeypatch.setattr(suppliers, "list_all", lambda q=None: [])
    c = signed_in(application, CASHIER)
    for url in ("/sales/new", "/sales", "/products", "/customers"):
        assert c.get(url).status_code == 200, url
    html = c.get("/sales/new").get_data(as_text=True)
    assert "Karan Shetty" in html and 'name="employee_id"' not in html


def test_cashier_product_page_has_no_write_controls(application, monkeypatch):
    """Cashier views products | no add form, restock or edit/delete buttons rendered"""
    row = {"product_id": 1, "product_name": "P", "brand": "B", "model_no": "M", "category_id": 1, "category_name": "C",
           "supplier_id": 1, "supplier_name": "S", "unit_price": Decimal("5"), "stock_qty": 1, "reorder_level": 2, "warranty_months": 12}
    monkeypatch.setattr(products, "list_page", lambda *a: {"rows": [row], "page": 1, "pages": 1, "total": 1})
    monkeypatch.setattr(categories, "list_all", lambda q=None: [])
    from services import suppliers
    monkeypatch.setattr(suppliers, "list_all", lambda q=None: [])
    html = signed_in(application, CASHIER).get("/products").get_data(as_text=True)
    assert "Add product" not in html and "Restock" not in html and "/delete" not in html


def test_cashier_sale_uses_own_employee_id(application, monkeypatch):
    """Cashier submits a sale with a forged employee_id | create_sale receives the cashier's own employee id"""
    captured = {}
    monkeypatch.setattr(sales, "create_sale", lambda c, e, p, i: captured.update(emp=e) or {"sale_id": 5, "invoice_no": "INV-1", "total": Decimal("1")})
    c = signed_in(application, CASHIER)
    with c.session_transaction() as s:
        s["csrf"] = "tok"
    resp = c.post("/sales/new", data={"csrf_token": "tok", "customer_id": "1", "employee_id": "999", "payment_method": "CASH",
                                      "product_id": ["1"], "quantity": ["1"]})
    assert resp.status_code == 303 and captured["emp"] == 4


# ------------------------------------------------------------------ login / logout
def test_login_success_starts_session_and_redirects_by_role(anon, monkeypatch):
    """Valid credentials | 303 to dashboard (manager) / new sale (cashier); session holds the user; password never stored in session"""
    monkeypatch.setattr(users, "authenticate", lambda u, p: MANAGER if p == "right-password" else None)
    resp = anon.post("/login", data={"username": "Meera", "password": "right-password", "csrf_token": csrf(anon)})
    assert resp.status_code == 303 and resp.headers["Location"].endswith("/")
    with anon.session_transaction() as s:
        assert s["user"]["role"] == "MANAGER" and "password" not in str(s["user"])
    monkeypatch.setattr(users, "authenticate", lambda u, p: CASHIER)
    other = app_module.create_app({"SECRET_KEY": "k", "TESTING": True}).test_client()
    resp = other.post("/login", data={"username": "karan", "password": "x", "csrf_token": csrf(other)})
    assert resp.headers["Location"].endswith("/sales/new")


def test_login_failure_is_generic_401(anon, monkeypatch):
    """Wrong credentials | HTTP 401, same message for unknown user or bad password, no session"""
    monkeypatch.setattr(users, "authenticate", lambda u, p: None)
    resp = anon.post("/login", data={"username": "ghost", "password": "nope", "csrf_token": csrf(anon)})
    assert resp.status_code == 401 and "Invalid username or password." in resp.get_data(as_text=True)
    with anon.session_transaction() as s:
        assert "user" not in s


def test_login_is_throttled_after_repeated_failures(anon, monkeypatch):
    """5 failed attempts for one username | 6th attempt gets HTTP 429 even with the right password"""
    monkeypatch.setattr(users, "authenticate", lambda u, p: MANAGER if p == "right-password" else None)
    token = csrf(anon)
    for _ in range(5):
        assert anon.post("/login", data={"username": "meera", "password": "bad", "csrf_token": token}).status_code == 401
    assert anon.post("/login", data={"username": "meera", "password": "right-password", "csrf_token": token}).status_code == 429


@pytest.mark.parametrize("target,expected", [("//evil.example/x", "/"), ("https://evil.example", "/"),
                                              ("/\\evil", "/"), ("/products", "/products")])
def test_login_next_cannot_redirect_off_site(anon, monkeypatch, target, expected):
    """Login with a next= parameter | only same-site relative paths are followed (no open redirect)"""
    monkeypatch.setattr(users, "authenticate", lambda u, p: MANAGER)
    resp = anon.post("/login", data={"username": "m", "password": "p", "next": target, "csrf_token": csrf(anon)})
    assert resp.status_code == 303 and resp.headers["Location"].endswith(expected) and "evil" not in resp.headers["Location"]


def test_login_requires_csrf_token(anon, monkeypatch):
    """Login POST without a CSRF token | HTTP 400, authenticate never called"""
    monkeypatch.setattr(users, "authenticate", lambda u, p: pytest.fail("must not authenticate"))
    assert anon.post("/login", data={"username": "m", "password": "p"}).status_code == 400


def test_logout_is_post_only_and_clears_session(application):
    """GET /logout rejected; POST /logout with token ends the session | 405 then redirect to login, protected page redirects again"""
    c = signed_in(application, MANAGER)
    assert c.get("/logout").status_code == 405
    with c.session_transaction() as s:
        s["csrf"] = "tok"
    resp = c.post("/logout", data={"csrf_token": "tok"})
    assert resp.status_code == 303 and "/login" in resp.headers["Location"]
    assert c.get("/products").status_code == 302


def test_signed_in_user_visiting_login_is_redirected(application):
    """Already signed in and opening /login | redirected to the landing page"""
    assert signed_in(application, MANAGER).get("/login").status_code == 302


def test_session_cookie_settings_and_lifetime(application):
    """Session lifetime configured and cookie hardening present | 8-hour lifetime"""
    assert application.config["PERMANENT_SESSION_LIFETIME"].total_seconds() == 8 * 3600


# ------------------------------------------------------------------ users service
def test_create_user_stores_only_a_hash(fake_db):
    """Create a user | the INSERT carries a salted hash, never the plain password; username lower-cased"""
    conn = fake_db([], {"new_id": 3})
    uid = users.create({"username": "Karan", "role": "cashier", "password": "correct-horse-1", "password_confirm": "correct-horse-1", "employee_id": "4"})
    sql, params = conn.executed[0]
    assert uid == 3 and params["u"] == "karan" and params["r"] == "CASHIER"
    assert params["h"] != "correct-horse-1" and check_password_hash(params["h"], "correct-horse-1")
    assert "correct-horse-1" not in sql and conn.commits == 1


@pytest.mark.parametrize("form", [
    {"username": "ab", "role": "MANAGER", "password": "longenough-1", "password_confirm": "longenough-1", "employee_id": "1"},
    {"username": "Bad Name!", "role": "MANAGER", "password": "longenough-1", "password_confirm": "longenough-1", "employee_id": "1"},
    {"username": "okname", "role": "ROOT", "password": "longenough-1", "password_confirm": "longenough-1", "employee_id": "1"},
    {"username": "okname", "role": "MANAGER", "password": "short", "password_confirm": "short", "employee_id": "1"},
    {"username": "okname", "role": "MANAGER", "password": "longenough-1", "password_confirm": "different-1234", "employee_id": "1"},
    {"username": "okname", "role": "MANAGER", "password": "okname", "password_confirm": "okname", "employee_id": "1"},
    {"username": "okname", "role": "MANAGER", "password": "longenough-1", "password_confirm": "longenough-1", "employee_id": "x"}])
def test_create_user_validation(fake_db, form):
    """Bad username, role, short/mismatched/equal password, bad employee id | ValidationError and no SQL"""
    conn = fake_db([])
    with pytest.raises(ValidationError):
        users.create(form)
    assert conn.executed == []


def test_duplicate_username_is_conflict(fake_db):
    """ORA-00001 on user insert | ConflictError (409)"""
    fake_db([{"match": "INSERT INTO USERS", "error": oracledb.IntegrityError("ORA-00001: unique constraint violated")}])
    with pytest.raises(ConflictError):
        users.create({"username": "meera", "role": "MANAGER", "password": "longenough-1", "password_confirm": "longenough-1", "employee_id": "1"})


COLS = ["USER_ID", "USERNAME", "PASSWORD_HASH", "ROLE", "EMPLOYEE_ID", "FULL_NAME"]


def test_authenticate_accepts_only_the_right_password(fake_db):
    """Correct password -> user dict and LAST_LOGIN update; wrong password or unknown user -> None"""
    h = generate_password_hash("correct-horse-1")
    conn = fake_db([{"match": "FROM USERS u JOIN", "cols": COLS, "rows": [(1, "meera", h, "MANAGER", 9, "Meera Nair")]}])
    user = users.authenticate(" Meera ", "correct-horse-1")
    assert user == {"id": 1, "username": "meera", "role": "MANAGER", "employee_id": 9, "name": "Meera Nair"}
    assert "password_hash" not in user and conn.executed[0][1] == {"u": "meera"}
    assert users.authenticate("meera", "wrong-password") is None
    fake_db([{"match": "FROM USERS u JOIN", "cols": COLS, "rows": []}])
    assert users.authenticate("ghost", "whatever-123") is None


def test_cannot_delete_own_or_last_manager_account(fake_db):
    """Delete own account / the only manager | ConflictError; deleting another cashier works"""
    fake_db([{"match": "SELECT ROLE FROM USERS", "cols": ["ROLE"], "rows": [("MANAGER",)]},
             {"match": "COUNT(*)", "cols": ["N"], "rows": [(1,)]}])
    with pytest.raises(ConflictError, match="own account"):
        users.delete(1, 1)
    with pytest.raises(ConflictError, match="last manager"):
        users.delete(5, 1)
    conn = fake_db([{"match": "SELECT ROLE FROM USERS", "cols": ["ROLE"], "rows": [("CASHIER",)]}])
    users.delete(7, 1)
    assert any(s.startswith("DELETE FROM USERS") for s in conn.sql_log())


def test_change_own_password_requires_current_password(fake_db):
    """Wrong current password | ValidationError; correct current + valid new -> hashed UPDATE"""
    h = generate_password_hash("old-password-1")
    rows = [{"match": "SELECT USERNAME, PASSWORD_HASH", "cols": ["USERNAME", "PASSWORD_HASH"], "rows": [("meera", h)]},
            {"match": "SELECT USERNAME FROM USERS", "cols": ["USERNAME"], "rows": [("meera",)]}]
    fake_db(rows)
    with pytest.raises(ValidationError, match="Current password"):
        users.change_own_password(1, {"current_password": "nope", "password": "new-password-1", "password_confirm": "new-password-1"})
    conn = fake_db(rows)
    users.change_own_password(1, {"current_password": "old-password-1", "password": "new-password-1", "password_confirm": "new-password-1"})
    update = [p for s, p in conn.executed if s.startswith("UPDATE USERS SET PASSWORD_HASH")][0]
    assert check_password_hash(update["h"], "new-password-1")


# ------------------------------------------------------------------ employees service
GOOD = {"full_name": "Asha Menon", "email": "asha@example.com", "phone": "9000002001", "job_title": "Sales Associate", "hire_date": "2022-06-01"}


def test_employee_create_binds_parameters(fake_db):
    """Create an employee | bind variables incl. a real date object; commit once"""
    conn = fake_db([], {"new_id": 5})
    assert employees.create({**GOOD, "full_name": "x'); DROP TABLE EMPLOYEES;--"}) == 5
    sql, params = conn.executed[0]
    assert "DROP" not in sql and params["hired"] == datetime.date(2022, 6, 1) and conn.commits == 1


@pytest.mark.parametrize("bad", [{"hire_date": "2999-01-01"}, {"hire_date": "not-a-date"}, {"hire_date": ""},
                                 {"email": "nope"}, {"job_title": ""}])
def test_employee_validation(fake_db, bad):
    """Future/invalid hire date, bad email, missing job title | ValidationError and no SQL"""
    conn = fake_db([])
    with pytest.raises(ValidationError):
        employees.create({**GOOD, **bad})
    assert conn.executed == []


def test_employee_delete_with_history_is_conflict(fake_db):
    """Deleting an employee referenced by sales/users (ORA-02292) | ConflictError, safe text"""
    fake_db([{"match": "DELETE FROM EMPLOYEES", "error": oracledb.IntegrityError("ORA-02292: child record found FK_SALES_EMPLOYEE")}])
    with pytest.raises(ConflictError) as e:
        employees.delete(1)
    assert "FK_" not in str(e.value) and "ORA" not in str(e.value)


def test_serve_module_exposes_waitress_entrypoint():
    """Importing serve.py | does not start a server; waitress is installed"""
    import serve
    assert callable(serve.serve)


def test_users_and_employee_pages_render_for_manager(application, monkeypatch):
    """Manager opens Employees and User accounts | pages render with data and password inputs"""
    when = datetime.datetime(2026, 1, 2, 3, 4)
    monkeypatch.setattr(employees, "list_page", lambda *a: {"rows": [{"employee_id": 1, "full_name": "A", "email": "a@x.com", "phone": None, "job_title": "J", "hire_date": datetime.date(2022, 1, 1)}], "page": 1, "pages": 1, "total": 1})
    monkeypatch.setattr(employees, "list_without_user", lambda: [{"employee_id": 2, "full_name": "B", "job_title": "Cashier"}])
    monkeypatch.setattr(users, "list_all", lambda: [{"user_id": 1, "username": "meera", "role": "MANAGER", "full_name": "A", "job_title": "J", "last_login": when},
                                                    {"user_id": 2, "username": "karan", "role": "CASHIER", "full_name": "B", "job_title": "C", "last_login": None}])
    c = signed_in(application, MANAGER)
    assert c.get("/employees").status_code == 200
    html = c.get("/users").get_data(as_text=True)
    assert "meera" in html and "never" in html and 'type="password"' in html
    assert html.count("/delete") == 1          # no delete button for your own account
