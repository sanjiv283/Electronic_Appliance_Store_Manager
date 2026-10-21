"""Flask route tests. Services are replaced by stubs, so no Oracle is needed."""
import re
from datetime import datetime
from decimal import Decimal

import pytest

import app as app_module
from services import (categories, customers, employees, products, reports, sales, suppliers)
from services.errors import (ConflictError, DatabaseUnavailableError, InsufficientStockError, ValidationError)


@pytest.fixture
def client(monkeypatch):
    # /categories is used only to obtain a CSRF token, so give it harmless data
    monkeypatch.setattr(categories, "list_all", lambda q=None: [])
    application = app_module.create_app({"SECRET_KEY": "test-key-not-secret", "TESTING": True})
    c = application.test_client()
    with c.session_transaction() as sess:       # these tests exercise routes as a signed-in manager
        sess["user"] = {"id": 1, "username": "meera", "role": "MANAGER", "employee_id": 9, "name": "Meera Nair"}
    return c


def token(client):
    html = client.get("/categories", follow_redirects=True).get_data(as_text=True)
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


@pytest.fixture
def stub_lists(monkeypatch):
    monkeypatch.setattr(categories, "list_all", lambda q=None: [
        {"category_id": 1, "category_name": "<script>alert(1)</script>", "description": None, "product_count": 0}])
    monkeypatch.setattr(suppliers, "list_all", lambda q=None: [])


def test_dashboard_shows_real_stats_when_service_returns(client, monkeypatch):
    """Dashboard with stubbed DB figures | 200 and the figures are rendered"""
    monkeypatch.setattr(reports, "dashboard", lambda: {
        "stats": {"products": 14, "customers": 8, "sales": 8, "revenue": Decimal("1234.50"), "low_stock": 2},
        "recent": [{"sale_id": 1, "invoice_no": "INV-000001", "sale_date": datetime(2026, 1, 1, 9, 30),
                    "customer_name": "A", "total_amount": Decimal("10")}]})
    html = client.get("/").get_data(as_text=True)
    assert "₹1,234.50" in html and "INV-000001" in html


def test_dashboard_without_database_shows_error_not_fake_numbers(client, monkeypatch):
    """Oracle unavailable | HTTP 503 error page, no statistics shown"""
    def down():
        raise DatabaseUnavailableError("The database is unavailable. Check ...")
    monkeypatch.setattr(reports, "dashboard", down)
    resp = client.get("/")
    assert resp.status_code == 503 and "unavailable" in resp.get_data(as_text=True)
    assert "Revenue" not in resp.get_data(as_text=True)


def test_output_is_html_escaped(client, stub_lists):
    """Category name containing <script> | rendered escaped, never as live markup"""
    html = client.get("/categories").get_data(as_text=True)
    assert "<script>alert(1)" not in html and "&lt;script&gt;alert(1)" in html


def test_post_without_csrf_token_rejected(client, monkeypatch):
    """POST with no CSRF token | 400 and the service is never called"""
    called = []
    monkeypatch.setattr(categories, "create", lambda f: called.append(f))
    assert client.post("/categories", data={"category_name": "X"}).status_code == 400
    assert called == []


def test_post_with_wrong_csrf_token_rejected(client, stub_lists):
    """POST with a forged CSRF token | 400"""
    token(client)
    assert client.post("/categories", data={"category_name": "X", "csrf_token": "forged"}).status_code == 400


def test_post_with_valid_csrf_calls_service_and_redirects(client, stub_lists, monkeypatch):
    """Valid CSRF token + valid form | service called, 303 redirect (post/redirect/get)"""
    seen = []
    monkeypatch.setattr(categories, "create", lambda f: seen.append(dict(f)) or 5)
    resp = client.post("/categories", data={"category_name": "Fans", "csrf_token": token(client)})
    assert resp.status_code == 303 and seen[0]["category_name"] == "Fans"


def test_csrf_header_accepted_for_scripted_clients(client, stub_lists, monkeypatch):
    """X-CSRF-Token header instead of form field | accepted"""
    monkeypatch.setattr(categories, "delete", lambda i: None)
    resp = client.post("/categories/3/delete", headers={"X-CSRF-Token": token(client)})
    assert resp.status_code == 303


def test_get_never_mutates_state(client):
    """GET on delete / update / restock URLs | 405 Method Not Allowed"""
    for url in ("/products/1/delete", "/customers/1/update", "/products/1/restock", "/sales/new/delete"):
        assert client.get(url).status_code in (404, 405)
    assert client.get("/products/1/delete").status_code == 405


def test_validation_error_returns_400(client, stub_lists, monkeypatch):
    """Service raises ValidationError | HTTP 400 with the message"""
    def bad(form):
        raise ValidationError("Category name is required.")
    monkeypatch.setattr(categories, "create", bad)
    resp = client.post("/categories", data={"csrf_token": token(client)})
    assert resp.status_code == 400 and "Category name is required" in resp.get_data(as_text=True)


def test_conflict_returns_409(client, stub_lists, monkeypatch):
    """Delete of a referenced row | HTTP 409 with friendly message"""
    def conflict(i):
        raise ConflictError("This record is referenced by other records ...")
    monkeypatch.setattr(categories, "delete", conflict)
    assert client.post("/categories/1/delete", data={"csrf_token": token(client)}).status_code == 409


def test_insufficient_stock_returns_409(client, monkeypatch):
    """Sale rejected for insufficient stock | HTTP 409 with product detail"""
    monkeypatch.setattr(sales, "create_sale", lambda *a: (_ for _ in ()).throw(InsufficientStockError("Insufficient stock for: Mixer")))
    t = token(client)
    resp = client.post("/sales/new", data={"csrf_token": t, "customer_id": "1", "employee_id": "1",
                                           "payment_method": "CASH", "product_id": ["2"], "quantity": ["9"]})
    assert resp.status_code == 409 and "Mixer" in resp.get_data(as_text=True)


def test_sale_post_ignores_client_supplied_price_and_total(client, monkeypatch):
    """Forged price/total/employee fields in the sale POST | price and total ignored; employee id comes from the login session"""
    captured = {}
    monkeypatch.setattr(sales, "create_sale", lambda c, e, p, items: captured.update(args=(c, e, p, items))
                        or {"sale_id": 3, "invoice_no": "INV-X", "total": Decimal("1.00")})
    t = token(client)
    resp = client.post("/sales/new", data={"csrf_token": t, "customer_id": "1", "employee_id": "999",
                                           "payment_method": "UPI", "product_id": ["7", "7"], "quantity": ["1", "2"],
                                           "unit_price": "0.01", "total_amount": "0.01"})
    assert resp.status_code == 303 and captured["args"] == ("1", 9, "UPI", [(7, 3)])


def test_empty_sale_rejected_400(client):
    """Sale form with no product lines | HTTP 400, create_sale never reached"""
    t = token(client)
    resp = client.post("/sales/new", data={"csrf_token": t, "customer_id": "1", "employee_id": "1",
                                           "payment_method": "CASH", "product_id": [""], "quantity": [""]})
    assert resp.status_code == 400


def test_unknown_route_404_and_bad_sale_id(client, monkeypatch):
    """Unknown URL -> 404; non-numeric sale id -> 404"""
    assert client.get("/nope").status_code == 404
    assert client.get("/sales/abc").status_code == 404


def test_unexpected_exception_is_generic_500(client, monkeypatch):
    """Unexpected exception text with a secret | HTTP 500, page shows a generic message only"""
    app = client.application
    app.config["TESTING"] = False
    app.config["PROPAGATE_EXCEPTIONS"] = False
    monkeypatch.setattr(reports, "dashboard", lambda: 1 / 0)
    resp = client.get("/")
    assert resp.status_code == 500 and "division" not in resp.get_data(as_text=True)


def test_security_headers_present(client, stub_lists):
    """Any response | CSP, nosniff and frame protection headers set"""
    h = client.get("/categories").headers
    assert "default-src 'self'" in h["Content-Security-Policy"]
    assert h["X-Content-Type-Options"] == "nosniff" and h["X-Frame-Options"] == "DENY"


def test_health_endpoint_reports_unavailable_honestly(client, monkeypatch):
    """No Oracle configured | /health returns 503 and database=unavailable, never 'ok'"""
    for k in ("DB_HOST", "DB_PORT", "DB_SERVICE_NAME", "DB_USER", "DB_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    resp = client.get("/health")
    assert resp.status_code == 503 and resp.json["database"] == "unavailable"


def test_health_endpoint_ok_when_database_answers(client, monkeypatch):
    """health_check reporting success | /health 200 with no secrets in the body"""
    from services import database
    monkeypatch.setattr(database, "health_check", lambda: (True, "Connected as APPLIANCE_APP to service XEPDB1"))
    resp = client.get("/health")
    assert resp.status_code == 200 and "password" not in resp.get_data(as_text=True).lower()


def test_every_listing_page_renders(client, monkeypatch):
    """Products, customers, sales, sale detail, new sale, reports pages | all render 200 with stubbed data"""
    page = lambda rows: {"rows": rows, "page": 1, "pages": 2, "total": 11}
    when = datetime(2026, 1, 2, 3, 4)
    monkeypatch.setattr(categories, "list_all", lambda q=None: [{"category_id": 1, "category_name": "C", "description": "", "product_count": 1}])
    monkeypatch.setattr(suppliers, "list_all", lambda q=None: [{"supplier_id": 1, "supplier_name": "S", "contact_person": None, "email": None, "phone": None, "address": None, "product_count": 0}])
    monkeypatch.setattr(products, "list_page", lambda *a: page([{"product_id": 1, "product_name": "P", "brand": "B", "model_no": "M", "category_id": 1, "category_name": "C", "supplier_id": 1, "supplier_name": "S", "unit_price": Decimal("5"), "stock_qty": 1, "reorder_level": 2, "warranty_months": 12}]))
    monkeypatch.setattr(customers, "list_page", lambda *a: page([{"customer_id": 1, "full_name": "N", "email": "e@x.com", "phone": "1234567", "address": None}]))
    monkeypatch.setattr(customers, "list_all", lambda: [{"customer_id": 1, "full_name": "N"}])
    monkeypatch.setattr(products, "list_for_sale", lambda: [{"product_id": 1, "product_name": "P", "model_no": "M", "unit_price": Decimal("5"), "stock_qty": 3}])
    row = {"sale_id": 1, "invoice_no": "INV-1", "sale_date": when, "payment_method": "BANK_TRANSFER", "customer_name": "N", "employee_name": "E", "line_count": 1, "unit_count": 1, "total_amount": Decimal("5")}
    monkeypatch.setattr(sales, "list_page", lambda *a: page([row]))
    monkeypatch.setattr(sales, "get", lambda i: {"sale": {**row, "total_matches": "Y"}, "items": [{"product_name": "P", "model_no": "M", "quantity": 1, "unit_price": Decimal("5"), "line_total": Decimal("5")}]})
    monkeypatch.setattr(reports, "inventory", lambda: [{"product_name": "P", "category_name": "C", "stock_qty": 0, "reorder_level": 1, "unit_price": Decimal("1"), "stock_value": Decimal("0"), "status": "OUT OF STOCK"}])
    monkeypatch.setattr(reports, "sales_by_month", lambda: [{"sale_month": "2026-01", "sales_count": 1, "revenue": Decimal("5")}])
    monkeypatch.setattr(reports, "top_products", lambda limit=5: [{"product_name": "P", "units_sold": 1, "revenue": Decimal("5")}])
    monkeypatch.setattr(reports, "category_revenue", lambda: [{"category_name": "C", "revenue": Decimal("5")}])
    monkeypatch.setattr(reports, "customer_summary", lambda: [{"customer_id": 1, "full_name": "N", "purchases": 0, "total_spent": Decimal("0"), "last_purchase": None}])
    for url in ("/products", "/products?q=x&low_stock=1&page=2", "/customers", "/categories", "/suppliers",
                "/sales", "/sales/new", "/sales/1", "/reports"):
        resp = client.get(url)
        assert resp.status_code == 200, url
    html = client.get("/products?q=x&page=1").get_data(as_text=True)
    assert "page=2" in html and "q=x" in html            # working pagination link keeps the filter
