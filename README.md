# Electronic Appliance Store Management System

DBMS Review 2 project by **Sanjiv Shine Fernandas** — Flask + Oracle Database 21c XE (`XEPDB1`), python-oracledb in Thin mode, vanilla HTML/CSS/JS.

> **Status honesty note:** the code, SQL scripts and unit tests were produced and checked in a sandbox that had **no Oracle database**. The SQL was statically parsed and the Python was unit-tested with fakes, but **nothing has yet been executed against a real Oracle instance**. Section 9 and `docs/Review_2_Report.md` list exactly which checks you must run locally.

## 1. Features

- **Review 3:** login with two roles (Manager, Cashier), employee management, user-account management, deployable with `waitress` (see §8a and `docs/deployment.md`).

- Seven normalized tables: `CATEGORIES, SUPPLIERS, PRODUCTS, CUSTOMERS, EMPLOYEES, SALES, SALE_ITEMS` with PK/FK/UNIQUE/NOT NULL/CHECK constraints and indexes.
- CRUD for products, categories, suppliers, customers (search, filter, pagination, delete confirmation).
- **Atomic sales**: row locks (`SELECT … FOR UPDATE WAIT`), stock re-check, sale + items + stock deduction in one transaction, rollback on any error; prices always read from the database.
- Sales history, sale detail, dashboard and five reports (inventory, monthly revenue, top sellers, category revenue, customer spend).
- Oracle objects: view `V_SALES_SUMMARY`, procedure `SP_RESTOCK_PRODUCT`, function `FN_CUSTOMER_TOTAL_SPEND`, trigger `TRG_SALES_PROTECT_HISTORY`.
- Security: bind variables everywhere, CSRF tokens, escaped output, CSP header, least-privilege DB user, sanitized errors.

## 2. Architecture and layout

```
Browser ── HTML/CSS/JS ──► Flask routes (app.py) ──► services/*.py ──► python-oracledb (Thin) ──► Oracle XEPDB1
```

```
app.py  config.py  requirements.txt  .env.example  .gitignore  CLAUDE.md
database/   setup_user.sql (admin, once)  schema.sql  advanced_features.sql  seed.sql  queries.sql
services/   database.py (connection+errors)  validation.py  products.py  categories.py  suppliers.py
            customers.py  employees.py  sales.py (transaction)  reports.py  errors.py
templates/  base, dashboard, products, categories, suppliers, customers, sale_new, sales, sale_detail, reports, error
static/     css/style.css  js/app.js
tests/      test_config  test_services  test_routes  test_oracle_integration (live)
docs/       Review_2_Report.{md,docx,pdf}  Review_2_Presentation.pptx  demo_guide.md  images/
            build_reports.py  build_presentation.py  make_diagrams.py
```

## 3. Prerequisites (Windows 10/11)

- Python 3.11 or newer — <https://www.python.org/downloads/> (tick *Add python.exe to PATH*).
- Oracle Database 21c Express Edition (installs SQL*Plus). Pluggable database `XEPDB1` is created by the installer.
- Git (optional).

All commands below are **Windows PowerShell**, run from the project folder, unless marked *(sqlplus)*.

## 4. Verify Oracle is running

```powershell
Get-Service Oracle*                  # OracleServiceXE and OracleOraDB21Home1TNSListener must be "Running"
Start-Service OracleServiceXE        # only if stopped (run PowerShell as Administrator)
Start-Service OracleOraDB21Home1TNSListener
lsnrctl status                       # the service list must contain XEPDB1
```

Service names can differ slightly (`OracleOraDB21Home1TNSListener` is the XE default). If `sqlplus`/`lsnrctl` are "not recognized", use the full path under `C:\app\<you>\product\21c\dbhomeXE\bin`.

## 5. One-time database account creation (administrator)

Run once as an administrator. The script switches to `XEPDB1`, asks for a password (hidden — it is never stored in a file) and grants only `CREATE SESSION/TABLE/SEQUENCE/VIEW/PROCEDURE/TRIGGER`. No DBA rights.

```powershell
sqlplus / as sysdba
```
```sql
-- (sqlplus)
@database\setup_user.sql
EXIT
```

Verify the account can log in to the pluggable DB (you will be prompted for the password):

```powershell
sqlplus appliance_app@localhost:1521/XEPDB1
```

## 6. Python environment and configuration

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1          # if blocked:  Set-ExecutionPolicy -Scope Process Bypass
python -m pip install -r requirements.txt

copy .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"   # paste result as FLASK_SECRET_KEY
notepad .env                                               # set DB_PASSWORD and FLASK_SECRET_KEY
```

`.env` is git-ignored — **never commit it**. Any password that was previously shared or committed anywhere must be considered compromised: change it (`ALTER USER appliance_app IDENTIFIED BY "new";` as admin) and use the new one only in `.env`.

Connectivity check (prints OK/FAILED; never prints secrets):

```powershell
python -m services.database
```

## 7. Load the database (order matters)

```powershell
sqlplus appliance_app@localhost:1521/XEPDB1 @database\schema.sql
sqlplus appliance_app@localhost:1521/XEPDB1 @database\advanced_features.sql
sqlplus appliance_app@localhost:1521/XEPDB1 @database\seed.sql
sqlplus appliance_app@localhost:1521/XEPDB1 @database\auth.sql           # Review 3: USERS table (run after schema.sql)
sqlplus appliance_app@localhost:1521/XEPDB1 @database\queries.sql     # optional: runs the 16 demo queries
```

- `schema.sql` and `seed.sql` are **safe to re-run**: they skip existing objects (only ORA-00955 is tolerated) and `MERGE` seed rows by natural key. Nothing is dropped.
- `seed.sql` first-run row counts: 6 categories, 4 suppliers, 14 products, 8 customers, 4 employees, 8 sales, 15 sale items.
- There is intentionally **no destructive reset script**. To start over, drop the objects yourself in your own schema (`DROP TABLE SALE_ITEMS; …`) or recreate the user.

## 8a. Login and roles (Review 3)

The app now requires sign-in. There are **no default accounts or passwords**. After loading `auth.sql` (§7), create the first manager from the project folder (Command Prompt, virtual environment active). The password is typed at a hidden prompt and stored only as a hash:

```bat
python manage.py create-user meera MANAGER meera.nair@applstore-demo.example.com
python manage.py list-users
python manage.py reset-password meera     # forgotten password: prompts twice, hidden
```

The e-mail must belong to an existing employee (the seed has `Meera Nair`, Store Manager). Then sign in at <http://127.0.0.1:5000/login>. Managers create further accounts under **User accounts** and employees under **Employees**.

| Area | Manager | Cashier |
|---|---|---|
| New sale, sales history, sale detail | yes | yes (sold-by is always the signed-in employee) |
| Products | full CRUD + restock | view only |
| Customers | full CRUD | list, add, edit (no delete) |
| Dashboard, reports | yes | no (HTTP 403) |
| Categories, suppliers | full CRUD | no |
| Employees, user accounts | full CRUD | no |
| Change own password | yes | yes |

Rules: every page except `/login` and `/health` requires sign-in (default deny); 5 failed sign-ins for a user within 5 minutes are blocked for a while (HTTP 429); sessions last 8 hours; sign-out is a POST; passwords need at least 10 characters; manager accounts cannot be deleted in the app (only cashier accounts can; a database administrator can remove a manager with SQL, see `docs/deployment.md`), which also means you can never delete your own account or the last manager.

## 8. Run the application

```powershell
python app.py
```
Open <http://127.0.0.1:5000> (redirects to the sign-in page). Health endpoint: <http://127.0.0.1:5000/health> (status only: 503 + `database: unavailable` when Oracle cannot be reached, `ok` only after a real round trip; the reason is in the server log, and `python -m services.database` prints details locally).

Production-style run (waitress, no debug): `python serve.py` -> <http://127.0.0.1:8000>. Set `APP_ENV=production` only when served over HTTPS (it turns on secure-only cookies, so sign-in would not work over plain http). Full guide: `docs/deployment.md`.

## 9. Tests

```powershell
python -m pytest tests -v                      # unit + route + auth tests (no Oracle needed); live tests show as BLOCKED unless enabled below
```

Live Oracle integration tests need a **separate test schema** (never your populated demo schema). Create it with `setup_user.sql` (answer `appliance_test` at the first prompt), load `schema.sql` and `advanced_features.sql` into it, then:

```powershell
$env:RUN_ORACLE_TESTS="1"
$env:TEST_DB_HOST="localhost"; $env:TEST_DB_PORT="1521"; $env:TEST_DB_SERVICE_NAME="XEPDB1"
$env:TEST_DB_USER="appliance_test"; $env:TEST_DB_PASSWORD=(Read-Host "test password")
python -m pytest tests\test_oracle_integration.py -v
```

The tests create rows tagged `ITEST-…` and delete only those. Test status meanings: **PASSED** executed and passed · **FAILED** executed and failed · **NOT RUN** skipped on purpose · **BLOCKED** missing dependency (e.g. no Oracle).

Regenerate the report files after a test run: `python -m pytest tests --junitxml=docs/test_results.xml` then `python docs\build_reports.py`.

## 10. Faculty demonstration

Follow `docs/demo_guide.md` (10-minute script with SQL to paste).

## 11. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `DPY-6005` / "database is unavailable" | Listener or `OracleServiceXE` stopped → section 4. Check `DB_HOST/DB_PORT`. |
| `ORA-12514` listener does not know service | `DB_SERVICE_NAME` must be `XEPDB1` (not `XE`). `lsnrctl status`. |
| `ORA-01017` invalid username/password | Fix `DB_PASSWORD` in `.env`; user must be created in **XEPDB1**, not the root container. |
| `ORA-01950` no privileges on tablespace | Re-run `setup_user.sql` (grants `QUOTA UNLIMITED ON USERS`). |
| `ORA-00942` table or view does not exist | Scripts not loaded as `appliance_app`, or run order wrong (section 7). |
| Sales pages fail with `ORA-00942`, or Restock fails with `PLS-00201` | `advanced_features.sql` not loaded (history uses view `V_SALES_SUMMARY`; restock calls `SP_RESTOCK_PRODUCT`). |
| "Missing database configuration: …" | `.env` missing or still contains `<set-locally>` placeholders. |
| "Security token missing or invalid" (400) | Session expired or cookies blocked → reload the page. |
| `Activate.ps1 cannot be loaded` | `Set-ExecutionPolicy -Scope Process Bypass`. |
| `ORA-00942` on `USERS` / sign-in fails with a database error | `auth.sql` not loaded (§7). |
| Cannot sign in; no accounts exist | Create the first manager with `python manage.py create-user` (§8a). |
| Sign-in loops back to the login page with `APP_ENV=production` over http | Secure cookies need HTTPS; use `APP_ENV=development` for a local http demo. |
| `ORA-20999` "Run this script as the application user…" | `schema.sql`/`seed.sql`/`auth.sql`/`advanced_features.sql` were run as SYS/SYSTEM or in `CDB$ROOT`. Run them as `appliance_app` in `XEPDB1` (§7). |
| Port 5000 in use | Stop the other process or edit the port at the bottom of `app.py`. |
| `ORA-30006` resource busy during a sale | Another session holds the product row lock; retry. |

## 12. Security precautions

Never commit `.env`; run `git status` before each commit. The app uses only `appliance_app` (config rejects SYS/SYSTEM). SQL uses bind variables only; state changes are POST + CSRF token; templates auto-escape; CSP forbids inline scripts. Error pages hide ORA codes, SQL and credentials (details go to the server log).

## 13. Known limitations

- Login/roles are basic: two fixed roles, no self-registration, no password-reset e-mail (a manager resets passwords in the app, or an administrator runs `manage.py reset-password`), no multi-factor sign-in. Role and account changes take effect at the next sign-in (sessions last 8 hours). The login throttle is in-process (single server process, unbounded memory, not proxy-aware); see `docs/Review_3_Notes.md` for the deferred follow-up.
- Single-currency (₹) display; no returns/refunds, no tax or discount model; employees are seed-only (no CRUD screen).
- `TRG_SALES_PROTECT_HISTORY` contains a documented `CLIENT_INFO = 'ITEST_CLEANUP'` bypass used only by integration tests in a test schema — remove it for a production-style deployment.
- Header total vs. line totals consistency is enforced by the service (and reported by the view), not by a database constraint.
- The `LIKE` search treats `%`/`_` typed by users as wildcards.
- Not verified on a live Oracle instance in the authoring environment (see note at top).
