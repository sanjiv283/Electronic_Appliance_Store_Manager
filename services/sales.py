"""Sales processing: one atomic transaction covering sale, items and stock."""
from decimal import Decimal

from . import database as db, validation as v
from .errors import InsufficientStockError, ValidationError

PAYMENT_METHODS = ("CASH", "CARD", "UPI", "BANK_TRANSFER")
MAX_LINES = 50
MAX_QTY = 1000
LOCK_WAIT_SECONDS = 10      # row-lock wait; tests lower it

_LOCK_SQL = ("SELECT PRODUCT_ID, PRODUCT_NAME, UNIT_PRICE, STOCK_QTY FROM PRODUCTS "
             "WHERE PRODUCT_ID = :pid FOR UPDATE WAIT ")   # + int constant, appended at call time


def parse_items(product_ids, quantities):
    """Turn parallel form lists into [(product_id, qty)], merging duplicate products.

    Returns items sorted by product id - the fixed lock order that prevents deadlocks.
    """
    if len(product_ids) != len(quantities):
        raise ValidationError("Each sale line needs a product and a quantity.")
    merged = {}
    for raw_id, raw_qty in zip(product_ids, quantities):
        if not (raw_id or "").strip() and not (raw_qty or "").strip():
            continue                                        # blank row left in the form
        pid = v.record_id(raw_id, "Product")
        qty = v.integer(raw_qty, "Quantity", 1, MAX_QTY)
        merged[pid] = merged.get(pid, 0) + qty
    if not merged:
        raise ValidationError("A sale needs at least one product.")
    if len(merged) > MAX_LINES or any(q > MAX_QTY for q in merged.values()):
        raise ValidationError(f"A sale can have at most {MAX_LINES} products and {MAX_QTY} units of each.")
    return sorted(merged.items())


def create_sale(customer_id, employee_id, payment_method, items):
    """Create a sale atomically. Client prices/totals are never accepted.

    items: output of parse_items. Steps: validate refs -> lock products in id
    order (FOR UPDATE WAIT) -> re-check stock -> insert sale + items -> deduct
    stock -> commit. Any failure rolls the whole transaction back.
    """
    cid = v.record_id(customer_id, "Customer")
    eid = v.record_id(employee_id, "Employee")
    if payment_method not in PAYMENT_METHODS:
        raise ValidationError("Payment method must be one of: " + ", ".join(PAYMENT_METHODS) + ".")
    if not items:
        raise ValidationError("A sale needs at least one product.")
    items = sorted(items)
    try:
        with db.connection() as conn:               # closes connection; rolls back on error
            with conn.cursor() as cur:
                for table, col, value, label in (("CUSTOMERS", "CUSTOMER_ID", cid, "customer"),
                                                 ("EMPLOYEES", "EMPLOYEE_ID", eid, "employee")):
                    cur.execute(f"SELECT 1 FROM {table} WHERE {col} = :id", {"id": value})
                    if cur.fetchone() is None:
                        raise ValidationError(f"The selected {label} does not exist.")

                locked = {}
                for pid, _qty in items:             # ascending id order, row locks held until commit
                    cur.execute(_LOCK_SQL + str(int(LOCK_WAIT_SECONDS)), {"pid": pid})
                    row = cur.fetchone()
                    if row is None:
                        raise ValidationError(f"Product {pid} does not exist.")
                    locked[pid] = row

                shortages = [f"{locked[pid][1]} (requested {qty}, available {locked[pid][3]})"
                             for pid, qty in items if locked[pid][3] < qty]
                if shortages:
                    raise InsufficientStockError("Insufficient stock for: " + "; ".join(shortages) + ".")

                lines = [(pid, qty, Decimal(str(locked[pid][2])),
                          Decimal(str(locked[pid][2])) * qty) for pid, qty in items]
                total = sum((line[3] for line in lines), Decimal("0")).quantize(Decimal("0.01"))

                sale_id, invoice = cur.var(int), cur.var(str)
                cur.execute(
                    "INSERT INTO SALES (INVOICE_NO, CUSTOMER_ID, EMPLOYEE_ID, PAYMENT_METHOD, TOTAL_AMOUNT) "
                    "VALUES ('INV-' || LPAD(TO_CHAR(SEQ_INVOICE_NO.NEXTVAL), 6, '0'), :cid, :eid, :pay, :total) "
                    "RETURNING SALE_ID, INVOICE_NO INTO :sale_id, :invoice_no",
                    {"cid": cid, "eid": eid, "pay": payment_method, "total": total,
                     "sale_id": sale_id, "invoice_no": invoice})
                new_id = sale_id.getvalue()[0]
                if isinstance(new_id, list):
                    new_id = new_id[0]

                for pid, qty, price, line_total in lines:
                    cur.execute("INSERT INTO SALE_ITEMS (SALE_ID, PRODUCT_ID, QUANTITY, UNIT_PRICE, LINE_TOTAL) "
                                "VALUES (:sid, :pid, :qty, :price, :line_total)",
                                {"sid": new_id, "pid": pid, "qty": qty, "price": price, "line_total": line_total})
                    cur.execute("UPDATE PRODUCTS SET STOCK_QTY = STOCK_QTY - :qty WHERE PRODUCT_ID = :pid",
                                {"qty": qty, "pid": pid})     # the ONLY place stock is deducted
            conn.commit()
            return {"sale_id": new_id, "invoice_no": invoice.getvalue()[0], "total": total}
    except db.oracledb.Error as exc:
        raise db.translate(exc) from None


def list_page(q, page_no):
    where, params = "", {}
    if q:
        where = " WHERE UPPER(INVOICE_NO) LIKE :q OR UPPER(CUSTOMER_NAME) LIKE :q OR UPPER(EMPLOYEE_NAME) LIKE :q"
        params = {"q": f"%{q.upper()}%"}
    return db.fetch_page("SALE_ID, INVOICE_NO, SALE_DATE, PAYMENT_METHOD, CUSTOMER_NAME, EMPLOYEE_NAME, "
                         "LINE_COUNT, UNIT_COUNT, TOTAL_AMOUNT", "V_SALES_SUMMARY", where, params,
                         "SALE_DATE DESC, SALE_ID DESC", page_no)


def get(sale_id):
    from .errors import NotFoundError
    sid = v.record_id(sale_id, "Sale")
    header = db.fetch_one("SELECT SALE_ID, INVOICE_NO, SALE_DATE, PAYMENT_METHOD, CUSTOMER_ID, CUSTOMER_NAME, "
                          "EMPLOYEE_NAME, TOTAL_AMOUNT, TOTAL_MATCHES FROM V_SALES_SUMMARY WHERE SALE_ID = :id",
                          {"id": sid})
    if not header:
        raise NotFoundError("Sale not found.")
    items = db.fetch_all("SELECT p.PRODUCT_NAME, p.MODEL_NO, si.QUANTITY, si.UNIT_PRICE, si.LINE_TOTAL "
                         "FROM SALE_ITEMS si JOIN PRODUCTS p ON p.PRODUCT_ID = si.PRODUCT_ID "
                         "WHERE si.SALE_ID = :id ORDER BY p.PRODUCT_NAME", {"id": sid})
    return {"sale": header, "items": items}
