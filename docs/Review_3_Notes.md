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
| Project documentation | `README.md`, `docs/deployment.md`, `docs/demo_guide.md`, Review 2 report/deck, this file | — | Review 3 report/deck not generated yet |

## Role matrix
| | Manager | Cashier |
|---|---|---|
| Sales (new, history, detail) | yes | yes — sold-by = signed-in employee |
| Products | CRUD + restock | view |
| Customers | CRUD | list, add, edit |
| Dashboard, reports, categories, suppliers, employees, user accounts | yes | no (403) |

## Security notes (honest limits)
No self-registration or password-reset e-mail; no MFA; throttle is per process; role changes apply at next sign-in; HTTPS must be provided by the deployment (see `docs/deployment.md`).
