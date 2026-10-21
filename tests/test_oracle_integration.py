"""LIVE Oracle integration tests.

Run only against a dedicated TEST schema (e.g. user appliance_test created with
setup_user.sql, then schema.sql + advanced_features.sql loaded; seed.sql optional).
Tests create uniquely tagged rows and delete only those rows. They never drop
or reset anything. Enable with:

    RUN_ORACLE_TESTS=1 TEST_DB_HOST=... TEST_DB_PORT=1521 TEST_DB_SERVICE_NAME=XEPDB1
    TEST_DB_USER=appliance_test TEST_DB_PASSWORD=...   (python -m pytest tests/test_oracle_integration.py -v)

Without them every test is reported as BLOCKED (skipped with a BLOCKED reason).
"""
import os
import threading
import uuid
from decimal import Decimal

import oracledb
import pytest

from services import categories, customers, database, employees, products, sales, suppliers, users
from services.errors import ConflictError, InsufficientStockError, ValidationError

_NEEDED = ("TEST_DB_HOST", "TEST_DB_PORT", "TEST_DB_SERVICE_NAME", "TEST_DB_USER", "TEST_DB_PASSWORD")
_missing = [n for n in _NEEDED if not os.environ.get(n)]
_blocked = None
if os.environ.get("RUN_ORACLE_TESTS") != "1":
    _blocked = "BLOCKED: live Oracle tests not enabled (set RUN_ORACLE_TESTS=1 and TEST_DB_* variables)"
elif _missing:
    _blocked = "BLOCKED: missing " + ", ".join(_missing)
elif os.environ["TEST_DB_USER"].upper() in ("SYS", "SYSTEM"):
    _blocked = "BLOCKED: refusing to run as an administrator account"
pytestmark = pytest.mark.skipif(_blocked is not None, reason=_blocked or "")


@pytest.fixture(scope="module", autouse=True)
def oracle_env():
    mp = pytest.MonkeyPatch()
    for name, test_name in (("DB_HOST", "TEST_DB_HOST"), ("DB_PORT", "TEST_DB_PORT"),
                            ("DB_SERVICE_NAME", "TEST_DB_SERVICE_NAME"), ("DB_USER", "TEST_DB_USER"),
                            ("DB_PASSWORD", "TEST_DB_PASSWORD")):
        mp.setenv(name, os.environ[test_name])
    yield
    mp.undo()


@pytest.fixture
def conn():
    c = database.get_connection()
    yield c
    c.rollback()
    c.close()


def tag():
    return "ITEST-" + uuid.uuid4().hex[:10]


def scalar(c, sql, **p):
    with c.cursor() as cur:
        cur.execute(sql, p)
        return cur.fetchone()[0]


@pytest.fixture
def world():
    """A tagged category, supplier, customer, employee and two products; removed afterwards."""
    t = tag()
    ids = {"tag": t}
    with database.connection() as c, c.cursor() as cur:
        ids["cat"] = categories.create({"category_name": t})
        ids["sup"] = suppliers.create({"supplier_name": t})
        ids["cust"] = customers.create({"full_name": t, "email": f"{t.lower()}@example.com", "phone": "9000000000"})
        out = cur.var(int)
        cur.execute("INSERT INTO EMPLOYEES (FULL_NAME, EMAIL, JOB_TITLE, HIRE_DATE) VALUES (:n, :e, 'Tester', SYSDATE) "
                    "RETURNING EMPLOYEE_ID INTO :o", {"n": t, "e": f"{t.lower()}@example.com", "o": out})
        ids["emp"] = out.getvalue()[0]
        c.commit()
    for key, stock, price in (("p1", 10, "100.00"), ("p2", 5, "49.50")):
        ids[key] = products.create({"product_name": f"{t}-{key}", "brand": "T", "model_no": f"{t}-{key}",
                                    "category_id": str(ids["cat"]), "supplier_id": str(ids["sup"]),
                                    "unit_price": price, "stock_qty": str(stock), "reorder_level": "1",
                                    "warranty_months": "1"})
    yield ids
    with database.connection() as c:
        c.clientinfo = "ITEST_CLEANUP"          # lets the trigger allow removing OUR test sales
        with c.cursor() as cur:
            pid = {"a": ids["p1"], "b": ids["p2"]}
            cur.execute("DELETE FROM SALE_ITEMS WHERE PRODUCT_ID IN (:a, :b)", pid)
            cur.execute("DELETE FROM SALES WHERE CUSTOMER_ID = :c", {"c": ids["cust"]})
            cur.execute("DELETE FROM PRODUCTS WHERE PRODUCT_ID IN (:a, :b)", pid)
            cur.execute("DELETE FROM CUSTOMERS WHERE CUSTOMER_ID = :c", {"c": ids["cust"]})
            cur.execute("DELETE FROM EMPLOYEES WHERE EMPLOYEE_ID = :e", {"e": ids["emp"]})
            cur.execute("DELETE FROM SUPPLIERS WHERE SUPPLIER_ID = :s", {"s": ids["sup"]})
            cur.execute("DELETE FROM CATEGORIES WHERE CATEGORY_ID = :c", {"c": ids["cat"]})
        c.commit()


def stock(pid):
    return database.fetch_one("SELECT STOCK_QTY AS s FROM PRODUCTS WHERE PRODUCT_ID = :i", {"i": pid})["s"]


def ora(exc_info):
    return database.ora_code(exc_info.value)


# ---------------------------------------------------------------- connectivity / schema
def test_connection_established_as_application_user(conn):
    """Connect to XEPDB1 as the test application user | connected, user is not SYS/SYSTEM"""
    user = scalar(conn, "SELECT USER FROM DUAL")
    assert user == os.environ["TEST_DB_USER"].upper() and user not in ("SYS", "SYSTEM")
    ok, _ = database.health_check()
    assert ok


def test_schema_has_seven_tables(conn):
    """USER_TABLES | all 7 required tables exist"""
    with conn.cursor() as cur:
        cur.execute("SELECT TABLE_NAME FROM USER_TABLES")
        names = {r[0] for r in cur.fetchall()}
    assert {"CATEGORIES", "SUPPLIERS", "PRODUCTS", "CUSTOMERS", "EMPLOYEES", "SALES", "SALE_ITEMS"} <= names


def test_advanced_objects_exist_and_valid(conn):
    """USER_OBJECTS | view, procedure, function, trigger all VALID"""
    with conn.cursor() as cur:
        cur.execute("SELECT OBJECT_NAME, STATUS FROM USER_OBJECTS WHERE OBJECT_NAME IN "
                    "('V_SALES_SUMMARY','SP_RESTOCK_PRODUCT','FN_CUSTOMER_TOTAL_SPEND','TRG_SALES_PROTECT_HISTORY')")
        rows = dict(cur.fetchall())
    assert len(rows) == 4 and set(rows.values()) == {"VALID"}


# ---------------------------------------------------------------- constraints
def test_check_unique_and_foreign_key_constraints_enforced(conn, world):
    """Negative price/stock, duplicate model, bad category FK | ORA-02290 / ORA-00001 / ORA-02291"""
    base = dict(n="x", m=tag(), c=world["cat"], s=world["sup"])
    sql = ("INSERT INTO PRODUCTS (PRODUCT_NAME, BRAND, MODEL_NO, CATEGORY_ID, SUPPLIER_ID, UNIT_PRICE, STOCK_QTY) "
           "VALUES (:n, 'B', :m, :c, :s, :price, :stock)")
    with conn.cursor() as cur:
        with pytest.raises(oracledb.DatabaseError) as e:
            cur.execute(sql, {**base, "price": -1, "stock": 1})
        assert ora(e) == 2290
        with pytest.raises(oracledb.DatabaseError) as e:
            cur.execute(sql, {**base, "price": 1, "stock": -1})
        assert ora(e) == 2290
        with pytest.raises(oracledb.DatabaseError) as e:
            cur.execute(sql, {**base, "price": 1, "stock": 1, "c": -12345})
        assert ora(e) == 2291
        with pytest.raises(oracledb.DatabaseError) as e:
            cur.execute(sql, {**base, "m": f"{world['tag']}-p1", "price": 1, "stock": 1})
        assert ora(e) == 1


def test_sale_item_line_total_check(conn, world):
    """SALE_ITEMS with LINE_TOTAL != QUANTITY*UNIT_PRICE | ORA-02290"""
    r = sales.create_sale(world["cust"], world["emp"], "CASH", [(world["p1"], 1)])
    with conn.cursor() as cur:
        with pytest.raises(oracledb.DatabaseError) as e:
            cur.execute("INSERT INTO SALE_ITEMS (SALE_ID, PRODUCT_ID, QUANTITY, UNIT_PRICE, LINE_TOTAL) "
                        "VALUES (:s, :p, 2, 10, 5)", {"s": r["sale_id"], "p": world["p2"]})
        assert ora(e) == 2290


def test_restrict_delete_of_referenced_rows(world):
    """Delete category/customer/product that history references | ConflictError (ORA-02292 translated)"""
    with pytest.raises(ConflictError):
        categories.delete(world["cat"])               # products reference it
    sales.create_sale(world["cust"], world["emp"], "CASH", [(world["p1"], 1)])
    with pytest.raises(ConflictError):
        customers.delete(world["cust"])
    with pytest.raises(ConflictError):
        products.delete(world["p1"])


# ---------------------------------------------------------------- CRUD
def test_crud_round_trip():
    """Create, read, update, delete a category and customer through the services | each step reflected in DB"""
    t = tag()
    cid = categories.create({"category_name": t, "description": "d"})
    try:
        assert categories.get(cid)["category_name"] == t
        categories.update(cid, {"category_name": t + "-x"})
        assert categories.get(cid)["category_name"] == t + "-x"
        with pytest.raises(ConflictError):
            categories.create({"category_name": t + "-x"})      # UNIQUE
    finally:
        categories.delete(cid)
    assert database.fetch_one("SELECT 1 AS x FROM CATEGORIES WHERE CATEGORY_ID = :i", {"i": cid}) is None


# ---------------------------------------------------------------- PL/SQL objects
def test_procedure_restock_and_errors(conn, world):
    """SP_RESTOCK_PRODUCT | +5 stock on success; ORA-20001 for 0, ORA-20002 unknown product"""
    products.restock(world["p1"], 5)
    assert stock(world["p1"]) == 15
    with conn.cursor() as cur:
        with pytest.raises(oracledb.DatabaseError) as e:
            cur.callproc("SP_RESTOCK_PRODUCT", [world["p1"], 0])
        assert ora(e) == 20001
        with pytest.raises(oracledb.DatabaseError) as e:
            cur.callproc("SP_RESTOCK_PRODUCT", [-999, 1])
        assert ora(e) == 20002


def test_function_customer_total_spend(conn, world):
    """FN_CUSTOMER_TOTAL_SPEND | 0 before sales, equals sale total after, ORA-20010 for unknown customer"""
    assert scalar(conn, "SELECT FN_CUSTOMER_TOTAL_SPEND(:c) FROM DUAL", c=world["cust"]) == 0
    r = sales.create_sale(world["cust"], world["emp"], "UPI", [(world["p1"], 2), (world["p2"], 1)])
    assert Decimal(str(scalar(conn, "SELECT FN_CUSTOMER_TOTAL_SPEND(:c) FROM DUAL", c=world["cust"]))) == r["total"]
    with conn.cursor() as cur:
        with pytest.raises(oracledb.DatabaseError) as e:
            cur.execute("SELECT FN_CUSTOMER_TOTAL_SPEND(-999) FROM DUAL")
        assert ora(e) == 20010


def test_trigger_blocks_sale_delete_and_update(conn, world):
    """TRG_SALES_PROTECT_HISTORY | DELETE -> ORA-20030, UPDATE total -> ORA-20031"""
    r = sales.create_sale(world["cust"], world["emp"], "CARD", [(world["p2"], 1)])
    with conn.cursor() as cur:
        with pytest.raises(oracledb.DatabaseError) as e:
            cur.execute("DELETE FROM SALES WHERE SALE_ID = :s", {"s": r["sale_id"]})
        assert ora(e) == 20030
        with pytest.raises(oracledb.DatabaseError) as e:
            cur.execute("UPDATE SALES SET TOTAL_AMOUNT = 1 WHERE SALE_ID = :s", {"s": r["sale_id"]})
        assert ora(e) == 20031


def test_view_sales_summary(world):
    """V_SALES_SUMMARY | shows the new sale with correct line/unit counts and TOTAL_MATCHES = 'Y'"""
    r = sales.create_sale(world["cust"], world["emp"], "CASH", [(world["p1"], 2), (world["p2"], 3)])
    row = database.fetch_one("SELECT * FROM V_SALES_SUMMARY WHERE SALE_ID = :s", {"s": r["sale_id"]})
    assert (row["line_count"], row["unit_count"], row["total_matches"]) == (2, 5, "Y")
    assert row["total_amount"] == Decimal("348.50")


# ---------------------------------------------------------------- transactions
def test_multi_item_sale_deducts_stock_and_uses_db_prices(world):
    """Two-item sale | totals from DB prices (2*100.00+3*49.50=348.50), stock 10->8 and 5->2, items stored"""
    r = sales.create_sale(world["cust"], world["emp"], "CASH", [(world["p2"], 3), (world["p1"], 2)])
    assert r["total"] == Decimal("348.50") and r["invoice_no"].startswith("INV-")
    assert (stock(world["p1"]), stock(world["p2"])) == (8, 2)
    detail = sales.get(r["sale_id"])
    assert len(detail["items"]) == 2 and detail["sale"]["total_amount"] == Decimal("348.50")


def test_insufficient_stock_changes_nothing(world):
    """Quantity above stock | InsufficientStockError; no sale row, stock unchanged"""
    before = database.fetch_one("SELECT COUNT(*) AS n FROM SALES WHERE CUSTOMER_ID = :c", {"c": world["cust"]})["n"]
    with pytest.raises(InsufficientStockError):
        sales.create_sale(world["cust"], world["emp"], "CASH", [(world["p1"], 1), (world["p2"], 6)])
    assert stock(world["p1"]) == 10 and stock(world["p2"]) == 5
    assert database.fetch_one("SELECT COUNT(*) AS n FROM SALES WHERE CUSTOMER_ID = :c",
                              {"c": world["cust"]})["n"] == before


def test_invalid_product_rolls_back_whole_sale(world):
    """Valid line + nonexistent product | ValidationError and the valid line's stock is untouched"""
    with pytest.raises(ValidationError):
        sales.create_sale(world["cust"], world["emp"], "CASH", [(world["p1"], 1), (999999999, 1)])
    assert stock(world["p1"]) == 10


def test_row_lock_blocks_concurrent_sale(world, monkeypatch):
    """Another session holds FOR UPDATE on a product | sale waits then fails with ConflictError (ORA-30006), stock intact"""
    monkeypatch.setattr(sales, "LOCK_WAIT_SECONDS", 2)
    holder = database.get_connection()
    try:
        with holder.cursor() as cur:
            cur.execute("SELECT 1 FROM PRODUCTS WHERE PRODUCT_ID = :p FOR UPDATE", {"p": world["p1"]})
        with pytest.raises(ConflictError):
            sales.create_sale(world["cust"], world["emp"], "CASH", [(world["p1"], 1)])
    finally:
        holder.rollback()
        holder.close()
    assert stock(world["p1"]) == 10


def test_concurrent_sales_cannot_oversell(world):
    """8 threads each buy 1 unit of a product with 5 in stock | exactly 5 succeed, 3 InsufficientStockError, final stock 0"""
    results, lock = [], threading.Lock()

    def buy():
        try:
            sales.create_sale(world["cust"], world["emp"], "CASH", [(world["p2"], 1)])
            outcome = "ok"
        except InsufficientStockError:
            outcome = "short"
        except Exception as exc:                      # surfaced in the assertion below
            outcome = repr(exc)
        with lock:
            results.append(outcome)

    threads = [threading.Thread(target=buy) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(results) == ["ok"] * 5 + ["short"] * 3
    assert stock(world["p2"]) == 0


# ---------------------------------------------------------------- Review 3 (needs database/auth.sql loaded)
def test_users_table_and_constraints_enforced(conn, world):
    """USERS table (auth.sql) | role CHECK, lower-case username CHECK and one-account-per-employee UNIQUE enforced (ORA-02290 / ORA-00001)"""
    sql = "INSERT INTO USERS (USERNAME, PASSWORD_HASH, ROLE, EMPLOYEE_ID) VALUES (:u, 'hash', :r, :e)"
    with conn.cursor() as cur:
        with pytest.raises(oracledb.DatabaseError) as e:
            cur.execute(sql, {"u": "itest-user", "r": "ROOT", "e": world["emp"]})
        assert ora(e) == 2290
        with pytest.raises(oracledb.DatabaseError) as e:
            cur.execute(sql, {"u": "ITEST-UPPER", "r": "CASHIER", "e": world["emp"]})
        assert ora(e) == 2290
        cur.execute(sql, {"u": world["tag"].lower(), "r": "CASHIER", "e": world["emp"]})
        with pytest.raises(oracledb.DatabaseError) as e:
            cur.execute(sql, {"u": world["tag"].lower() + "x", "r": "CASHIER", "e": world["emp"]})
        assert ora(e) == 1
    conn.rollback()


def test_user_account_lifecycle_and_hashing(world):
    """Create user, sign in, wrong password, change password, delete | password stored hashed, authenticate works only with the right password"""
    name = world["tag"].lower()
    uid = users.create({"username": name, "role": "CASHIER", "password": "itest-password-1",
                        "password_confirm": "itest-password-1", "employee_id": str(world["emp"])})
    try:
        stored = database.fetch_one("SELECT PASSWORD_HASH AS h FROM USERS WHERE USER_ID = :i", {"i": uid})["h"]
        assert stored != "itest-password-1" and len(stored) > 40
        assert users.authenticate(name, "itest-password-1")["role"] == "CASHIER"
        assert users.authenticate(name, "wrong-password") is None
        users.change_own_password(uid, {"current_password": "itest-password-1", "password": "itest-password-2",
                                        "password_confirm": "itest-password-2"})
        assert users.authenticate(name, "itest-password-1") is None
        assert users.authenticate(name, "itest-password-2") is not None
        with pytest.raises(ConflictError):                       # employee already has an account
            users.create({"username": name + "2", "role": "CASHIER", "password": "itest-password-1",
                          "password_confirm": "itest-password-1", "employee_id": str(world["emp"])})
        with pytest.raises(ConflictError):                       # cannot delete employee that owns an account
            employees.delete(world["emp"])
    finally:
        users.delete(uid, acting_user_id=-1)
    assert users.authenticate(name, "itest-password-2") is None


def test_employee_crud_round_trip():
    """Create, update, delete an employee through the service | each step reflected in the database"""
    t = tag()
    eid = employees.create({"full_name": t, "email": f"{t.lower()}@example.com", "job_title": "Tester", "hire_date": "2024-01-15"})
    try:
        assert employees.get(eid)["job_title"] == "Tester"
        employees.update(eid, {"full_name": t, "email": f"{t.lower()}@example.com", "job_title": "Lead Tester", "hire_date": "2024-01-15"})
        assert employees.get(eid)["job_title"] == "Lead Tester"
    finally:
        employees.delete(eid)
    assert database.fetch_one("SELECT 1 AS x FROM EMPLOYEES WHERE EMPLOYEE_ID = :i", {"i": eid}) is None
