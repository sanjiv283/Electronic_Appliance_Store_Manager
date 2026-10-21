"""Build docs/Review_3_Presentation.pptx (11 slides). Reuses the helpers/theme of build_presentation.py.

    python docs/build_presentation_r3.py     # test numbers are read from docs/test_results_r3.xml
"""
import os
import xml.etree.ElementTree as ET

_here = os.path.dirname(os.path.abspath(__file__))
_src = open(os.path.join(_here, "build_presentation.py"), encoding="utf-8").read()
_src = _src.split("# ---------------------------------------------------------------- 1 title")[0]
exec(compile(_src.replace("DBMS Review 2", "DBMS Review 3"), "build_presentation_helpers", "exec"))
total_slides = 11


def tally3():
    t, per = {"PASSED": 0, "FAILED": 0, "SKIPPED": 0}, {}
    for case in ET.parse(os.path.join(ROOT, "docs", "test_results_r3.xml")).getroot().iter("testcase"):
        mod, st = case.get("classname").split(".")[-1], "PASSED"
        for ch in case:
            st = "FAILED" if ch.tag in ("failure", "error") else ("SKIPPED" if ch.tag == "skipped" else st)
        t[st] += 1
        per.setdefault(mod, {}).setdefault(st, 0)
        per[mod][st] += 1
    return t, per


def pic(slide, name, x, y, w):
    slide.shapes.add_picture(os.path.join(IMG, name), Inches(x), Inches(y), width=Inches(w))


def table(slide, rows, x, y, w, h, widths, size=13):
    tb = slide.shapes.add_table(len(rows), len(rows[0]), Inches(x), Inches(y), Inches(w), Inches(h)).table
    for ci, cw in enumerate(widths):
        tb.columns[ci].width = Inches(cw)
    for ri, r in enumerate(rows):
        for ci, v in enumerate(r):
            c = tb.cell(ri, ci); c.fill.solid()
            c.fill.fore_color.rgb = C["cyan"] if ri == 0 else (C["panel"] if ri % 2 else C["panel2"])
            c.text = v; run = c.text_frame.paragraphs[0].runs[0]
            run.font.size, run.font.name, run.font.bold = Pt(size), SANS, ri == 0
            run.font.color.rgb = C["bg"] if ri == 0 else C["text"]


# 1 title
s = prs.slides.add_slide(BLANK)
s.background.fill.solid(); s.background.fill.fore_color.rgb = C["bg"]
for i, col in enumerate(("cyan", "mag")):
    r = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Inches(2.2 + i * 0.07), prs.slide_width, Inches(0.04))
    r.fill.solid(); r.fill.fore_color.rgb = C[col]; r.line.fill.background()
text(s, 0.9, 0.7, 11, 0.5, "DATABASE MANAGEMENT SYSTEMS · REVIEW 3", 16, "cyan", True)
text(s, 0.9, 2.5, 11.6, 1.6, ["Electronic Appliance", "Store Management System"], 48, "text", True)
text(s, 0.9, 4.3, 11.6, 0.5, "Final web application: login, roles, management screens, deployment", 22, "muted")
text(s, 0.9, 5.2, 8, 1.2, ["Sanjiv Shine Fernandas", "Subject: Database Management Systems (DBMS)"], 20, "text")
text(s, 8.2, 5.2, 4.4, 1.3, ["Oracle Database 21c XE · XEPDB1", "Flask · python-oracledb (Thin)", "waitress · pytest"], 15, "cyan", font=MONO)
text(s, 0.9, 6.9, 11, 0.3, "github.com/sanjiv283/Electronic_Appliance_Store_Manager", 12, "muted")
notes(s, "Review 2 delivered the database and backend. Review 3 completes the application: authentication, roles, employee and account management, hardening and deployment.")

# 2 what is new
s = new_slide(2, "What Review 3 adds", "On top of the Review 2 schema, queries, PL/SQL objects and atomic sales")
bullets(s, 0.6, 1.5, 6.0, 5.2, [
    "Sign-in with two roles: Manager and Cashier",
    "Default-deny access: every page needs sign-in except /login and /health",
    "Employee management and user-account management (managers)",
    "Sale 'sold by' is always the signed-in employee",
    "Change own password; scrypt password hashes",
    "8th table USERS in a separate script (auth.sql)"], 17, gap=8)
bullets(s, 6.8, 1.5, 6.0, 5.2, [
    "Security hardening: open-redirect fix, status-only /health, clean CLI errors",
    "Bug found in manual testing: Oracle Decimal ids broke the 'cannot delete yourself' check — fixed with tests",
    "Production-style launcher (waitress) and deployment guide",
    "Manager accounts cannot be deleted in the app",
    "Live Oracle: 19/19 integration tests and 16/16 queries passed"], 17, gap=8)
notes(s, "Mention that the Decimal bug was caught by the student during manual use, after offline tests passed — evidence that live testing matters.")

# 3 architecture
s = new_slide(3, "Architecture and request flow", "Routes call services; services own all SQL")
flow = ["Browser", "Flask routes\nlogin gate · CSRF · roles", "services/*.py\nall SQL, bind variables", "python-oracledb (Thin)", "Oracle XEPDB1\n8 tables"]
for i, lab in enumerate(flow):
    x = 0.6 + i * 2.5
    box(s, x, 1.7, 2.2, 1.3, "panel", "cyan" if i % 2 == 0 else "mag")
    text(s, x, 1.75, 2.2, 1.2, lab.split("\n"), 14, "text", True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    if i < 4:
        line(s, x + 2.2, 2.35, x + 2.5, 2.35, "amber", 2.5)
bullets(s, 0.6, 3.5, 12.1, 3.2, [
    "Stock is deducted in exactly one place (services/sales.create_sale), never in a trigger",
    "App connects only as appliance_app; configuration comes from environment variables only (.env, git-ignored)",
    "A before_request gate enforces sign-in; CASHIER_ENDPOINTS lists what cashiers may open; everything else is manager-only",
    "A test enumerates every registered route, so a new page cannot ship without an access decision"], 16, gap=8)
notes(s, "Walk the flow left to right; stress that the browser never talks to Oracle and routes contain no SQL.")

# 4 roles
s = new_slide(4, "Roles and permissions")
table(s, [("Area", "Manager", "Cashier"),
          ("New sale, sales history, sale detail", "yes", "yes (sold-by = signed-in employee)"),
          ("Products", "full CRUD + restock", "view only"),
          ("Customers", "full CRUD", "list, add, edit"),
          ("Dashboard and reports", "yes", "no (HTTP 403)"),
          ("Categories and suppliers", "full CRUD", "no (HTTP 403)"),
          ("Employees and user accounts", "full CRUD (managers protected)", "no (HTTP 403)"),
          ("Change own password", "yes", "yes")], 0.6, 1.5, 12.15, 4.2, (4.4, 3.6, 4.15), 14)
text(s, 0.6, 6.0, 12.1, 0.8, "Sessions last 8 hours. 5 failed sign-ins in 5 minutes return HTTP 429. Role changes apply at next sign-in.", 14, "muted")
notes(s, "Show a cashier login and a 403 on a manager page.")

# 5 database
s = new_slide(5, "Database: the USERS table", "auth.sql runs after schema.sql · 8 tables in total")
table(s, [("Column", "Rule"),
          ("USER_ID", "identity primary key"),
          ("USERNAME", "unique, CHECK lower-case"),
          ("PASSWORD_HASH", "scrypt hash, never the password"),
          ("ROLE", "CHECK IN ('MANAGER','CASHIER')"),
          ("EMPLOYEE_ID", "UNIQUE foreign key to EMPLOYEES (one login per employee)"),
          ("CREATED_AT, LAST_LOGIN", "timestamps")], 0.6, 1.6, 7.4, 3.6, (2.6, 4.8), 14)
bullets(s, 8.3, 1.6, 4.5, 4.5, [
    "Load order: schema → advanced_features → seed → auth",
    "No default accounts: the first manager is created with manage.py",
    "Live test INT-17 proves the CHECK and UNIQUE rules on Oracle"], 15, gap=10)
notes(s, "Passwords are never stored; only the hash.")

# 6 screenshots 1
s = new_slide(6, "Sign-in and user accounts", "Real templates, sample data (not live records)")
pic(s, "r3_login.png", 0.6, 1.5, 6.0)
pic(s, "r3_users.png", 6.75, 1.5, 6.0)
text(s, 0.6, 5.0, 6, 0.3, "Sign-in page", 12, "muted", True)
text(s, 6.75, 5.0, 6, 0.3, "User accounts: own row 'you', managers 'protected'", 12, "muted", True)
notes(s, "Screenshots are rendered from the real templates with stubbed data.")

# 7 screenshots 2
s = new_slide(7, "Employees and cashier view", "Real templates, sample data (not live records)")
pic(s, "r3_employees.png", 0.6, 1.5, 4.0)
pic(s, "r3_cashier_sale.png", 4.75, 1.5, 4.0)
pic(s, "r3_forbidden.png", 8.9, 1.5, 4.0)
text(s, 0.6, 4.1, 4, 0.3, "Employee management (manager)", 12, "muted", True)
text(s, 4.75, 4.1, 4, 0.3, "Cashier: restricted navigation", 12, "muted", True)
text(s, 8.9, 4.1, 4, 0.3, "Cashier opening a manager page: 403", 12, "muted", True)
notes(s, "Role-filtered navigation, and the default-deny result when a cashier types a manager URL.")

# 8 security
s = new_slide(8, "Security hardening", "Findings from review and manual testing, with fixes")
table(s, [("Finding", "Fix"),
          ("next= redirect with TAB/newline became an external URL or HTTP 500", "same-site paths only; control chars, backslash, // rejected"),
          ("manage.py traceback on missing configuration", "prints FAILED: … and exits 1"),
          ("/health exposed DB user, service and variable names", "status-only response; detail in server log"),
          ("Oracle Decimal ids in the session cookie bypassed 'cannot delete yourself'", "int casts + regression tests"),
          ("Flask 31-day default session", "8-hour lifetime")], 0.6, 1.5, 12.15, 4.0, (6.4, 5.75), 13)
text(s, 0.6, 5.8, 12.1, 0.8, "Also: bind variables only, CSRF on every POST, escaped output, CSP, least-privilege DB user, hashed passwords.", 14, "muted")
notes(s, "The Decimal bug passed all offline tests; the student found it by using the app against Oracle.")

# 9 tests
tot, per = tally3()
s = new_slide(9, "Testing results", "Offline suite run by the authoring environment · live suite run by the student on Oracle 21c XE")
for i, (label, n, col) in enumerate([("PASSED", tot["PASSED"], "green"), ("FAILED", tot["FAILED"], "red"), ("NOT RUN / BLOCKED", tot["SKIPPED"], "muted")]):
    x = 0.6 + i * 4.1
    box(s, x, 1.55, 3.9, 1.5, "panel", col)
    text(s, x, 1.6, 3.9, 0.9, str(n), 50, col, True, align=PP_ALIGN.CENTER)
    text(s, x, 2.45, 3.9, 0.4, label, 14, "text", True, align=PP_ALIGN.CENTER)
nm = {"test_config": "Configuration", "test_services": "Validation, CRUD, sale transaction (fake DB)",
      "test_routes": "Routes, CSRF, errors, health", "test_auth": "Sign-in, roles, redirects, hashing", "test_throttle": "Login throttle, proxy header handling",
      "test_oracle_integration": "Live Oracle (student run, 2026-10-22)"}
rows = [("Suite", "Scope", "Result")] + [(m + ".py", nm[m], " · ".join(f"{v} {k}" for k, v in per[m].items())) for m in nm]
table(s, rows, 0.6, 3.3, 12.15, 2.5, (3.4, 5.6, 3.15), 13)
text(s, 0.6, 6.0, 12.1, 0.9, ["Live results were transcribed from the student's console output. First live run: 18/19 — the one failure was a mistake in the test, fixed, then 19/19.",
                              "All 16 queries also ran live without error."], 13, "amber")
notes(s, "Fakes prove logic, not Oracle behaviour; that is why the live suite exists.")

# 10 deployment & limits
s = new_slide(10, "Deployment and limitations")
bullets(s, 0.6, 1.4, 6.0, 5.4, [
    "python serve.py (waitress, 8 threads) on 127.0.0.1:8000",
    "HTTPS via a reverse proxy; APP_ENV=production turns on Secure cookies",
    "Start at boot with Task Scheduler or NSSM",
    "Backups with expdp / RMAN; password rotation steps",
    "docs/deployment.md has the full guide"], 16, gap=8)
bullets(s, 6.8, 1.4, 6.0, 5.4, [
    "Login throttle is bounded and proxy-aware, but per process: resets on restart, not shared by workers",
    "No password-reset e-mail or MFA; managers reset passwords",
    "Role changes apply at next sign-in",
    "HTTPS deployment and a recorded browser walkthrough not yet done",
    "Trigger test-cleanup bypass should be removed for production"], 16, gap=8)
notes(s, "The throttle redesign is covered by offline tests only; HTTPS was not exercised.")

# 11 conclusion
s = new_slide(11, "Conclusion")
chk = [("DONE", "green", "Login, Manager/Cashier roles, default-deny gate, employee and account management"),
       ("DONE", "green", "Hardening fixes with regression tests; Decimal-id bug fixed"),
       ("DONE", "green", f"{tot['PASSED']} tests PASSED (155 offline + 19 live on Oracle 21c XE); 16 queries ran live"),
       ("DONE", "green", "README, deployment guide, demo guide, Review 2 and Review 3 reports"),
       ("TO DO", "amber", "HTTPS deployment, recorded role walkthrough, shared throttle store if several workers")]
for i, (tag, col, msg) in enumerate(chk):
    y = 1.5 + i * 0.95
    box(s, 0.6, y, 12.15, 0.8, "panel", col, 0.1, 1.0)
    text(s, 0.75, y + 0.08, 1.1, 0.6, tag, 15, col, True, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 1.95, y + 0.08, 10.7, 0.6, msg, 15, "text", anchor=MSO_ANCHOR.MIDDLE)
notes(s, "Offer to demonstrate a manager login, a cashier sale and a 403.")

assert len(prs.slides) == total_slides, len(prs.slides)
out = os.path.join(ROOT, "docs", "Review_3_Presentation.pptx")
prs.save(out)
print(out, os.path.getsize(out), "bytes,", len(prs.slides), "slides")
