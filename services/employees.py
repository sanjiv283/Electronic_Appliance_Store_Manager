"""Employees are seeded and read-only in the UI; they are referenced by sales."""
from . import database as db


def list_all():
    return db.fetch_all("SELECT EMPLOYEE_ID, FULL_NAME, JOB_TITLE FROM EMPLOYEES ORDER BY FULL_NAME")
