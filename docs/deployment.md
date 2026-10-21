# Deployment guide (Review 3)

Target: a Windows machine in the store (or a lab PC) with Oracle Database 21c XE already installed.

## 1. One-time setup
1. Oracle: create the application user once with `database\setup_user.sql`; then load, as `appliance_app`, in this order: `schema.sql`, `advanced_features.sql`, `auth.sql`, and (demo data only) `seed.sql`.
2. Python 3.11+: `py -3.11 -m venv .venv`, `.venv\Scripts\activate.bat`, `python -m pip install -r requirements.txt`.
3. Configuration: `copy .env.example .env`, then edit `.env` — set `DB_PASSWORD` and a long random `FLASK_SECRET_KEY`
   (`python -c "import secrets; print(secrets.token_hex(32))"`). `.env` is git-ignored; never commit or e-mail it.
4. First manager: `python manage.py create-user <username> MANAGER <employee e-mail>` (hidden password prompt).
5. Check: `python -m services.database` must print `OK: Connected as APPLIANCE_APP ...`.

## 2. Run
| Purpose | Command | URL |
|---|---|---|
| Development (auto-reload with `FLASK_DEBUG=1`) | `python app.py` | http://127.0.0.1:5000 |
| Production-style (waitress, 8 threads, no debug) | `python serve.py` | http://127.0.0.1:8000 (`HOST`/`PORT` in `.env`) |

`serve.py` listens on `127.0.0.1` by default. To let other store PCs connect, set `HOST=0.0.0.0` **and** put HTTPS in front (section 3); do not expose plain http on a network.

## 3. HTTPS and production settings
- `APP_ENV=production` turns on `Secure` cookies and disables debug. Browsers then send the session cookie only over HTTPS, so enable it **only** when the app is reached through HTTPS.
- Recommended: run `serve.py` on localhost and terminate TLS in a reverse proxy (IIS with URL Rewrite/ARR, Caddy or nginx) that forwards to `http://127.0.0.1:8000`. Obtain a certificate from your organisation or an ACME CA; self-signed certificates are fine for a lab demo.
- Start `serve.py` at boot with Task Scheduler ("Run whether user is logged on or not", action: `.venv\Scripts\python.exe serve.py`, start in the project folder) or a service wrapper such as NSSM.
- Keep Oracle (port 1521) reachable only from the application server.

## 4. Operations
- Health: `GET /health` -> 200 `{"database":"ok"}` or 503 (monitor this URL).
- Logs: application errors go to the console/stderr of `serve.py` (no passwords or SQL are shown to users).
- Backups: use Oracle Data Pump (`expdp`) or RMAN on the `XEPDB1` schema regularly; test a restore.
- Accounts: managers manage users in the web UI; `python manage.py list-users` lists accounts. If every manager password is lost, create a new manager with `manage.py` (needs `.env` access on the server).
- Password rotation: change the Oracle password with `ALTER USER appliance_app IDENTIFIED BY "..."` (as admin, in `XEPDB1`) and update `.env`; restart `serve.py`.

## 5. Known limits of this deployment
Single server process (login throttle is in memory), no connection pool, no automatic TLS, session role changes apply at next sign-in. These are acceptable for a single-store deployment and are listed in the README.
