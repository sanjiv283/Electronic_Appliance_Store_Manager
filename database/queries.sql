-- =====================================================================
-- queries.sql  -  exactly 16 numbered Oracle 21c queries (read-only)
-- Run after schema.sql + seed.sql:  @database/queries.sql
-- Each query: purpose, concept demonstrated, then the statement.
-- =====================================================================
SET LINESIZE 200
SET PAGESIZE 100
SET DEFINE OFF
COLUMN PRODUCT_NAME FORMAT A42
COLUMN FULL_NAME FORMAT A22

-- Query 1: Basic SELECT with filtering and ordering
-- Concept: WHERE, AND, ORDER BY. In-stock products priced above 20,000.
SELECT PRODUCT_ID, PRODUCT_NAME, BRAND, UNIT_PRICE, STOCK_QTY
  FROM PRODUCTS
 WHERE UNIT_PRICE > 20000 AND STOCK_QTY > 0
 ORDER BY UNIT_PRICE DESC;

-- Query 2: Product search by category
-- Concept: IN with a subquery. All products in categories whose name starts with 'Kitchen'/'Small'/'Tele'.
SELECT PRODUCT_NAME, BRAND, MODEL_NO, UNIT_PRICE
  FROM PRODUCTS
 WHERE CATEGORY_ID IN (SELECT CATEGORY_ID FROM CATEGORIES
                        WHERE CATEGORY_NAME LIKE 'Tele%' OR CATEGORY_NAME LIKE 'Small%')
 ORDER BY CATEGORY_ID, PRODUCT_NAME;

-- Query 3: Products with their category (INNER JOIN)
-- Concept: INNER JOIN on PRODUCTS.CATEGORY_ID = CATEGORIES.CATEGORY_ID.
SELECT c.CATEGORY_NAME, p.PRODUCT_NAME, p.UNIT_PRICE
  FROM PRODUCTS p
  INNER JOIN CATEGORIES c ON c.CATEGORY_ID = p.CATEGORY_ID
 ORDER BY c.CATEGORY_NAME, p.PRODUCT_NAME;

-- Query 4: Products with their supplier
-- Concept: JOIN across the PRODUCTS-SUPPLIERS one-to-many relationship.
SELECT s.SUPPLIER_NAME, s.CONTACT_PERSON, p.PRODUCT_NAME, p.STOCK_QTY
  FROM SUPPLIERS s
  JOIN PRODUCTS p ON p.SUPPLIER_ID = s.SUPPLIER_ID
 ORDER BY s.SUPPLIER_NAME, p.PRODUCT_NAME;

-- Query 5: Customers and their sales (including customers with none)
-- Concept: LEFT OUTER JOIN. Customers with no sales show NULL invoice.
SELECT c.FULL_NAME, s.INVOICE_NO, s.SALE_DATE, s.TOTAL_AMOUNT
  FROM CUSTOMERS c
  LEFT JOIN SALES s ON s.CUSTOMER_ID = c.CUSTOMER_ID
 ORDER BY c.FULL_NAME, s.SALE_DATE;

-- Query 6: Employee sales performance
-- Concept: LEFT JOIN + COUNT + SUM per employee.
SELECT e.FULL_NAME, e.JOB_TITLE, COUNT(s.SALE_ID) AS SALES_HANDLED,
       NVL(SUM(s.TOTAL_AMOUNT), 0) AS SALES_VALUE
  FROM EMPLOYEES e
  LEFT JOIN SALES s ON s.EMPLOYEE_ID = e.EMPLOYEE_ID
 GROUP BY e.EMPLOYEE_ID, e.FULL_NAME, e.JOB_TITLE
 ORDER BY SALES_VALUE DESC;

-- Query 7: Full invoice lines (five-table JOIN)
-- Concept: SALES - CUSTOMERS - EMPLOYEES - SALE_ITEMS - PRODUCTS.
SELECT s.INVOICE_NO, TO_CHAR(s.SALE_DATE, 'YYYY-MM-DD') AS SALE_DAY,
       c.FULL_NAME AS CUSTOMER, e.FULL_NAME AS EMPLOYEE,
       p.PRODUCT_NAME, si.QUANTITY, si.UNIT_PRICE, si.LINE_TOTAL
  FROM SALES s
  JOIN CUSTOMERS  c  ON c.CUSTOMER_ID = s.CUSTOMER_ID
  JOIN EMPLOYEES  e  ON e.EMPLOYEE_ID = s.EMPLOYEE_ID
  JOIN SALE_ITEMS si ON si.SALE_ID    = s.SALE_ID
  JOIN PRODUCTS   p  ON p.PRODUCT_ID  = si.PRODUCT_ID
 ORDER BY s.SALE_DATE, s.INVOICE_NO, p.PRODUCT_NAME;

-- Query 8: Number of products per category
-- Concept: GROUP BY with COUNT (LEFT JOIN keeps empty categories).
SELECT c.CATEGORY_NAME, COUNT(p.PRODUCT_ID) AS PRODUCT_COUNT
  FROM CATEGORIES c
  LEFT JOIN PRODUCTS p ON p.CATEGORY_ID = c.CATEGORY_ID
 GROUP BY c.CATEGORY_ID, c.CATEGORY_NAME
 ORDER BY PRODUCT_COUNT DESC, c.CATEGORY_NAME;

-- Query 9: Monthly sales revenue
-- Concept: SUM / COUNT / AVG aggregation grouped by a date expression.
SELECT TO_CHAR(SALE_DATE, 'YYYY-MM') AS SALE_MONTH,
       COUNT(*) AS SALES_COUNT,
       SUM(TOTAL_AMOUNT) AS REVENUE,
       ROUND(AVG(TOTAL_AMOUNT), 2) AS AVG_SALE
  FROM SALES
 GROUP BY TO_CHAR(SALE_DATE, 'YYYY-MM')
 ORDER BY SALE_MONTH;

-- Query 10: Categories with revenue above 50,000
-- Concept: HAVING filters groups after aggregation.
SELECT c.CATEGORY_NAME, SUM(si.LINE_TOTAL) AS CATEGORY_REVENUE
  FROM SALE_ITEMS si
  JOIN PRODUCTS   p ON p.PRODUCT_ID  = si.PRODUCT_ID
  JOIN CATEGORIES c ON c.CATEGORY_ID = p.CATEGORY_ID
 GROUP BY c.CATEGORY_ID, c.CATEGORY_NAME
HAVING SUM(si.LINE_TOTAL) > 50000
 ORDER BY CATEGORY_REVENUE DESC;

-- Query 11: Products priced above the overall average
-- Concept: scalar subquery (returns one value, evaluated once).
SELECT PRODUCT_NAME, UNIT_PRICE,
       (SELECT ROUND(AVG(UNIT_PRICE), 2) FROM PRODUCTS) AS AVG_PRICE
  FROM PRODUCTS
 WHERE UNIT_PRICE > (SELECT AVG(UNIT_PRICE) FROM PRODUCTS)
 ORDER BY UNIT_PRICE DESC;

-- Query 12: Products priced above the average of their OWN category
-- Concept: correlated subquery (inner query references the outer row).
SELECT p.PRODUCT_NAME, p.CATEGORY_ID, p.UNIT_PRICE
  FROM PRODUCTS p
 WHERE p.UNIT_PRICE > (SELECT AVG(p2.UNIT_PRICE)
                         FROM PRODUCTS p2
                        WHERE p2.CATEGORY_ID = p.CATEGORY_ID)
 ORDER BY p.CATEGORY_ID, p.UNIT_PRICE DESC;

-- Query 13: Products that have never been sold
-- Concept: NOT EXISTS anti-join (dead stock report).
SELECT p.PRODUCT_ID, p.PRODUCT_NAME, p.STOCK_QTY
  FROM PRODUCTS p
 WHERE NOT EXISTS (SELECT 1 FROM SALE_ITEMS si WHERE si.PRODUCT_ID = p.PRODUCT_ID)
 ORDER BY p.PRODUCT_NAME;

-- Query 14: Top 5 best-selling products by units sold
-- Concept: aggregation + ORDER BY + FETCH FIRST (Oracle 12c+ row limiting).
SELECT p.PRODUCT_NAME, SUM(si.QUANTITY) AS UNITS_SOLD, SUM(si.LINE_TOTAL) AS REVENUE
  FROM SALE_ITEMS si
  JOIN PRODUCTS p ON p.PRODUCT_ID = si.PRODUCT_ID
 GROUP BY p.PRODUCT_ID, p.PRODUCT_NAME
 ORDER BY UNITS_SOLD DESC, REVENUE DESC
 FETCH FIRST 5 ROWS ONLY;

-- Query 15: Customer spending ranking
-- Concept: LEFT JOIN, aggregation and the RANK() analytic function.
SELECT c.FULL_NAME, COUNT(s.SALE_ID) AS PURCHASES,
       NVL(SUM(s.TOTAL_AMOUNT), 0) AS TOTAL_SPENT,
       RANK() OVER (ORDER BY NVL(SUM(s.TOTAL_AMOUNT), 0) DESC) AS SPEND_RANK
  FROM CUSTOMERS c
  LEFT JOIN SALES s ON s.CUSTOMER_ID = c.CUSTOMER_ID
 GROUP BY c.CUSTOMER_ID, c.FULL_NAME
 ORDER BY SPEND_RANK, c.FULL_NAME;

-- Query 16: Inventory KPI - stock value and reorder status
-- Concept: CASE expression, arithmetic on columns, per-product KPI.
SELECT PRODUCT_NAME, STOCK_QTY, REORDER_LEVEL,
       STOCK_QTY * UNIT_PRICE AS STOCK_VALUE,
       CASE WHEN STOCK_QTY = 0 THEN 'OUT OF STOCK'
            WHEN STOCK_QTY <= REORDER_LEVEL THEN 'REORDER NOW'
            ELSE 'OK' END AS STATUS
  FROM PRODUCTS
 ORDER BY CASE WHEN STOCK_QTY <= REORDER_LEVEL THEN 0 ELSE 1 END, STOCK_VALUE DESC;
