from . import database as db, validation as v
from .errors import NotFoundError


def list_all(q=None):
    sql = ("SELECT s.SUPPLIER_ID, s.SUPPLIER_NAME, s.CONTACT_PERSON, s.EMAIL, s.PHONE, s.ADDRESS, "
           "COUNT(p.PRODUCT_ID) AS PRODUCT_COUNT FROM SUPPLIERS s "
           "LEFT JOIN PRODUCTS p ON p.SUPPLIER_ID = s.SUPPLIER_ID")
    params = {}
    if q:
        sql += " WHERE UPPER(s.SUPPLIER_NAME) LIKE :q OR UPPER(s.CONTACT_PERSON) LIKE :q"
        params["q"] = f"%{q.upper()}%"
    return db.fetch_all(sql + " GROUP BY s.SUPPLIER_ID, s.SUPPLIER_NAME, s.CONTACT_PERSON, s.EMAIL, "
                              "s.PHONE, s.ADDRESS ORDER BY s.SUPPLIER_NAME", params)


def get(supplier_id):
    row = db.fetch_one("SELECT SUPPLIER_ID, SUPPLIER_NAME, CONTACT_PERSON, EMAIL, PHONE, ADDRESS "
                       "FROM SUPPLIERS WHERE SUPPLIER_ID = :id", {"id": v.record_id(supplier_id)})
    if not row:
        raise NotFoundError("Supplier not found.")
    return row


def _fields(form):
    return {"name": v.text(form, "supplier_name", "Supplier name", 100),
            "contact": v.text(form, "contact_person", "Contact person", 100, required=False),
            "email": v.email(form, required=False),
            "phone": v.phone(form, required=False),
            "address": v.text(form, "address", "Address", 255, required=False)}


def create(form):
    return db.insert_returning(
        "INSERT INTO SUPPLIERS (SUPPLIER_NAME, CONTACT_PERSON, EMAIL, PHONE, ADDRESS) "
        "VALUES (:name, :contact, :email, :phone, :address) RETURNING SUPPLIER_ID INTO :new_id", _fields(form))


def update(supplier_id, form):
    params = {**_fields(form), "id": v.record_id(supplier_id)}
    if not db.execute("UPDATE SUPPLIERS SET SUPPLIER_NAME = :name, CONTACT_PERSON = :contact, EMAIL = :email, "
                      "PHONE = :phone, ADDRESS = :address WHERE SUPPLIER_ID = :id", params):
        raise NotFoundError("Supplier not found.")


def delete(supplier_id):
    if not db.execute("DELETE FROM SUPPLIERS WHERE SUPPLIER_ID = :id", {"id": v.record_id(supplier_id)}):
        raise NotFoundError("Supplier not found.")
