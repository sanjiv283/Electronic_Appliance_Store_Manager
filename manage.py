"""Command-line user management (no default accounts exist).

    python manage.py create-user USERNAME ROLE EMPLOYEE_EMAIL
    python manage.py list-users
    python manage.py reset-password USERNAME

Example (first manager):
    python manage.py create-user meera MANAGER meera.nair@applstore-demo.example.com
The password is typed at a hidden prompt and stored only as a hash.
"""
import getpass
import sys

from dotenv import load_dotenv

from config import ConfigError
from services import database, users
from services.errors import AppError


def _run(argv):
    load_dotenv()
    if len(argv) >= 2 and argv[1] == "list-users":
        for u in users.list_all():
            print(f"{u['username']:<20} {u['role']:<8} {u['full_name']}")
        return 0
    if len(argv) == 5 and argv[1] == "create-user":
        _, _, username, role, email = argv
        employee = database.fetch_one("SELECT EMPLOYEE_ID FROM EMPLOYEES WHERE EMAIL = :e", {"e": email})
        if not employee:
            print(f"No employee with e-mail {email}. Add the employee first.")
            return 1
        password = getpass.getpass("Password (min 10 characters): ")
        users.create({"username": username, "role": role, "password": password,
                      "password_confirm": getpass.getpass("Repeat password: "),
                      "employee_id": str(employee["employee_id"])})
        print(f"Created {role} user '{username.lower()}'.")
        return 0
    if len(argv) == 3 and argv[1] == "reset-password":
        user = database.fetch_one("SELECT USER_ID FROM USERS WHERE USERNAME = :u", {"u": argv[2].strip().lower()})
        if not user:
            print(f"No user named '{argv[2]}'.")
            return 1
        users.reset_password(user["user_id"], {"password": getpass.getpass("New password (min 10 characters): "),
                                               "password_confirm": getpass.getpass("Repeat password: ")})
        print(f"Password changed for '{argv[2].strip().lower()}'.")
        return 0
    print(__doc__)
    return 2


def main(argv):
    try:
        return _run(argv)
    except (AppError, ConfigError) as exc:      # e.g. .env missing: a clear message, not a traceback
        print(f"FAILED: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
