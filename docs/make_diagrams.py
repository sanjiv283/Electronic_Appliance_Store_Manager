"""Draw the ER and architecture diagrams from the real schema definition (docs/images/*.png).
    python docs/make_diagrams.py        (needs matplotlib; development-time only)"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")
INK, CYAN, MAG, BG, PANEL = "#0b1020", "#00b8d4", "#c2185b", "#ffffff", "#eef4f8"

# name -> [(column, type, flag)]  -- must match database/schema.sql
TABLES = {
 "CATEGORIES": [("CATEGORY_ID","NUMBER","PK"),("CATEGORY_NAME","VARCHAR2(60)","UK"),("DESCRIPTION","VARCHAR2(255)","")],
 "SUPPLIERS": [("SUPPLIER_ID","NUMBER","PK"),("SUPPLIER_NAME","VARCHAR2(100)","UK"),("CONTACT_PERSON","VARCHAR2(100)",""),("EMAIL","VARCHAR2(120)",""),("PHONE","VARCHAR2(20)",""),("ADDRESS","VARCHAR2(255)","")],
 "PRODUCTS": [("PRODUCT_ID","NUMBER","PK"),("PRODUCT_NAME","VARCHAR2(120)",""),("BRAND","VARCHAR2(60)",""),("MODEL_NO","VARCHAR2(40)","UK"),("CATEGORY_ID","NUMBER","FK"),("SUPPLIER_ID","NUMBER","FK"),("UNIT_PRICE","NUMBER(10,2)",""),("STOCK_QTY","NUMBER(8)",""),("REORDER_LEVEL","NUMBER(6)",""),("WARRANTY_MONTHS","NUMBER(3)",""),("CREATED_AT","TIMESTAMP","")],
 "CUSTOMERS": [("CUSTOMER_ID","NUMBER","PK"),("FULL_NAME","VARCHAR2(100)",""),("EMAIL","VARCHAR2(120)","UK"),("PHONE","VARCHAR2(20)",""),("ADDRESS","VARCHAR2(255)",""),("CREATED_AT","TIMESTAMP","")],
 "EMPLOYEES": [("EMPLOYEE_ID","NUMBER","PK"),("FULL_NAME","VARCHAR2(100)",""),("EMAIL","VARCHAR2(120)","UK"),("PHONE","VARCHAR2(20)",""),("JOB_TITLE","VARCHAR2(60)",""),("HIRE_DATE","DATE","")],
 "SALES": [("SALE_ID","NUMBER","PK"),("INVOICE_NO","VARCHAR2(20)","UK"),("CUSTOMER_ID","NUMBER","FK"),("EMPLOYEE_ID","NUMBER","FK"),("SALE_DATE","TIMESTAMP",""),("PAYMENT_METHOD","VARCHAR2(20)",""),("TOTAL_AMOUNT","NUMBER(12,2)","")],
 "SALE_ITEMS": [("SALE_ITEM_ID","NUMBER","PK"),("SALE_ID","NUMBER","FK"),("PRODUCT_ID","NUMBER","FK"),("QUANTITY","NUMBER(6)",""),("UNIT_PRICE","NUMBER(10,2)",""),("LINE_TOTAL","NUMBER(12,2)","")],
}
W, ROW = 3.9, 0.36
# name -> (x, y_top): a cross layout that keeps every relationship line straight
POS = {"CATEGORIES": (0.2, 11.4), "PRODUCTS": (5.4, 11.9), "SUPPLIERS": (10.6, 11.4),
       "SALE_ITEMS": (5.4, 6.5), "CUSTOMERS": (0.2, 2.6), "SALES": (5.4, 2.6), "EMPLOYEES": (10.6, 2.6)}


def box(ax, name):
    x, top = POS[name]
    cols = TABLES[name]
    h = 0.55 + ROW * len(cols)
    ax.add_patch(FancyBboxPatch((x, top - h), W, h, boxstyle="round,pad=0,rounding_size=0.08", fc=PANEL, ec=INK, lw=1.4))
    ax.add_patch(FancyBboxPatch((x, top - 0.5), W, 0.5, boxstyle="round,pad=0,rounding_size=0.08", fc=INK, ec=INK))
    ax.text(x + W / 2, top - 0.28, name, color="white", ha="center", va="center", fontsize=14, fontweight="bold", family="DejaVu Sans")
    for i, (c, t, f) in enumerate(cols):
        y = top - 0.55 - ROW * (i + 0.55)
        ax.text(x + 0.1, y, f, fontsize=10, color=MAG if f == "FK" else CYAN if f == "PK" else "#555", fontweight="bold", va="center", family="DejaVu Sans Mono")
        ax.text(x + 0.6, y, c, fontsize=11, va="center", family="DejaVu Sans Mono", color=INK)
        ax.text(x + W - 0.1, y, t, fontsize=8.5, va="center", ha="right", color="#555", family="DejaVu Sans Mono")
    return dict(l=(x, top - h / 2), r=(x + W, top - h / 2), t=(x + W / 2, top), b=(x + W / 2, top - h), x=x, top=top, h=h)


def rel(ax, p, c, label, pa, ca, lab_off=(0, 0.15)):
    (x1, y1), (x2, y2) = p[pa], c[ca]
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-", color=CYAN, lw=1.8, shrinkA=0, shrinkB=0))
    ax.text(x1 + (0.18 if pa == "r" else -0.18 if pa == "l" else 0.0), y1 + (0.2 if pa == "t" else -0.2 if pa == "b" else 0.15), "1", color=INK, fontsize=11, fontweight="bold", ha="center")
    ax.text(x2 + (0.18 if ca == "r" else -0.18 if ca == "l" else 0.0), y2 + (0.2 if ca == "t" else -0.25 if ca == "b" else 0.15), "N", color=MAG, fontsize=11, fontweight="bold", ha="center")
    ax.text((x1 + x2) / 2 + lab_off[0], (y1 + y2) / 2 + lab_off[1], label, fontsize=8.5, style="italic", ha="center", color=INK,
            bbox=dict(fc="white", ec="none", pad=1))


def er():
    fig, ax = plt.subplots(figsize=(14.6, 12.2))
    ax.set_xlim(0, 14.7); ax.set_ylim(-1.9, 12.2); ax.axis("off")
    b = {n: box(ax, n) for n in TABLES}
    rel(ax, b["CATEGORIES"], b["PRODUCTS"], "classifies", "r", "l", lab_off=(0, 0.2))
    rel(ax, b["SUPPLIERS"], b["PRODUCTS"], "supplies", "l", "r", lab_off=(0, 0.2))
    rel(ax, b["PRODUCTS"], b["SALE_ITEMS"], "appears in", "b", "t", lab_off=(1.0, 0))
    rel(ax, b["SALES"], b["SALE_ITEMS"], "contains (1..N)", "t", "b", lab_off=(1.2, 0))
    rel(ax, b["CUSTOMERS"], b["SALES"], "places", "r", "l", lab_off=(0, 0.2))
    rel(ax, b["EMPLOYEES"], b["SALES"], "processes", "l", "r", lab_off=(0, 0.2))
    ax.text(0.2, -1.2, "PK primary key  FK foreign key (all NO ACTION / restrict, no cascade)  UK unique key\nAlso UNIQUE (SALE_ID, PRODUCT_ID) on SALE_ITEMS. Drawn from database/schema.sql.",
            fontsize=10, color="#444", va="center")
    fig.savefig(os.path.join(OUT, "er_diagram.png"), dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close(fig)


def arch():
    fig, ax = plt.subplots(figsize=(11, 5.2)); ax.set_xlim(0, 11); ax.set_ylim(0, 5.2); ax.axis("off")
    layers = [("Browser", "HTML5 · CSS3 · vanilla JS (cyberpunk theme)", "#e3f6fb"),
              ("Flask routes — app.py", "CSRF · security headers · error pages · 25 routes", "#eaf0fb"),
              ("Service layer — services/*.py", "validation · CRUD · sales transaction · reports (all SQL, bind variables)", "#f3e8f6"),
              ("services/database.py + python-oracledb (Thin)", "connections · error translation · config.py (.env)", "#fdeaf1"),
              ("Oracle 21c XE — XEPDB1 / appliance_app", "7 tables · view · procedure · function · trigger", "#e8f5e9")]
    for i, (t, s, c) in enumerate(layers):
        y = 4.2 - i * 1.0
        ax.add_patch(FancyBboxPatch((1.2, y), 8.6, 0.78, boxstyle="round,pad=0,rounding_size=0.1", fc=c, ec=INK, lw=1.3))
        ax.text(5.5, y + 0.5, t, ha="center", va="center", fontsize=12, fontweight="bold", color=INK)
        ax.text(5.5, y + 0.22, s, ha="center", va="center", fontsize=9, color="#333")
        if i < 4:
            ax.add_patch(FancyArrowPatch((5.5, y), (5.5, y - 0.2), arrowstyle="<->", mutation_scale=12, color=CYAN, lw=1.6))
    fig.savefig(os.path.join(OUT, "architecture.png"), dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close(fig)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    er(); arch()
    print("wrote er_diagram.png, architecture.png")
