"""Command-line user management (no default accounts exist).

    python manage.py create-user USERNAME ROLE EMPLOYEE_EMAIL
    python manage.py list-users

Example (first manager):
    python manage.py create-user meera MANAGER meera.nair@applstore-demo.example.com
The password is typed at a hidden prompt and stored only as a hash.
"""
import getpass
import sys

from dotenv import load_dotenv

from services import database, users
from services.errors import AppError


def main(argv):
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
    print(__doc__)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except AppError as exc:
        print(f"FAILED: {exc}")
        sys.exit(1)
