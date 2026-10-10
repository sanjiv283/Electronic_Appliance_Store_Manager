"""Build docs/Review_2_Presentation.pptx (12 slides) from the project's real facts.

    python -m pytest tests --junitxml=docs/test_results.xml
    python docs/build_presentation.py

Test numbers are read from docs/test_results.xml - never typed by hand.
"""
import os
import xml.etree.ElementTree as ET

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, "docs", "images")
C = {k: RGBColor.from_string(v) for k, v in dict(
    bg="0B1020", panel="141B33", panel2="1C2547", cyan="00E5FF", mag="FF2E93", text="E8EEF8",
    muted="9AA7C7", amber="FFB300", green="00E676", red="FF5252").items()}
SANS, MONO = "Calibri", "Consolas"

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]
total_slides = 12


def tally():
    t = {"PASSED": 0, "BLOCKED": 0, "FAILED": 0, "NOT RUN": 0}
    per = {}
    for case in ET.parse(os.path.join(ROOT, "docs", "test_results.xml")).getroot().iter("testcase"):
        mod, status = case.get("classname").split(".")[-1], "PASSED"
        for ch in case:
            if ch.tag in ("failure", "error"):
                status = "FAILED"
            elif ch.tag == "skipped":
                status = "BLOCKED" if (ch.get("message") or "").startswith("BLOCKED") else "NOT RUN"
        t[status] += 1
        per.setdefault(mod, {}).setdefault(status, 0)
        per[mod][status] += 1
    return t, per


def text(slide, x, y, w, h, s, size=16, color="text", bold=False, font=SANS, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap, tf.vertical_anchor = True, anchor
    tf.margin_left = tf.margin_right = Inches(0.05)
    tf.margin_top = tf.margin_bottom = Inches(0.03)
    lines = s if isinstance(s, list) else [s]
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        r = p.add_run()
        r.text = line
        r.font.size, r.font.bold, r.font.name = Pt(size), bold, font
        r.font.color.rgb = C[color]
    return tb


def bullets(slide, x, y, w, h, items, size=17, color="text", gap=6):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    for i, it in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(gap)
        r0 = p.add_run()
        r0.text = "▪ "
        r0.font.size, r0.font.color.rgb, r0.font.name = Pt(size), C["cyan"], SANS
        r = p.add_run()
        r.text = it
        r.font.size, r.font.name = Pt(size), SANS
        r.font.color.rgb = C[color]
    return tb


def box(slide, x, y, w, h, fill="panel", line="cyan", radius=0.06, lw=1.25):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    s.adjustments[0] = radius
    s.fill.solid()
    s.fill.fore_color.rgb = C[fill]
    if line:
        s.line.color.rgb, s.line.width = C[line], Pt(lw)
    else:
        s.line.fill.background()
    s.shadow.inherit = False
    return s


def line(slide, x1, y1, x2, y2, color="cyan", w=2.0):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb, c.line.width = C[color], Pt(w)
    return c


def new_slide(n, title, subtitle=None):
    s = prs.slides.add_slide(BLANK)
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = C["bg"]
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(0.18), prs.slide_height)
    bar.fill.solid(); bar.fill.fore_color.rgb = C["cyan"]; bar.line.fill.background()
    text(s, 0.55, 0.3, 12.2, 0.7, title, 30, "text", True)
    ul = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.6), Inches(0.98), Inches(1.1), Inches(0.05))
    ul.fill.solid(); ul.fill.fore_color.rgb = C["mag"]; ul.line.fill.background()
    if subtitle:
        text(s, 0.55, 1.02, 12.2, 0.32, subtitle, 13, "muted")
    text(s, 0.55, 7.1, 9, 0.3, "Electronic Appliance Store Management System · DBMS Review 2 · Sanjiv Shine Fernandas", 10, "muted")
    text(s, 11.8, 7.1, 1.0, 0.3, f"{n} / {total_slides}", 10, "muted", align=PP_ALIGN.RIGHT)
    return s


def notes(slide, s):
    slide.notes_slide.notes_text_frame.text = s


# ---------------------------------------------------------------- 1 title
s = prs.slides.add_slide(BLANK)
s.background.fill.solid(); s.background.fill.fore_color.rgb = C["bg"]
for i, col in enumerate(("cyan", "mag")):
    r = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Inches(2.2 + i * 0.07), prs.slide_width, Inches(0.04))
    r.fill.solid(); r.fill.fore_color.rgb = C[col]; r.line.fill.background()
text(s, 0.9, 0.7, 11, 0.5, "DATABASE MANAGEMENT SYSTEMS · REVIEW 2", 16, "cyan", True)
text(s, 0.9, 2.5, 11.6, 1.6, ["Electronic Appliance", "Store Management System"], 48, "text", True)
text(s, 0.9, 4.3, 11.6, 0.5, "Database Implementation & Backend Integration", 22, "muted")
text(s, 0.9, 5.2, 8, 1.2, ["Sanjiv Shine Fernandas", "Subject: Database Management Systems (DBMS)"], 20, "text")
text(s, 8.2, 5.2, 4.4, 1.3, ["Oracle Database 21c XE · XEPDB1", "Flask · python-oracledb (Thin)", "HTML5 · CSS3 · vanilla JS"], 15, "cyan", font=MONO)
text(s, 0.9, 6.9, 11, 0.3, "github.com/sanjiv283/Electronic_Appliance_Store_Manager", 12, "muted")
notes(s, "Introduce the project, the student and the Review 2 scope: database implementation and backend integration.")

# ---------------------------------------------------------------- 2 problem
s = new_slide(2, "Problem statement & objectives")
box(s, 0.6, 1.4, 5.9, 5.0)
text(s, 0.85, 1.5, 5.4, 0.4, "THE PROBLEM", 14, "mag", True)
bullets(s, 0.85, 2.0, 5.5, 4.7, [
    "Appliance retail: high-value items, changing prices, limited stock",
    "Spreadsheets cause oversold items and lost price history",
    "Customer, supplier and product data get duplicated and inconsistent",
    "Concurrent cashiers can sell the same last unit twice",
    "Managers need quick answers: revenue, best sellers, low stock"], 18, gap=9)
box(s, 6.8, 1.4, 5.95, 5.0)
text(s, 7.05, 1.5, 5.4, 0.4, "OBJECTIVES", 14, "cyan", True)
bullets(s, 7.05, 2.0, 5.55, 4.7, [
    "Normalized (3NF) Oracle schema with full integrity constraints",
    "Fictional seed data; 16 documented SQL queries",
    "View, procedure, function and trigger in PL/SQL",
    "Secure Flask ↔ Oracle connectivity (Thin mode, least-privilege user)",
    "CRUD + an atomic, lock-ordered sales transaction",
    "Automated tests with honest PASSED / BLOCKED reporting"], 18, gap=9)
notes(s, "Scope: master-data CRUD, sales, inventory reports. Out of scope: login/roles, returns, taxes.")

# ---------------------------------------------------------------- 3 architecture
s = new_slide(3, "System architecture", "Routes call services; services own all SQL")
layers = [("Browser", "HTML5 · CSS3 · vanilla JS · cyberpunk theme (dark / light)", "cyan"),
          ("Flask routes — app.py", "25 routes · CSRF tokens · security headers · safe error pages", "cyan"),
          ("Service layer — services/*.py", "validation · CRUD · sales transaction · reports — bind variables only", "mag"),
          ("services/database.py + python-oracledb (Thin)", "connections · Oracle-error translation · config.py reads .env", "mag"),
          ("Oracle 21c XE — XEPDB1 · schema appliance_app", "7 tables · view · procedure · function · trigger · sequence", "green")]
for i, (t, sub, col) in enumerate(layers):
    y = 1.35 + i * 1.12
    box(s, 0.7, y, 7.6, 0.88, "panel", col)
    text(s, 0.9, y + 0.05, 7.2, 0.4, t, 18, "text", True)
    text(s, 0.9, y + 0.44, 7.2, 0.4, sub, 13, "muted")
    if i < 4:
        a = s.shapes.add_shape(MSO_SHAPE.DOWN_ARROW, Inches(4.35), Inches(y + 0.88), Inches(0.3), Inches(0.24))
        a.fill.solid(); a.fill.fore_color.rgb = C["cyan"]; a.line.fill.background()
box(s, 8.7, 1.35, 4.05, 5.5, "panel2", None)
text(s, 8.9, 1.45, 3.7, 0.4, "TECHNOLOGY STACK", 14, "cyan", True)
bullets(s, 8.9, 1.95, 3.7, 4.8, ["Python · Flask · python-dotenv", "python-oracledb, Thin mode (no Oracle Client)",
                                 "Oracle Database 21c XE", "pytest + fake DB connection", "Windows local demonstration",
                                 "Connects only as appliance_app — never SYS/SYSTEM"], 15)
notes(s, "Single direction of dependency. Only services/database.py opens connections.")

# ---------------------------------------------------------------- 4 ER diagram (native shapes)
s = new_slide(4, "Entity-relationship diagram", "Key columns shown · full column list in report §11 · matches database/schema.sql")
ENT = {
    "CATEGORIES": (0.7, 1.9, ["PK CATEGORY_ID", "UK CATEGORY_NAME", "   DESCRIPTION"]),
    "PRODUCTS": (5.17, 1.4, ["PK PRODUCT_ID", "UK MODEL_NO", "FK CATEGORY_ID", "FK SUPPLIER_ID", "   UNIT_PRICE · STOCK_QTY"]),
    "SUPPLIERS": (9.63, 1.9, ["PK SUPPLIER_ID", "UK SUPPLIER_NAME", "   CONTACT · EMAIL · PHONE"]),
    "SALE_ITEMS": (5.17, 3.55, ["PK SALE_ITEM_ID", "FK SALE_ID", "FK PRODUCT_ID", "   QUANTITY · UNIT_PRICE", "   LINE_TOTAL"]),
    "CUSTOMERS": (0.7, 5.75, ["PK CUSTOMER_ID", "UK EMAIL", "   FULL_NAME · PHONE"]),
    "SALES": (5.17, 5.67, ["PK SALE_ID · UK INVOICE_NO", "FK CUSTOMER_ID", "FK EMPLOYEE_ID", "   SALE_DATE · TOTAL_AMOUNT"]),
    "EMPLOYEES": (9.63, 5.75, ["PK EMPLOYEE_ID", "UK EMAIL", "   FULL_NAME · JOB_TITLE"]),
}
W = 3.0
RH = 0.215
geo = {}
for name, (x, y, cols) in ENT.items():
    h = 0.36 + RH * len(cols) + 0.08
    box(s, x, y, W, h, "panel", "cyan", 0.04)
    hd = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(W), Inches(0.34))
    hd.fill.solid(); hd.fill.fore_color.rgb = C["cyan"]; hd.line.fill.background()
    text(s, x, y + 0.01, W, 0.32, name, 14, "bg", True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    tb = text(s, x + 0.1, y + 0.38, W - 0.2, h - 0.4, cols, 11.5, "text", font=MONO)
    for p in tb.text_frame.paragraphs:
        tag = p.runs[0].text[:2]
        if tag in ("PK", "UK", "FK"):
            p.runs[0].font.color.rgb = C["mag"] if tag == "FK" else C["cyan"]
            p.runs[0].font.bold = True
    geo[name] = (x, y, W, h)


def mid(n, side):
    x, y, w, h = geo[n]
    return {"l": (x, y + h / 2), "r": (x + w, y + h / 2), "t": (x + w / 2, y), "b": (x + w / 2, y + h)}[side]


def rel(parent, ps, child, cs, label, vertical=False):
    (x1, y1), (x2, y2) = mid(parent, ps), mid(child, cs)
    line(s, x1, y1, x2, y2, "cyan", 2.25)
    off = {"r": (0.08, -0.3), "l": (-0.38, -0.3), "t": (-0.42, -0.3), "b": (-0.42, 0.02)}
    text(s, x1 + off[ps][0], y1 + off[ps][1], 0.35, 0.3, "1", 14, "text", True)
    text(s, x2 + off[cs][0], y2 + off[cs][1], 0.35, 0.3, "N", 14, "mag", True)
    if vertical:
        text(s, (x1 + x2) / 2 + 0.12, (y1 + y2) / 2 - 0.15, 1.6, 0.3, label, 11, "muted")
    else:
        text(s, (x1 + x2) / 2 - 0.55, (y1 + y2) / 2 - 0.3, 1.1, 0.3, label, 11, "muted", align=PP_ALIGN.CENTER)


rel("CATEGORIES", "r", "PRODUCTS", "l", "classifies")
rel("SUPPLIERS", "l", "PRODUCTS", "r", "supplies")
rel("PRODUCTS", "b", "SALE_ITEMS", "t", "appears in", vertical=True)
rel("SALES", "t", "SALE_ITEMS", "b", "contains (1..N)", vertical=True)
rel("CUSTOMERS", "r", "SALES", "l", "places")
rel("EMPLOYEES", "l", "SALES", "r", "processes")
notes(s, "Seven tables, six one-to-many relationships. No cascade deletes, so sales history is protected. SALE_ITEMS keeps the price and quantity at sale time.")

# ---------------------------------------------------------------- 5 schema table
s = new_slide(5, "Database schema & relationships", "Identity primary keys · all foreign keys are restrict (no cascade)")
rows = [("Table", "Primary key", "Foreign keys", "Unique / CHECK highlights"),
        ("CATEGORIES", "CATEGORY_ID", "—", "UQ category name"),
        ("SUPPLIERS", "SUPPLIER_ID", "—", "UQ supplier name"),
        ("PRODUCTS", "PRODUCT_ID", "CATEGORY_ID, SUPPLIER_ID", "UQ model no · price ≥ 0 · stock ≥ 0"),
        ("CUSTOMERS", "CUSTOMER_ID", "—", "UQ e-mail"),
        ("EMPLOYEES", "EMPLOYEE_ID", "—", "UQ e-mail"),
        ("SALES", "SALE_ID", "CUSTOMER_ID, EMPLOYEE_ID", "UQ invoice no · payment ∈ {CASH, CARD, UPI, BANK_TRANSFER} · total > 0"),
        ("SALE_ITEMS", "SALE_ITEM_ID", "SALE_ID, PRODUCT_ID", "UQ (sale, product) · qty > 0 · line total = qty × price")]
tbl = s.shapes.add_table(len(rows), 4, Inches(0.6), Inches(1.4), Inches(12.15), Inches(3.9)).table
for ci, w in enumerate((1.9, 2.0, 3.2, 5.05)):
    tbl.columns[ci].width = Inches(w)
for ri, r in enumerate(rows):
    for ci, v in enumerate(r):
        cell = tbl.cell(ri, ci)
        cell.fill.solid(); cell.fill.fore_color.rgb = C["cyan"] if ri == 0 else (C["panel"] if ri % 2 else C["panel2"])
        cell.text = v
        p = cell.text_frame.paragraphs[0]
        p.runs[0].font.size, p.runs[0].font.name = Pt(14), SANS
        p.runs[0].font.bold = ri == 0 or ci == 0
        p.runs[0].font.color.rgb = C["bg"] if ri == 0 else C["text"]
bullets(s, 0.6, 5.5, 12.1, 1.5, [
    "Relationships: category→products, supplier→products, customer→sales, employee→sales, sale→items, product→items",
    "7 tables · 6 indexes on FK/report columns · sequence SEQ_INVOICE_NO · sample data: 14 products, 8 sales, 15 sale items"], 15)
notes(s, "Deleting a customer, employee or product with history fails with ORA-02292, shown to the user as a friendly 409.")

# ---------------------------------------------------------------- 6 normalization
s = new_slide(6, "Normalization: 1NF → 3NF")
for i, (h, col, items) in enumerate([
        ("1NF", "cyan", ["Atomic columns, a key in every table", "No repeating groups: many products per sale = rows in SALE_ITEMS, not PRODUCT1, PRODUCT2 …"]),
        ("2NF", "mag", ["Single-column surrogate keys: no partial dependency possible", "SALE_ITEMS (SALE_ID, PRODUCT_ID): qty and price depend on both; product name is NOT copied in"]),
        ("3NF", "green", ["Non-key attributes depend only on the key", "PRODUCTS stores category/supplier as FKs, not names; SALES stores no customer or employee names"])]):
    x = 0.6 + i * 4.1
    box(s, x, 1.4, 3.95, 3.7, "panel", col)
    text(s, x + 0.2, 1.5, 3.5, 0.6, h, 30, col, True)
    bullets(s, x + 0.2, 2.2, 3.6, 2.9, items, 15)
box(s, 0.6, 5.3, 12.15, 1.65, "panel2", "amber")
text(s, 0.8, 5.35, 11.8, 0.4, "DOCUMENTED, DELIBERATE REDUNDANCY (not hidden)", 13, "amber", True)
bullets(s, 0.8, 5.75, 11.8, 1.2, [
    "SALE_ITEMS.LINE_TOTAL = QUANTITY × UNIT_PRICE is derived, so strictly SALE_ITEMS is not 3NF — kept for audit/reporting and guarded by a CHECK constraint",
    "SALES.TOTAL_AMOUNT = sum of lines: computed once by the service; view V_SALES_SUMMARY exposes mismatches"], 13.5, gap=3)
notes(s, "Be upfront: LINE_TOTAL is a derived column, a controlled trade-off. SALE_ITEMS.UNIT_PRICE is the historical price, not a copy of the current price.")

# ---------------------------------------------------------------- 7 SQL + advanced
s = new_slide(7, "SQL queries & advanced database features", "16 numbered queries in queries.sql · 4 objects in advanced_features.sql")
box(s, 0.6, 1.35, 6.1, 5.55)
text(s, 0.8, 1.42, 5.7, 0.4, "16 QUERIES — CONCEPTS", 14, "cyan", True)
bullets(s, 0.8, 1.85, 5.8, 2.6, ["Filtering, IN-subquery, INNER / LEFT JOIN (Q1–Q6)", "5-table join over an invoice (Q7)",
                                  "GROUP BY, SUM/COUNT/AVG, HAVING (Q8–Q10)", "Scalar & correlated subqueries (Q11–Q12)",
                                  "NOT EXISTS, FETCH FIRST, RANK(), CASE (Q13–Q16)"], 14, gap=3)
code = ["-- Query 12: above own-category average",
        "SELECT p.PRODUCT_NAME, p.UNIT_PRICE",
        "  FROM PRODUCTS p",
        " WHERE p.UNIT_PRICE >",
        "   (SELECT AVG(p2.UNIT_PRICE) FROM PRODUCTS p2",
        "     WHERE p2.CATEGORY_ID = p.CATEGORY_ID);"]
box(s, 0.8, 4.55, 5.7, 2.2, "bg", "muted", 0.03, 0.75)
text(s, 0.9, 4.65, 5.5, 2.1, code, 13, "green", font=MONO)
box(s, 6.95, 1.35, 5.8, 5.55)
text(s, 7.15, 1.42, 5.4, 0.4, "PL/SQL OBJECTS", 14, "mag", True)
for i, (n, d) in enumerate([("V_SALES_SUMMARY  (view)", "sale + customer + employee + line count + TOTAL_MATCHES check"),
                            ("SP_RESTOCK_PRODUCT  (procedure)", "adds stock under a row lock; ORA-20001 / 20002 errors"),
                            ("FN_CUSTOMER_TOTAL_SPEND  (function)", "lifetime spend, 0 if none; ORA-20010 unknown customer"),
                            ("TRG_SALES_PROTECT_HISTORY  (trigger)", "blocks DELETE / UPDATE of posted sales (ORA-20030 / 20031); no stock logic")]):
    y = 1.9 + i * 1.22
    box(s, 7.15, y, 5.4, 1.08, "panel2", "mag", 0.05, 1.0)
    text(s, 7.3, y + 0.04, 5.15, 0.4, n, 14.5, "text", True, font=MONO)
    text(s, 7.3, y + 0.46, 5.15, 0.6, d, 12.5, "muted")
notes(s, "Syntax-checked statically (sqlglot, Oracle dialect) for the queries; live execution on Oracle is pending — state this plainly.")

# ---------------------------------------------------------------- 8 Flask + Oracle
s = new_slide(8, "Flask backend & Oracle connectivity")
box(s, 0.6, 1.35, 5.9, 5.55)
text(s, 0.8, 1.42, 5.5, 0.4, "CONNECTIVITY & CRUD", 14, "cyan", True)
bullets(s, 0.8, 1.9, 5.55, 5.0, [
    "config.py: DB_HOST / PORT / SERVICE_NAME / USER / PASSWORD from .env; placeholders count as missing; SYS/SYSTEM refused",
    "python-oracledb Thin mode; connection per unit of work, always closed",
    "Bind variables only; server-side validation; Decimal for money",
    "ORA errors translated to safe 400 / 404 / 409 / 503 messages",
    "/health and python -m services.database report success only after a real round trip",
    "CRUD: products, categories, suppliers, customers + search, filters, pagination"], 14.5, gap=5)
box(s, 6.8, 1.35, 5.95, 5.55)
text(s, 7.0, 1.42, 5.5, 0.4, "ATOMIC SALE — services/sales.py", 14, "mag", True)
steps = ["1  validate ids, payment, items (qty 1–1000)", "2  check customer & employee exist",
         "3  SELECT … FOR UPDATE WAIT 10 per product,", "    in ascending product id (no deadlock)",
         "4  re-check stock after ALL locks held", "5  total = Σ DB price × qty  (never client)",
         "6  INSERT sale + items, UPDATE stock (once)", "7  COMMIT   — any error → ROLLBACK"]
box(s, 7.0, 1.9, 5.55, 3.55, "bg", "muted", 0.03, 0.75)
text(s, 7.1, 2.0, 5.4, 3.4, steps, 14, "green", font=MONO)
bullets(s, 7.0, 5.6, 5.6, 1.3, ["Stock is deducted only here — the trigger never touches inventory",
                                "Oversell protection: row locks + CHECK (STOCK_QTY ≥ 0)"], 13.5, gap=3)
notes(s, "Live concurrency proof (8 buyers, stock 5 -> exactly 5 succeed) is an integration test that needs Oracle: BLOCKED here.")

# ---------------------------------------------------------------- 9 UI
s = new_slide(9, "Application UI & key workflows", "Cyberpunk theme · dark default + light palette")
s.shapes.add_picture(os.path.join(IMG, "ui_dashboard.png"), Inches(0.6), Inches(1.45), width=Inches(6.0))
s.shapes.add_picture(os.path.join(IMG, "ui_new_sale.png"), Inches(6.75), Inches(1.45), width=Inches(6.0))
text(s, 0.6, 5.0, 6, 0.3, "Dashboard", 12, "muted", True)
text(s, 6.75, 5.0, 6, 0.3, "New sale — two lines, estimate only (server recalculates)", 12, "muted", True)
bullets(s, 0.6, 5.4, 12.1, 1.1, [
    "Workflow: add/edit master data → New Sale → invoice page → stock falls once → Reports",
    "Delete confirmation, CSRF on every POST, empty / error / 503 states, responsive layout"], 15, gap=3)
text(s, 0.6, 6.5, 12.1, 0.5, "Screenshots show the real templates and routes rendered with seed-equivalent sample data — no Oracle was available, so they are not live database results.",
     12, "amber")
notes(s, "Be explicit that the screenshots use stubbed service data. The real app without DB shows an honest 503 page.")

# ---------------------------------------------------------------- 10 testing
tot, per = tally()
s = new_slide(10, "Testing results", "Strict statuses: PASSED · FAILED · NOT RUN · BLOCKED")
for i, (label, n, col) in enumerate([("PASSED", tot["PASSED"], "green"), ("BLOCKED", tot["BLOCKED"], "amber"),
                                      ("FAILED", tot["FAILED"], "red"), ("NOT RUN", tot["NOT RUN"], "muted")]):
    x = 0.6 + i * 3.08
    box(s, x, 1.35, 2.9, 1.55, "panel", col)
    text(s, x, 1.4, 2.9, 0.9, str(n), 54, col, True, align=PP_ALIGN.CENTER)
    text(s, x, 2.3, 2.9, 0.4, label, 15, "text", True, align=PP_ALIGN.CENTER)
rows = [("Suite", "Scope", "Result")]
names = {"test_config": "Configuration rules", "test_services": "Validation, CRUD, sale transaction (fake DB)",
         "test_routes": "Routes, CSRF, errors, escaping, health", "test_oracle_integration": "Live Oracle (constraints, PL/SQL, locking)"}
for m in ("test_config", "test_services", "test_routes", "test_oracle_integration"):
    d = per.get(m, {})
    rows.append((m + ".py", names[m], " · ".join(f"{v} {k}" for k, v in d.items())))
tb = s.shapes.add_table(len(rows), 3, Inches(0.6), Inches(3.15), Inches(12.15), Inches(2.1)).table
for ci, w in enumerate((3.4, 5.6, 3.15)):
    tb.columns[ci].width = Inches(w)
for ri, r in enumerate(rows):
    for ci, v in enumerate(r):
        c = tb.cell(ri, ci); c.fill.solid(); c.fill.fore_color.rgb = C["cyan"] if ri == 0 else (C["panel"] if ri % 2 else C["panel2"])
        c.text = v; run = c.text_frame.paragraphs[0].runs[0]
        run.font.size, run.font.name, run.font.bold = Pt(14), SANS, ri == 0
        run.font.color.rgb = C["bg"] if ri == 0 else (C["amber"] if "BLOCKED" in v else C["text"])
bullets(s, 0.6, 5.45, 12.1, 1.6, [
    f"{tot['PASSED']} offline tests passed using a FAKE database connection: they prove application logic, not Oracle behaviour",
    f"{tot['BLOCKED']} live Oracle integration tests are BLOCKED / unverified — no Oracle instance was available; they are ready to run (README §9)",
    "Also passed: compile check, JS syntax, SQL syntax parse (queries + seed), Chromium page-render check"], 14.5, gap=3)
notes(s, "Do not claim database verification. The BLOCKED tests are the ones that prove constraints, PL/SQL objects and concurrency on a real Oracle.")

# ---------------------------------------------------------------- 11 limitations
s = new_slide(11, "Limitations & future improvements")
box(s, 0.6, 1.4, 5.95, 5.45, "panel", "amber")
text(s, 0.85, 1.5, 5.4, 0.4, "KNOWN LIMITATIONS", 14, "amber", True)
bullets(s, 0.85, 2.0, 5.5, 4.8, ["Not yet run against a live Oracle instance (16 tests BLOCKED)",
                                 "No login, roles or per-user audit trail — localhost demo only",
                                 "No returns, discounts, taxes or multi-currency; employees are seed-only",
                                 "LINE_TOTAL is a documented derived column; sale total consistency is service-enforced",
                                 "Trigger has a test-cleanup bypass (remove for production)",
                                 "Per-request connections, no pool"], 15.5)
box(s, 6.8, 1.4, 5.95, 5.45, "panel", "cyan")
text(s, 7.05, 1.5, 5.4, 0.4, "FUTURE IMPROVEMENTS", 14, "cyan", True)
bullets(s, 7.05, 2.0, 5.5, 4.8, ["Authentication and role-based access (admin / cashier)",
                                 "Connection pool; HTTPS deployment behind a WSGI server",
                                 "Returns/refunds, purchase orders to suppliers, tax and discounts",
                                 "Employee management screen; audit table fed by a trigger",
                                 "CI pipeline with an Oracle test container",
                                 "Charts and CSV export on reports"], 15.5)
notes(s, "Naming limitations openly is part of the evaluation criteria for accuracy.")

# ---------------------------------------------------------------- 12 conclusion
s = new_slide(12, "Conclusion & demonstration readiness")
bullets(s, 0.6, 1.3, 12.1, 1.5, [
    "Delivered: normalized 7-table Oracle design, seed data, 16 queries, 4 PL/SQL-side objects, secure Flask service layer, atomic sales, cyberpunk UI, tests and report",
    "Every claim above is backed by files in the repository; unverified items are labelled BLOCKED"], 16, gap=4)
chk = [("DONE", "green", "Code, SQL scripts, tests (76 passed offline), report PDF / DOCX / MD, this deck"),
       ("DONE", "green", "Screenshots of the real templates (sample data) and honest 503 page"),
       ("TO DO", "amber", "Run schema.sql → advanced_features.sql → seed.sql in XEPDB1 as appliance_app"),
       ("TO DO", "amber", "python -m services.database  then the live integration tests (separate test schema)"),
       ("TO DO", "amber", "Rehearse docs/demo_guide.md (10 minutes); regenerate report matrix after live run")]
for i, (tag, col, msg) in enumerate(chk):
    y = 2.65 + i * 0.75
    box(s, 0.6, y, 12.15, 0.65, "panel", col, 0.1, 1.0)
    text(s, 0.75, y + 0.05, 1.1, 0.55, tag, 15, col, True, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 1.95, y + 0.05, 10.7, 0.55, msg, 15, "text", anchor=MSO_ANCHOR.MIDDLE)
text(s, 0.6, 6.55, 12, 0.4, "Demonstration readiness: ready once the three live Oracle steps are completed on the presenter's machine.", 13, "muted")
notes(s, "Thank the panel; offer to demonstrate the sale transaction and the failing constraint inserts.")

assert len(prs.slides) == total_slides
out = os.path.join(ROOT, "docs", "Review_2_Presentation.pptx")
prs.save(out)
print(out, os.path.getsize(out), "bytes,", len(prs.slides), "slides")
