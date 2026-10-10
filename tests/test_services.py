"""Service-layer unit tests against a FAKE connection (no Oracle)."""
from decimal import Decimal

import oracledb
import pytest

from services import categories, customers, database, products, sales
from services import validation as v
from services.errors import (ConflictError, DatabaseUnavailableError, InsufficientStockError,
                             NotFoundError, ValidationError)


# ---------- validation ----------
@pytest.mark.parametrize("value", ["0", "10.50", "99999999.99"])
def test_money_accepts_valid(value):
    """Valid monetary strings | accepted and quantised to 2 decimals"""
    assert v.money(value) == Decimal(value).quantize(Decimal("0.01"))


@pytest.mark.parametrize("value", ["-1", "abc", "1.234", "NaN", "100000000", ""])
def test_money_rejects_invalid(value):
    """Negative, non-numeric, 3-decimal, NaN, too-large prices | ValidationError"""
    with pytest.raises(ValidationError):
        v.money(value)


def test_email_phone_validation():
    """Malformed email / phone numbers | ValidationError; valid ones accepted"""
    assert v.email({"email": "a.b@example.com"}) == "a.b@example.com"
    assert v.phone({"phone": "+91 90000-00001"})
    for bad in ("nope", "a@b", "a b@c.com"):
        with pytest.raises(ValidationError):
            v.email({"email": bad})
    for bad in ("12", "abcdefgh", "1" * 25):
        with pytest.raises(ValidationError):
            v.phone({"phone": bad})


@pytest.mark.parametrize("value", ["0", "-3", "x", "1.5", None, "10000000000000"])
def test_record_id_rejects_bad_ids(value):
    """Zero, negative, non-integer, None, absurd IDs | ValidationError"""
    with pytest.raises(ValidationError):
        v.record_id(value)


# ---------- sale item parsing ----------
def test_parse_items_merges_duplicates_and_sorts():
    """Duplicate products merged, lock order ascending | [(1, 3), (5, 2)]"""
    assert sales.parse_items(["5", "1", "5"], ["1", "3", "1"]) == [(1, 3), (5, 2)]


def test_parse_items_skips_blank_rows_but_rejects_empty_sale():
    """Blank form rows ignored; only blanks -> empty sale rejected | ValidationError"""
    assert sales.parse_items(["", "2"], ["", "1"]) == [(2, 1)]
    with pytest.raises(ValidationError):
        sales.parse_items([""], [""])


@pytest.mark.parametrize("qty", ["0", "-1", "abc", "1.5", "1001"])
def test_parse_items_rejects_bad_quantity(qty):
    """Zero, negative, non-numeric, fractional or huge quantity | ValidationError"""
    with pytest.raises(ValidationError):
        sales.parse_items(["1"], [qty])


# ---------- sales transaction ----------
PRODUCTS = {1: (1, "Fridge", Decimal("28999.00"), 5), 2: (2, "Mixer", Decimal("3299.00"), 2),
            3: (3, "Kettle", Decimal("1199.00"), 40)}


def sale_responders(**extra):
    base = [{"match": "SELECT 1 FROM CUSTOMERS", "rows": [(1,)]},
            {"match": "SELECT 1 FROM EMPLOYEES", "rows": [(1,)]},
            {"match": "FOR UPDATE WAIT", "rows": lambda p: [PRODUCTS[p["pid"]]] if p["pid"] in PRODUCTS else []}]
    return extra.get("before", []) + base


def test_successful_multi_item_sale(fake_db):
    """Two-item sale | one commit, DB-priced total 35597.00 (Decimal), stock deducted per item, connection closed"""
    conn = fake_db(sale_responders(), {"sale_id": 77, "invoice_no": "INV-001000"})
    result = sales.create_sale("1", "1", "CARD", [(2, 2), (1, 1)])
    assert result["sale_id"] == 77 and result["invoice_no"] == "INV-001000"
    assert result["total"] == Decimal("35597.00")
    assert conn.commits == 1 and conn.rollbacks == 0 and conn.closed
    deductions = [p for s, p in conn.executed if s.startswith("UPDATE PRODUCTS")]
    assert deductions == [{"qty": 1, "pid": 1}, {"qty": 2, "pid": 2}]
    assert sum(1 for s in conn.sql_log() if s.startswith("INSERT INTO SALE_ITEMS")) == 2


def test_locks_taken_in_ascending_product_order(fake_db):
    """Items supplied as 3,1,2 | FOR UPDATE issued for 1,2,3 (consistent order -> no deadlock), all before any INSERT"""
    conn = fake_db(sale_responders(), {})
    sales.create_sale(1, 1, "CASH", [(3, 1), (1, 1), (2, 1)])
    locks = [p["pid"] for s, p in conn.executed if "FOR UPDATE" in s]
    assert locks == [1, 2, 3]
    first_insert = min(i for i, s in enumerate(conn.sql_log()) if s.startswith("INSERT"))
    assert max(i for i, s in enumerate(conn.sql_log()) if "FOR UPDATE" in s) < first_insert


def test_insufficient_stock_rejected_with_rollback(fake_db):
    """Request 3 of a product with 2 in stock | InsufficientStockError, nothing inserted or updated, no commit, rolled back"""
    conn = fake_db(sale_responders())
    with pytest.raises(InsufficientStockError, match="Mixer"):
        sales.create_sale(1, 1, "CASH", [(1, 1), (2, 3)])
    assert conn.commits == 0 and conn.rollbacks >= 1 and conn.closed
    assert not [s for s in conn.sql_log() if s.startswith(("INSERT", "UPDATE"))]


def test_unknown_product_rejected(fake_db):
    """Product id 999 does not exist | ValidationError, no writes, no commit"""
    conn = fake_db(sale_responders())
    with pytest.raises(ValidationError, match="999"):
        sales.create_sale(1, 1, "CASH", [(999, 1)])
    assert conn.commits == 0 and conn.closed


def test_unknown_customer_rejected(fake_db):
    """Customer id missing in DB | ValidationError before any product is locked"""
    conn = fake_db([{"match": "SELECT 1 FROM CUSTOMERS", "rows": []}] + sale_responders())
    with pytest.raises(ValidationError, match="customer"):
        sales.create_sale(1, 1, "CASH", [(1, 1)])
    assert not [s for s in conn.sql_log() if "FOR UPDATE" in s]


def test_failure_after_partial_work_rolls_back_everything(fake_db):
    """Stock UPDATE fails (CHECK violation) after sale+item inserted | ValidationError, rollback, NO commit"""
    boom = oracledb.IntegrityError("ORA-02290: check constraint (APPLIANCE_APP.CK_PRODUCTS_STOCK) violated")
    conn = fake_db([{"match": "UPDATE PRODUCTS", "error": boom}] + sale_responders())
    with pytest.raises(ValidationError):
        sales.create_sale(1, 1, "CASH", [(1, 1)])
    assert conn.commits == 0 and conn.rollbacks >= 1 and conn.closed
    assert any(s.startswith("INSERT INTO SALES") for s in conn.sql_log())   # work had started


@pytest.mark.parametrize("args", [(1, 1, "BARTER", [(1, 1)]), (1, 1, "CASH", []), ("x", 1, "CASH", [(1, 1)]),
                                  (1, 0, "CASH", [(1, 1)])])
def test_create_sale_validates_before_touching_db(fake_db, args):
    """Bad payment method / empty items / bad ids | ValidationError and zero SQL executed"""
    conn = fake_db(sale_responders())
    with pytest.raises(ValidationError):
        sales.create_sale(*args)
    assert conn.executed == []


def test_sale_sql_is_parameterised_and_never_trusts_client_price(fake_db):
    """Every statement uses bind variables; create_sale has no price/total input | no literals from user data in SQL"""
    conn = fake_db(sale_responders())
    sales.create_sale(1, 1, "UPI", [(1, 1)])
    for sql, params in conn.executed:
        assert params is not None and "28999" not in sql and "UPI" not in sql
    import inspect
    assert "price" not in inspect.signature(sales.create_sale).parameters
    assert "total" not in inspect.signature(sales.create_sale).parameters


def test_stock_deduction_only_in_service_not_trigger():
    """advanced_features.sql trigger body | contains no UPDATE of PRODUCTS (single deduction point)"""
    text = open("database/advanced_features.sql").read().upper()
    trigger = text[text.index("CREATE OR REPLACE TRIGGER"):text.index("END TRG_SALES_PROTECT_HISTORY")]
    assert "UPDATE PRODUCTS" not in trigger


# ---------- CRUD ----------
def test_product_create_uses_bind_parameters(fake_db):
    """SQL-injection text in a product name | stays in bind params, never in the SQL string"""
    conn = fake_db([], {"new_id": 9})
    evil = "x'); DROP TABLE PRODUCTS;--"
    form = {"product_name": evil, "brand": "B", "model_no": "M-1", "category_id": "1", "supplier_id": "1",
            "unit_price": "100.00", "stock_qty": "3", "reorder_level": "1", "warranty_months": "12"}
    assert products.create(form) == 9
    sql, params = conn.executed[0]
    assert "DROP" not in sql and params["name"] == evil and conn.commits == 1


def test_product_rejects_negative_price_and_stock(fake_db):
    """Negative price or stock in the form | ValidationError before any SQL"""
    conn = fake_db([])
    base = {"product_name": "P", "brand": "B", "model_no": "M", "category_id": "1", "supplier_id": "1",
            "unit_price": "10", "stock_qty": "1", "reorder_level": "1", "warranty_months": "1"}
    for bad in ({"unit_price": "-5"}, {"stock_qty": "-1"}):
        with pytest.raises(ValidationError):
            products.create({**base, **bad})
    assert conn.executed == []


def test_update_missing_row_is_not_found(fake_db):
    """UPDATE affecting 0 rows | NotFoundError (404)"""
    fake_db([{"match": "UPDATE CATEGORIES", "rowcount": 0}])
    with pytest.raises(NotFoundError):
        categories.update(5, {"category_name": "X"})


def test_delete_referenced_row_gives_safe_conflict(fake_db):
    """ORA-02292 on delete | ConflictError with friendly text, no ORA code/constraint name leaked"""
    err = oracledb.IntegrityError("ORA-02292: integrity constraint (APPLIANCE_APP.FK_SALES_CUSTOMER) violated - child record found")
    fake_db([{"match": "DELETE FROM CUSTOMERS", "error": err}])
    with pytest.raises(ConflictError) as e:
        customers.delete(1)
    assert "referenced" in str(e.value) and "ORA" not in str(e.value) and "FK_" not in str(e.value)


def test_duplicate_value_gives_conflict(fake_db):
    """ORA-00001 on insert | ConflictError (409) with generic message"""
    fake_db([{"match": "INSERT INTO CATEGORIES", "error": oracledb.IntegrityError("ORA-00001: unique constraint (X.UQ) violated")}])
    with pytest.raises(ConflictError):
        categories.create({"category_name": "Dup"})


def test_connectivity_error_is_sanitised(fake_db):
    """Listener down (ORA-12541) | DatabaseUnavailableError (503) without host/user/password details"""
    fake_db([{"match": "SELECT", "error": oracledb.OperationalError("ORA-12541: TNS:no listener (host=secret-host pw=hunter2)")}])
    with pytest.raises(DatabaseUnavailableError) as e:
        customers.list_all()
    assert "hunter2" not in str(e.value) and "secret-host" not in str(e.value)


def test_restock_calls_stored_procedure_and_commits(fake_db):
    """Restock 10 units | SP_RESTOCK_PRODUCT called with (id, qty), exactly one commit"""
    conn = fake_db([])
    products.restock("4", "10")
    assert conn.executed == [("CALL SP_RESTOCK_PRODUCT", [4, 10])] and conn.commits == 1
    with pytest.raises(ValidationError):
        products.restock("4", "0")


def test_restock_unknown_product_maps_to_not_found(fake_db):
    """Procedure raises ORA-20002 | NotFoundError, rolled back"""
    conn = fake_db([{"match": "CALL SP_RESTOCK_PRODUCT", "error": oracledb.DatabaseError("ORA-20002: Product 9 does not exist.")}])
    with pytest.raises(NotFoundError):
        products.restock(9, 1)
    assert conn.commits == 0 and conn.closed


def test_database_get_connection_failure_translated(monkeypatch):
    """oracledb.connect raising ORA-01017 (bad login) | DatabaseUnavailableError, no credentials in message"""
    monkeypatch.setenv("DB_HOST", "h"); monkeypatch.setenv("DB_PORT", "1521")
    monkeypatch.setenv("DB_SERVICE_NAME", "XEPDB1"); monkeypatch.setenv("DB_USER", "appliance_app")
    monkeypatch.setenv("DB_PASSWORD", "pw-should-not-leak")
    def fail(**kw):
        raise oracledb.DatabaseError("ORA-01017: invalid credential for user appliance_app pw-should-not-leak")
    monkeypatch.setattr(database.oracledb, "connect", fail)
    with pytest.raises(DatabaseUnavailableError) as e:
        database.get_connection()
    assert "pw-should-not-leak" not in str(e.value)


def test_health_check_reports_failure_honestly(monkeypatch):
    """No DB configured | health_check returns (False, message) - never claims success"""
    for k in ("DB_HOST", "DB_PORT", "DB_SERVICE_NAME", "DB_USER", "DB_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    ok, message = database.health_check()
    assert ok is False and "DB_HOST" in message
