"""Employee records (Review 3: full CRUD; referenced by sales and user accounts)."""
import datetime

from . import database as db, validation as v
from .errors import NotFoundError, ValidationError


def list_page(q, page_no):
    where, params = "", {}
    if q:
        where = " WHERE UPPER(FULL_NAME) LIKE :q OR UPPER(EMAIL) LIKE :q OR UPPER(JOB_TITLE) LIKE :q"
        params = {"q": f"%{q.upper()}%"}
    return db.fetch_page("EMPLOYEE_ID, FULL_NAME, EMAIL, PHONE, JOB_TITLE, HIRE_DATE", "EMPLOYEES",
                         where, params, "FULL_NAME", page_no)


def list_all():
    return db.fetch_all("SELECT EMPLOYEE_ID, FULL_NAME, JOB_TITLE FROM EMPLOYEES ORDER BY FULL_NAME")


def list_without_user():
    """Employees that do not yet have a login (candidates for a new user account)."""
    return db.fetch_all("SELECT e.EMPLOYEE_ID, e.FULL_NAME, e.JOB_TITLE FROM EMPLOYEES e WHERE NOT EXISTS "
                        "(SELECT 1 FROM USERS u WHERE u.EMPLOYEE_ID = e.EMPLOYEE_ID) ORDER BY e.FULL_NAME")


def get(employee_id):
    row = db.fetch_one("SELECT EMPLOYEE_ID, FULL_NAME, EMAIL, PHONE, JOB_TITLE, HIRE_DATE FROM EMPLOYEES "
                       "WHERE EMPLOYEE_ID = :id", {"id": v.record_id(employee_id)})
    if not row:
        raise NotFoundError("Employee not found.")
    return row


def _fields(form):
    try:
        hired = datetime.date.fromisoformat((form.get("hire_date") or "").strip())
    except ValueError:
        raise ValidationError("Hire date must be a valid date (YYYY-MM-DD).") from None
    if hired > datetime.date.today():
        raise ValidationError("Hire date cannot be in the future.")
    return {"name": v.text(form, "full_name", "Full name", 100), "email": v.email(form),
            "phone": v.phone(form, required=False), "title": v.text(form, "job_title", "Job title", 60),
            "hired": hired}


def create(form):
    return db.insert_returning(
        "INSERT INTO EMPLOYEES (FULL_NAME, EMAIL, PHONE, JOB_TITLE, HIRE_DATE) "
        "VALUES (:name, :email, :phone, :title, :hired) RETURNING EMPLOYEE_ID INTO :new_id", _fields(form))


def update(employee_id, form):
    params = {**_fields(form), "id": v.record_id(employee_id)}
    if not db.execute("UPDATE EMPLOYEES SET FULL_NAME = :name, EMAIL = :email, PHONE = :phone, "
                      "JOB_TITLE = :title, HIRE_DATE = :hired WHERE EMPLOYEE_ID = :id", params):
        raise NotFoundError("Employee not found.")


def delete(employee_id):
    if not db.execute("DELETE FROM EMPLOYEES WHERE EMPLOYEE_ID = :id", {"id": v.record_id(employee_id)}):
        raise NotFoundError("Employee not found.")
