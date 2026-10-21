"""Application users, password hashing and role data (Review 3)."""
import re

from werkzeug.security import check_password_hash, generate_password_hash

from . import database as db, validation as v
from .errors import ConflictError, NotFoundError, ValidationError

ROLES = ("MANAGER", "CASHIER")
MIN_PASSWORD = 10
_USERNAME = re.compile(r"^[a-z0-9][a-z0-9._-]{2,39}$")
# Compared against when the username does not exist, so timing does not reveal valid names.
_DUMMY_HASH = generate_password_hash("not-a-real-password")


def check_password_rules(password, username=""):
    if not password or len(password) < MIN_PASSWORD:
        raise ValidationError(f"Password must be at least {MIN_PASSWORD} characters.")
    if len(password) > 128:
        raise ValidationError("Password must be at most 128 characters.")
    if username and password.lower() == username.lower():
        raise ValidationError("Password must not be the same as the username.")


def authenticate(username, password):
    """Return the session user dict for valid credentials, else None."""
    row = db.fetch_one(
        "SELECT u.USER_ID, u.USERNAME, u.PASSWORD_HASH, u.ROLE, u.EMPLOYEE_ID, e.FULL_NAME "
        "FROM USERS u JOIN EMPLOYEES e ON e.EMPLOYEE_ID = u.EMPLOYEE_ID WHERE u.USERNAME = :u",
        {"u": (username or "").strip().lower()})
    ok = check_password_hash(row["password_hash"] if row else _DUMMY_HASH, password or "")
    if not row or not ok:
        return None
    db.execute("UPDATE USERS SET LAST_LOGIN = SYSTIMESTAMP WHERE USER_ID = :id", {"id": row["user_id"]})
    # Oracle returns NUMBER ids as Decimal, which the session cookie turns into text ("3"); keep plain ints
    # so comparisons such as "is this my own account?" keep working.
    return {"id": int(row["user_id"]), "username": row["username"], "role": row["role"],
            "employee_id": int(row["employee_id"]), "name": row["full_name"]}


def list_all():
    return db.fetch_all("SELECT u.USER_ID, u.USERNAME, u.ROLE, e.FULL_NAME, e.JOB_TITLE, u.LAST_LOGIN "
                        "FROM USERS u JOIN EMPLOYEES e ON e.EMPLOYEE_ID = u.EMPLOYEE_ID ORDER BY u.USERNAME")


def create(form):
    username = (form.get("username") or "").strip().lower()
    if not _USERNAME.match(username):
        raise ValidationError("Username must be 3-40 characters: lower-case letters, digits, '.', '_' or '-'.")
    role = (form.get("role") or "").upper()
    if role not in ROLES:
        raise ValidationError("Role must be MANAGER or CASHIER.")
    password = form.get("password") or ""
    if password != (form.get("password_confirm") or ""):
        raise ValidationError("The two passwords do not match.")
    check_password_rules(password, username)
    return db.insert_returning(
        "INSERT INTO USERS (USERNAME, PASSWORD_HASH, ROLE, EMPLOYEE_ID) VALUES (:u, :h, :r, :e) "
        "RETURNING USER_ID INTO :new_id",
        {"u": username, "h": generate_password_hash(password), "r": role,
         "e": v.record_id(form.get("employee_id"), "Employee")})


def reset_password(user_id, form):
    uid = v.record_id(user_id, "User")
    row = db.fetch_one("SELECT USERNAME FROM USERS WHERE USER_ID = :id", {"id": uid})
    if not row:
        raise NotFoundError("User not found.")
    password = form.get("password") or ""
    if password != (form.get("password_confirm") or ""):
        raise ValidationError("The two passwords do not match.")
    check_password_rules(password, row["username"])
    db.execute("UPDATE USERS SET PASSWORD_HASH = :h WHERE USER_ID = :id",
               {"h": generate_password_hash(password), "id": uid})


def change_own_password(user_id, form):
    row = db.fetch_one("SELECT USERNAME, PASSWORD_HASH FROM USERS WHERE USER_ID = :id", {"id": user_id})
    if not row or not check_password_hash(row["password_hash"], form.get("current_password") or ""):
        raise ValidationError("Current password is incorrect.")
    reset_password(user_id, form)


def delete(user_id, acting_user_id):
    uid = v.record_id(user_id, "User")
    if uid == int(acting_user_id):
        raise ConflictError("You cannot delete your own account.")
    row = db.fetch_one("SELECT ROLE FROM USERS WHERE USER_ID = :id", {"id": uid})
    if not row:
        raise NotFoundError("User not found.")
    if row["role"] == "MANAGER" and \
            db.fetch_one("SELECT COUNT(*) AS n FROM USERS WHERE ROLE = 'MANAGER'")["n"] <= 1:
        raise ConflictError("The last manager account cannot be deleted.")
    db.execute("DELETE FROM USERS WHERE USER_ID = :id", {"id": uid})
