# Review 3 Demonstration Guide (about 12 minutes)

Presenter: Sanjiv Shine Fernandas · Subject: DBMS · Review 3 (final web application)

**Legend:** 🔌 = needs the live Oracle database. 📄 = shown from files or slides only.

Be honest on the day: only claim what you actually show. The live Oracle results in the report (19/19 integration tests, 16/16 queries, 2026-10-22) are from your own earlier run; today's demo shows the running application.

## Before you start (do this 10 minutes earlier)

1. Oracle running: `Get-Service Oracle*` shows OracleServiceXE and the listener as Running.
2. Project on `main` and up to date: `git checkout main` then `git pull`.
3. In PowerShell from the project folder: `.\.venv\Scripts\python.exe -m services.database` must print `OK: Connected as APPLIANCE_APP ...`.
4. Make sure nothing else is using port 5000 (close old app windows).
5. Start the app: `.\.venv\Scripts\python.exe app.py` and open <http://127.0.0.1:5000>.
6. Have a **cashier** account ready. If none exists, sign in as a manager, open **User accounts**, and create one for the employee *Karan Shetty* (username `karan`, role CASHIER, a password of at least 10 characters that you remember).
7. Open **two browser windows**: a normal one for the manager and a private/incognito one for the cashier.
8. Keep a SQL*Plus window open as `appliance_app` (`sqlplus appliance_app@localhost:1521/XEPDB1`, password typed at the prompt).
9. Never show `.env`, never type a password where the audience can read the screen, and do not demonstrate the lockout with a real username (use `ghost`).

If Oracle is unreachable on the day: show the slides and the report, run `python -m pytest tests -q` (155 passed, 19 skipped), open `/health` (it will say `unavailable`), and say clearly that the live screens were not demonstrated.

## Time plan

| Min | Section | Type |
|---|---|---|
| 0:00–1:00 | 1. What Review 3 adds (slides 1–3) | 📄 |
| 1:00–2:30 | 2. Sign-in and the manager view | 🔌 |
| 2:30–4:00 | 3. Roles: cashier view and access denied | 🔌 |
| 4:00–5:30 | 4. Employees and user accounts | 🔌 |
| 5:30–7:30 | 5. Sale transaction, stock and invoice | 🔌 |
| 7:30–8:30 | 6. Database proof in SQL*Plus | 🔌 |
| 8:30–9:30 | 7. Security: lockout, health, passwords | 🔌 |
| 9:30–10:30 | 8. Testing evidence | 📄 / 🔌 |
| 10:30–12:00 | 9. Limitations and questions | — |

## 1. What Review 3 adds (1:00) 📄

Open `docs/Review_3_Presentation.pptx`, slides 1–3. Say: Review 2 was the database and backend; Review 3 completes the application with **sign-in, two roles, employee and account management, hardening and deployment**. The browser never talks to Oracle; routes call services, and services own all SQL with bind variables.

## 2. Sign-in and the manager view (1:30) 🔌

1. Browser window 1 → <http://127.0.0.1:5000>. You are sent to the **login page** (default deny: every page except `/login` and `/health` needs sign-in).
2. Sign in as your manager account. You land on the **dashboard** (manager landing page).
3. Point out the sidebar: Products, Categories, Suppliers, Customers, Employees, User accounts, Sales, Reports.
4. Open **Reports** for a moment (monthly revenue, top sellers). Say these come from the 16 queries and the `V_SALES_SUMMARY` view.

Say: passwords are never stored, only an scrypt hash; there are no default accounts, the first manager is created from the server with `manage.py`.

## 3. Roles: cashier view and access denied (1:30) 🔌

1. Browser window 2 (private) → sign in as the cashier (`karan`). You land on **New sale**, not the dashboard.
2. Show the sidebar: only Products, Customers, New sale, Sales. Open **Products**: view only, no Add/Delete.
3. In the address bar type `http://127.0.0.1:5000/reports` → **403 Forbidden** page. Try `/users` → 403 as well.
4. Say: access is **default deny**. A cashier may use only a short list of pages (`CASHIER_ENDPOINTS`); a test goes through every route to prove it.

## 4. Employees and user accounts (1:30) 🔌

Back in the manager window:

1. **Employees**: add a demo employee, edit it, then delete it. Try to delete an employee who has sales (for example *Asha Menon*): you get a clear **409** message, because foreign keys are RESTRICT and sales history must not disappear.
2. **User accounts**:
   - Your own row says **you**, and manager rows say **protected**; only cashiers have a Delete button.
   - Say: managers cannot be deleted in the app, so nobody can delete themselves or the last manager. (If asked, a database administrator can do it with SQL; see `docs/deployment.md`.)
   - Optional: reset a cashier's password (hidden fields, minimum 10 characters).

## 5. Sale transaction, stock and invoice (2:00) 🔌

1. In the **cashier** window → **New sale**. Choose a customer, payment method, and add two lines, for example 2 × *Aurora Electric Kettle 1.8L* and 1 × *KitchenPro Mixer Grinder 750W*. Note the stock figures first (Products page).
2. Submit. The **invoice page** opens. Point out: invoice number from a sequence, prices taken **from the database** (not from the browser), and **Sold by = the signed-in cashier** (the employee cannot be chosen or forged).
3. Check **Products**: both stocks fell by exactly the quantities sold.
4. Try an oversized sale: 5 × *CoolBreeze 1.0 Ton Window AC* (stock is 2). You get **409 insufficient stock** and nothing changes.
5. Say: the whole sale is one transaction. Product rows are locked in a fixed order with `SELECT ... FOR UPDATE`, stock is re-checked, the sale and its items are inserted, stock is deducted **once in the service (never in a trigger)** and committed once; any error rolls everything back. The live tests proved this, including 8 simultaneous buyers of 5 units giving exactly 5 sales.

Note: demo sales stay in the database as history (a trigger forbids deleting or editing sales). That is intended.

## 6. Database proof in SQL*Plus (1:00) 🔌

```sql
SELECT table_name FROM user_tables ORDER BY 1;                 -- 8 tables, USERS is the new one
SELECT username, role, employee_id FROM USERS ORDER BY 1;      -- no password column shown
SELECT SUBSTR(password_hash, 1, 14) AS hash_start FROM USERS FETCH FIRST 1 ROWS ONLY;   -- hashed, not readable
SELECT invoice_no, customer_name, total_amount FROM V_SALES_SUMMARY ORDER BY sale_date DESC FETCH FIRST 3 ROWS ONLY;
```
Say: `USERS` has `CK_USERS_ROLE` (MANAGER or CASHIER only), a unique lower-case username and one login per employee (`UQ_USERS_EMPLOYEE`). Do not print whole hashes on screen.

## 7. Security (1:00) 🔌

1. **Lockout:** log out, then on the login page enter username `ghost` with a wrong password six times. The sixth attempt shows "Too many failed sign-in attempts" (HTTP 429); the PowerShell window running the app logs the block. Say: 5 failures per user and address, 20 per address, memory is bounded, and it is proxy-aware through `TRUSTED_PROXIES`.
2. **Health:** open <http://127.0.0.1:5000/health>: only `{"app":"ok","database":"ok"}`. No database user or service name is exposed.
3. Mention: CSRF token on every POST, escaped output, CSP header, open-redirect protection on `next=`, bind variables only, least-privilege database account.

## 8. Testing evidence (1:00) 📄 / 🔌

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q        # expect: 155 passed, 19 skipped
```
Say: the 19 skipped are the live Oracle tests; they passed 19 of 19 on my Oracle 21c XE on 2026-10-22 (first run 18/19: one mistake in the test itself, fixed). Open the Review 3 report, section 12 (matrix) and slide 9. Also mention the real bug found by hand-testing: Oracle returned ids as `Decimal`, which broke the "cannot delete yourself" check until it was fixed with regression tests.

## 9. Limitations and likely questions (1:30)

**State these yourself:** the throttle is per process (resets on restart, not shared between several workers); no self-registration, no password-reset e-mail, no MFA; role changes take effect at next sign-in (sessions last 8 hours); HTTPS and a deployment behind a reverse proxy were designed and documented (`docs/deployment.md`) but not run; no load testing; the trigger has a test-cleanup bypass that should be removed in production.

| Question | Short answer |
|---|---|
| Why can a cashier not open `/reports`? | Default deny. Only listed pages are allowed for cashiers; everything else is manager-only, and a test covers every route. |
| How are passwords stored? | scrypt hash with a salt (Werkzeug). The password is never stored or logged. |
| What if two cashiers sell the last unit? | Row lock plus stock re-check inside one transaction; the second waits and then gets an insufficient-stock error. |
| Why is stock not reduced in a trigger? | One deduction point in the service keeps the logic testable and avoids double deduction. |
| What is in the 8th table? | `USERS`: username, hashed password, role, and a unique link to an employee. |
| What did you not verify? | Browser walkthrough for every role as a recorded test, HTTPS, several workers, load. |

## After the demo

- Stop the app with Ctrl+C.
- If you created a demo cashier or employee only for today, delete it in the app.
- Rotate the `appliance_app` password if it was ever shown or pasted anywhere, and update `.env`.
