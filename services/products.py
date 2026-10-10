from . import database as db, validation as v
from .errors import NotFoundError

_SELECT = ("p.PRODUCT_ID, p.PRODUCT_NAME, p.BRAND, p.MODEL_NO, p.CATEGORY_ID, c.CATEGORY_NAME, "
           "p.SUPPLIER_ID, s.SUPPLIER_NAME, p.UNIT_PRICE, p.STOCK_QTY, p.REORDER_LEVEL, p.WARRANTY_MONTHS")
_SOURCE = ("PRODUCTS p JOIN CATEGORIES c ON c.CATEGORY_ID = p.CATEGORY_ID "
           "JOIN SUPPLIERS s ON s.SUPPLIER_ID = p.SUPPLIER_ID")


def list_page(q, category_id, low_stock, page_no):
    clauses, params = [], {}
    if q:
        clauses.append("(UPPER(p.PRODUCT_NAME) LIKE :q OR UPPER(p.BRAND) LIKE :q OR UPPER(p.MODEL_NO) LIKE :q)")
        params["q"] = f"%{q.upper()}%"
    if category_id:
        clauses.append("p.CATEGORY_ID = :category_id")
        params["category_id"] = v.record_id(category_id, "Category")
    if low_stock:
        clauses.append("p.STOCK_QTY <= p.REORDER_LEVEL")
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    return db.fetch_page(_SELECT, _SOURCE, where, params, "p.PRODUCT_NAME", page_no)


def list_for_sale():
    return db.fetch_all("SELECT PRODUCT_ID, PRODUCT_NAME, MODEL_NO, UNIT_PRICE, STOCK_QTY FROM PRODUCTS "
                        "WHERE STOCK_QTY > 0 ORDER BY PRODUCT_NAME")


def get(product_id):
    row = db.fetch_one(f"SELECT {_SELECT} FROM {_SOURCE} WHERE p.PRODUCT_ID = :id",
                       {"id": v.record_id(product_id)})
    if not row:
        raise NotFoundError("Product not found.")
    return row


def _fields(form):
    return {"name": v.text(form, "product_name", "Product name", 120),
            "brand": v.text(form, "brand", "Brand", 60),
            "model_no": v.text(form, "model_no", "Model number", 40),
            "category_id": v.record_id(form.get("category_id"), "Category"),
            "supplier_id": v.record_id(form.get("supplier_id"), "Supplier"),
            "price": v.money(form.get("unit_price"), "Unit price"),
            "stock": v.integer(form.get("stock_qty"), "Stock quantity", 0, 99_999_999),
            "reorder": v.integer(form.get("reorder_level"), "Reorder level", 0, 999_999),
            "warranty": v.integer(form.get("warranty_months"), "Warranty months", 0, 120)}


def create(form):
    return db.insert_returning(
        "INSERT INTO PRODUCTS (PRODUCT_NAME, BRAND, MODEL_NO, CATEGORY_ID, SUPPLIER_ID, UNIT_PRICE, "
        "STOCK_QTY, REORDER_LEVEL, WARRANTY_MONTHS) VALUES (:name, :brand, :model_no, :category_id, "
        ":supplier_id, :price, :stock, :reorder, :warranty) RETURNING PRODUCT_ID INTO :new_id", _fields(form))


def update(product_id, form):
    params = {**_fields(form), "id": v.record_id(product_id)}
    if not db.execute(
            "UPDATE PRODUCTS SET PRODUCT_NAME = :name, BRAND = :brand, MODEL_NO = :model_no, "
            "CATEGORY_ID = :category_id, SUPPLIER_ID = :supplier_id, UNIT_PRICE = :price, STOCK_QTY = :stock, "
            "REORDER_LEVEL = :reorder, WARRANTY_MONTHS = :warranty WHERE PRODUCT_ID = :id", params):
        raise NotFoundError("Product not found.")


def delete(product_id):
    if not db.execute("DELETE FROM PRODUCTS WHERE PRODUCT_ID = :id", {"id": v.record_id(product_id)}):
        raise NotFoundError("Product not found.")


def restock(product_id, quantity):
    """Add received stock via the SP_RESTOCK_PRODUCT stored procedure (one transaction)."""
    pid = v.record_id(product_id, "Product")
    qty = v.integer(quantity, "Restock quantity", 1, 1_000_000)
    try:
        with db.connection() as conn:
            with conn.cursor() as cur:
                cur.callproc("SP_RESTOCK_PRODUCT", [pid, qty])
            conn.commit()
    except db.oracledb.Error as exc:
        raise db.translate(exc) from None
