from . import database as db


def dashboard():
    stats = db.fetch_one(
        "SELECT (SELECT COUNT(*) FROM PRODUCTS) AS PRODUCTS, (SELECT COUNT(*) FROM CUSTOMERS) AS CUSTOMERS, "
        "(SELECT COUNT(*) FROM SALES) AS SALES, (SELECT NVL(SUM(TOTAL_AMOUNT), 0) FROM SALES) AS REVENUE, "
        "(SELECT COUNT(*) FROM PRODUCTS WHERE STOCK_QTY <= REORDER_LEVEL) AS LOW_STOCK FROM DUAL")
    recent = db.fetch_all("SELECT SALE_ID, INVOICE_NO, SALE_DATE, CUSTOMER_NAME, TOTAL_AMOUNT FROM V_SALES_SUMMARY "
                          "ORDER BY SALE_DATE DESC, SALE_ID DESC FETCH FIRST 5 ROWS ONLY")
    return {"stats": stats, "recent": recent}


def inventory():
    return db.fetch_all(
        "SELECT p.PRODUCT_NAME, c.CATEGORY_NAME, p.STOCK_QTY, p.REORDER_LEVEL, p.UNIT_PRICE, "
        "p.STOCK_QTY * p.UNIT_PRICE AS STOCK_VALUE, "
        "CASE WHEN p.STOCK_QTY = 0 THEN 'OUT OF STOCK' WHEN p.STOCK_QTY <= p.REORDER_LEVEL THEN 'REORDER NOW' "
        "ELSE 'OK' END AS STATUS "
        "FROM PRODUCTS p JOIN CATEGORIES c ON c.CATEGORY_ID = p.CATEGORY_ID "
        "ORDER BY CASE WHEN p.STOCK_QTY <= p.REORDER_LEVEL THEN 0 ELSE 1 END, STOCK_VALUE DESC")


def sales_by_month():
    return db.fetch_all("SELECT TO_CHAR(SALE_DATE, 'YYYY-MM') AS SALE_MONTH, COUNT(*) AS SALES_COUNT, "
                        "SUM(TOTAL_AMOUNT) AS REVENUE FROM SALES GROUP BY TO_CHAR(SALE_DATE, 'YYYY-MM') "
                        "ORDER BY SALE_MONTH DESC")


def top_products(limit=5):
    return db.fetch_all("SELECT p.PRODUCT_NAME, SUM(si.QUANTITY) AS UNITS_SOLD, SUM(si.LINE_TOTAL) AS REVENUE "
                        "FROM SALE_ITEMS si JOIN PRODUCTS p ON p.PRODUCT_ID = si.PRODUCT_ID "
                        "GROUP BY p.PRODUCT_ID, p.PRODUCT_NAME ORDER BY UNITS_SOLD DESC, REVENUE DESC "
                        "FETCH FIRST :n ROWS ONLY", {"n": int(limit)})


def category_revenue():
    return db.fetch_all("SELECT c.CATEGORY_NAME, SUM(si.LINE_TOTAL) AS REVENUE FROM SALE_ITEMS si "
                        "JOIN PRODUCTS p ON p.PRODUCT_ID = si.PRODUCT_ID "
                        "JOIN CATEGORIES c ON c.CATEGORY_ID = p.CATEGORY_ID "
                        "GROUP BY c.CATEGORY_ID, c.CATEGORY_NAME ORDER BY REVENUE DESC")


def customer_summary():
    return db.fetch_all("SELECT c.CUSTOMER_ID, c.FULL_NAME, COUNT(s.SALE_ID) AS PURCHASES, "
                        "NVL(SUM(s.TOTAL_AMOUNT), 0) AS TOTAL_SPENT, MAX(s.SALE_DATE) AS LAST_PURCHASE "
                        "FROM CUSTOMERS c LEFT JOIN SALES s ON s.CUSTOMER_ID = c.CUSTOMER_ID "
                        "GROUP BY c.CUSTOMER_ID, c.FULL_NAME ORDER BY TOTAL_SPENT DESC, c.FULL_NAME")
