# Review 3 — final web application: where each criterion is implemented

Status legend: **verified offline** = unit/route tests with a fake database (126 passed); **needs live Oracle** = written, tests exist, not yet run against a real database.

| Criterion | Implementation | Evidence / how to demonstrate | Status |
|---|---|---|---|
| Completion of all proposed functionalities | CRUD for products, categories, suppliers, customers, **employees**, **user accounts**; sales, restock, reports, dashboard | Sidebar pages; `app.py` routes | Offline-verified; live needs Oracle |
| Frontend–backend–database integration | Jinja forms -> Flask routes -> `services/*` -> python-oracledb -> Oracle; sale transaction with row locks | `README` §8; `docs/demo_guide.md` | Connectivity verified on student machine; rest needs live Oracle |
| User interface and usability | Cyberpunk theme (dark/light), responsive layout, role-filtered navigation, confirmations, clear errors, empty states | Browser; screenshots in `docs/images/r3_*.png` (sample data) | Rendered in Chromium |
| Authentication and role-based access | `/login`, `/logout`, `services/users.py` (scrypt hashes), `database/auth.sql` (USERS), Manager/Cashier roles, default-deny gate in `app.py`, login throttle, 8-hour sessions, change/reset password, `manage.py` bootstrap | `tests/test_auth.py` (every route requires login; role matrix; throttle; open-redirect; hashing) | Offline-verified |
| Database correctness and data integrity | 8 tables, PK/FK/UNIQUE/CHECK, no-cascade FKs, trigger protecting sales, atomic sale transaction, USERS role/username CHECKs | `schema.sql`, `auth.sql`, integration tests `INT-*` | Schema loaded on student machine; constraints need live tests |
| Search, filtering, reports, dashboard | Search/filter/pagination on products, customers, employees, sales; dashboard; 5 reports | Pages `/products?q=`, `/sales?q=`, `/reports` | Offline-verified; live needs Oracle |
| Error handling and basic security | Bind variables, CSRF on every POST, escaped output, CSP, safe error pages (400/401/403/404/409/429/503), hashed passwords, least-privilege DB user, default-deny access control | `tests/test_routes.py`, `tests/test_auth.py` | Offline-verified |
| Testing and demonstration | pytest suites (unit, route, auth, live-Oracle) + `docs/demo_guide.md` | `python -m pytest tests -v` | 126 passed, 19 blocked (live Oracle) |
| Project documentation | `README.md`, `docs/deployment.md`, `docs/demo_guide.md`, Review 2 report/deck, this file | — | Review 3 report (.md/.docx/.pdf) and deck (.pptx) generated |

## Role matrix
| | Manager | Cashier |
|---|---|---|
| Sales (new, history, detail) | yes | yes — sold-by = signed-in employee |
| Products | CRUD + restock | view |
| Customers | CRUD | list, add, edit |
| Dashboard, reports, categories, suppliers, employees, user accounts | yes | no (403) |

## Security notes (honest limits)
No self-registration or password-reset e-mail; no MFA; throttle is per process (bounded, proxy-aware via TRUSTED_PROXIES); role changes apply at next sign-in; HTTPS must be provided by the deployment (see `docs/deployment.md`).

## Security hardening patch (fix/review-3-hardening)
- **Open redirect fixed:** after sign-in, `next=` accepts only same-site paths; control characters (tab, CR, LF, DEL) and backslashes are rejected (a tab used to turn `/<TAB>/evil.example` into the external `//evil.example`; a newline caused a 500).
- **`manage.py` errors:** a missing database configuration now prints `FAILED: ...` and exits with status 1 instead of a traceback.
- **`/health` is status-only:** it returns `{"app":"ok","database":"ok"|"unavailable"}` with HTTP 200/503 and no database user, service name, host or error text, for everyone. The reason for a failure is written to the server log; `python -m services.database` prints full diagnostics locally.

## Login throttle (redesigned in fix/login-throttle)
`services/throttle.py` (`LoginThrottle`), used by `/login`:
- **Two sliding-window limits:** 5 failures per (username, client address) and 20 failures per client address across all usernames (stops one address spraying many usernames). A different address is never affected, so nobody can lock a user out from elsewhere.
- **Bounded memory:** at most 10,000 entries; expired entries are dropped, then the oldest-updated first. Thread-safe (waitress runs 8 threads).
- **Client address behind a proxy:** `TRUSTED_PROXIES=<n>` in `.env` (0-5, default 0) wraps the app in Werkzeug `ProxyFix(x_for=n)`; with 0, `X-Forwarded-For` is ignored so it cannot be spoofed. Set it to the exact number of reverse proxies in front of the app.
- **HTTP 429** now carries a `Retry-After` header (seconds); blocked attempts are written to the server log (username truncated, address, wait).
- Tests: `tests/test_throttle.py` (fake clock: lockout and Retry-After, isolation by address/user, address-wide cap, expiry, bounded size, header handling, setting validation).

Remaining limits: state is per process (resets on restart, not shared between several workers; for multiple workers use a shared store such as an Oracle table), no progressive delay, and the address-wide limit can block a whole office behind one NAT address for up to 5 minutes after 20 failures.
