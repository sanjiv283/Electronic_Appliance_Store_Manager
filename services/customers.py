from . import database as db, validation as v
from .errors import NotFoundError


def list_page(q, page_no):
    where, params = "", {}
    if q:
        where = " WHERE UPPER(FULL_NAME) LIKE :q OR UPPER(EMAIL) LIKE :q OR PHONE LIKE :q"
        params = {"q": f"%{q.upper()}%"}
    return db.fetch_page("CUSTOMER_ID, FULL_NAME, EMAIL, PHONE, ADDRESS", "CUSTOMERS", where, params,
                         "FULL_NAME", page_no)


def list_all():
    return db.fetch_all("SELECT CUSTOMER_ID, FULL_NAME FROM CUSTOMERS ORDER BY FULL_NAME")


def get(customer_id):
    row = db.fetch_one("SELECT CUSTOMER_ID, FULL_NAME, EMAIL, PHONE, ADDRESS FROM CUSTOMERS "
                       "WHERE CUSTOMER_ID = :id", {"id": v.record_id(customer_id)})
    if not row:
        raise NotFoundError("Customer not found.")
    return row


def _fields(form):
    return {"name": v.text(form, "full_name", "Full name", 100), "email": v.email(form),
            "phone": v.phone(form), "address": v.text(form, "address", "Address", 255, required=False)}


def create(form):
    return db.insert_returning(
        "INSERT INTO CUSTOMERS (FULL_NAME, EMAIL, PHONE, ADDRESS) VALUES (:name, :email, :phone, :address) "
        "RETURNING CUSTOMER_ID INTO :new_id", _fields(form))


def update(customer_id, form):
    params = {**_fields(form), "id": v.record_id(customer_id)}
    if not db.execute("UPDATE CUSTOMERS SET FULL_NAME = :name, EMAIL = :email, PHONE = :phone, "
                      "ADDRESS = :address WHERE CUSTOMER_ID = :id", params):
        raise NotFoundError("Customer not found.")


def delete(customer_id):
    if not db.execute("DELETE FROM CUSTOMERS WHERE CUSTOMER_ID = :id", {"id": v.record_id(customer_id)}):
        raise NotFoundError("Customer not found.")
