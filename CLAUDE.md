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

## Test results (verified)
- Offline (sandbox, Python 3.13, fake DB): 141 passed, 19 skipped (live).
- Live on the student's Oracle 21c XE (separate `appliance_test` schema, 2026-10-22): 19/19 integration tests passed; all 16 queries ran on `appliance_app` without error. First live run was 18/19 - the failure was a test bug (bind named like a helper arg), fixed in PR #6.
- Live-run results in docs/test_results*.xml are transcribed from the student's console output (stated in the reports).
- Not verified: recorded browser walkthrough of every role, HTTPS deployment, throttle across processes.

## Theme (cyberpunk)
`static/css/style.css`, `static/js/theme-init.js` (applies saved theme pre-paint, try/catch), `static/js/app.js`, `templates/base.html` (sidebar + toggle). CSP is `default-src 'self'` -> NO inline `style=`/`<script>` in templates.

## Review 3 (merged into main)
Auth: `database/auth.sql` (USERS, 8th table, run after schema/advanced/seed), `services/users.py` (scrypt hashes, no default accounts), `manage.py create-user | list-users | reset-password`, default-deny gate in `app.py` (`PUBLIC_ENDPOINTS`, `CASHIER_ENDPOINTS`), in-process login throttle, 8h sessions, status-only `/health`. Managers cannot be deleted in the UI. Employees CRUD, user accounts page. Deploy: `serve.py` (waitress), `docs/deployment.md`. Criteria map: `docs/Review_3_Notes.md`.
When adding a route: decide manager-only (default) or add to CASHIER_ENDPOINTS; test_auth enumerates all routes. Ids from Oracle are Decimal - cast to int before comparing/storing in the session.
SQL scripts refuse to run as SYS/SYSTEM or in CDB$ROOT (ORA-20999); `setup_user.sql` uses SET VERIFY OFF.

## Deliverables (docs/)
Review 2: `Review_2_Report.md` (source) -> `python docs/build_reports.py` -> .docx/.pdf; `python docs/build_presentation.py` -> .pptx. Review 3: `Review_3_Report.md` -> `python docs/build_review3.py`; `python docs/build_presentation_r3.py`. Matrix/deck numbers come from `docs/test_results.xml` (Review 2, gitignored) and `docs/test_results_r3.xml`. `python docs/make_diagrams.py` -> er_diagram.png, architecture.png. UI screenshots are real templates with stubbed data except ui_db_unavailable.png.

## Git workflow
Never push directly to `main`; branch + PR. PR #1 (fix/theme-polish) merged into main on the student's instruction. No force-push or history rewrite.

## Remaining / optional
Login-throttle redesign (bounded/shared store, ProxyFix), HTTPS deployment, remove trigger test bypass for production, rotate any DB password ever shared, drop `appliance_test` users when finished.
