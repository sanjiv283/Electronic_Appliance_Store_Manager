from . import database as db, validation as v
from .errors import NotFoundError


def list_all(q=None):
    sql = ("SELECT c.CATEGORY_ID, c.CATEGORY_NAME, c.DESCRIPTION, COUNT(p.PRODUCT_ID) AS PRODUCT_COUNT "
           "FROM CATEGORIES c LEFT JOIN PRODUCTS p ON p.CATEGORY_ID = c.CATEGORY_ID")
    params = {}
    if q:
        sql += " WHERE UPPER(c.CATEGORY_NAME) LIKE :q"
        params["q"] = f"%{q.upper()}%"
    return db.fetch_all(sql + " GROUP BY c.CATEGORY_ID, c.CATEGORY_NAME, c.DESCRIPTION ORDER BY c.CATEGORY_NAME", params)


def get(category_id):
    row = db.fetch_one("SELECT CATEGORY_ID, CATEGORY_NAME, DESCRIPTION FROM CATEGORIES WHERE CATEGORY_ID = :id",
                       {"id": v.record_id(category_id)})
    if not row:
        raise NotFoundError("Category not found.")
    return row


def _fields(form):
    return {"name": v.text(form, "category_name", "Category name", 60),
            "description": v.text(form, "description", "Description", 255, required=False)}


def create(form):
    return db.insert_returning(
        "INSERT INTO CATEGORIES (CATEGORY_NAME, DESCRIPTION) VALUES (:name, :description) "
        "RETURNING CATEGORY_ID INTO :new_id", _fields(form))


def update(category_id, form):
    params = {**_fields(form), "id": v.record_id(category_id)}
    if not db.execute("UPDATE CATEGORIES SET CATEGORY_NAME = :name, DESCRIPTION = :description "
                      "WHERE CATEGORY_ID = :id", params):
        raise NotFoundError("Category not found.")


def delete(category_id):
    if not db.execute("DELETE FROM CATEGORIES WHERE CATEGORY_ID = :id", {"id": v.record_id(category_id)}):
        raise NotFoundError("Category not found.")
