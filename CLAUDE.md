# CLAUDE.md - project memory

## Objective
Electronic Appliance Store Management System - DBMS Review 2 (Sanjiv Shine Fernandas).
Flask + python-oracledb (Thin) + Oracle 21c XE (service `XEPDB1`, user/schema `appliance_app`), vanilla HTML/CSS/JS, pytest.

## Architecture
Browser -> Flask routes (`app.py`) -> services (`services/*.py`, own all SQL) -> `services/database.py` -> Oracle.
`config.py` = env-only config. Routes never touch SQL. Stock is deducted ONLY in `services/sales.create_sale` (never in a trigger).

## Repository structure
`app.py config.py requirements.txt .env.example .gitignore` · `database/` (setup_user, schema, advanced_features, seed, queries) ·
`services/` · `templates/` · `static/` · `tests/` · `docs/` (Review_2_Report.md/.docx/.pdf, demo_guide.md, build_reports.py).

## Schema (7 tables, all FKs RESTRICT, identity PKs)
CATEGORIES 1-N PRODUCTS N-1 SUPPLIERS; CUSTOMERS 1-N SALES N-1 EMPLOYEES; SALES 1-N SALE_ITEMS N-1 PRODUCTS.
Extras: SEQ_INVOICE_NO, view V_SALES_SUMMARY, proc SP_RESTOCK_PRODUCT, func FN_CUSTOMER_TOTAL_SPEND, trigger TRG_SALES_PROTECT_HISTORY (test-cleanup bypass via CLIENT_INFO='ITEST_CLEANUP').
queries.sql = exactly 16 numbered queries.

## Conventions
Upper-case Oracle identifiers; bind variables only; Decimal for money; services raise `services.errors.AppError` subclasses with user-safe text; DB details only in server log; seed.sql was generated (totals computed) - edit with care.

## Security rules
Never print/commit secrets (`.env` is ignored). App connects only as appliance_app (config rejects SYS/SYSTEM). Admin SQL only in `database/setup_user.sql`, run manually. No commit/push/history rewrite without the user's authorization. Previously used DB passwords are compromised - rotate.

## Commands (PowerShell, Windows)
`py -3.11 -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt`
`python -m services.database` (connectivity) · `python -m pytest tests -v` · `python app.py` -> http://127.0.0.1:5000
Live tests: set RUN_ORACLE_TESTS=1 + TEST_DB_* (README section 9). Reports: pytest --junitxml=docs/test_results.xml; python docs\build_reports.py

## Completed phases (1-7)
Audit (repo was empty) -> DB scripts -> backend/services -> frontend -> tests -> docs + DOCX/PDF -> final audit.

## Actual test results (sandbox: Linux, Python 3.13, NO Oracle)
- pytest: 76 PASSED (unit/route, fake DB), 16 BLOCKED (live Oracle integration), 0 FAILED.
- compileall PASSED; node --check app.js PASSED; sqlglot Oracle-dialect parse of 16 queries + 7 seed MERGEs PASSED (syntax only).
- Flask smoke: /health 503 + honest message without Oracle; POST without CSRF 400.
- Mutation sanity: removing lock-order sort / adding mid-sale commit made tests fail.

## Known blockers
No Oracle in sandbox: schema.sql, seed.sql, queries.sql, advanced_features.sql (PL/SQL) and all INT tests are unexecuted. Student must run README sections 5-9 locally.

## Current state / remaining
All deliverables exist; changes are UNCOMMITTED (no commit/push authorized). Remaining: run live Oracle steps, then regenerate report matrix (build_reports.py), then commit when the user authorizes. Optional: remove trigger bypass, add auth, employee CRUD.
