-- =====================================================================
-- advanced_features.sql  -  exactly four objects: VIEW, PROCEDURE,
-- FUNCTION, TRIGGER.  Run as appliance_app AFTER schema.sql:
--     @database/advanced_features.sql
-- CREATE OR REPLACE makes it re-runnable (replaces code, never data).
-- Verification sections end in ROLLBACK, so running them changes nothing.
-- =====================================================================
SET SQLBLANKLINES ON
SET DEFINE OFF
SET SERVEROUTPUT ON
SET LINESIZE 200

-- ---------------------------------------------------------------------
-- 1. VIEW  V_SALES_SUMMARY
-- Purpose: one row per sale with customer, employee, line/unit counts and
--          a check that stored TOTAL_AMOUNT equals the sum of its lines.
--          Used by the Flask sales-history page.
-- Expected: sales with no items still appear (LEFT JOIN, 0 lines).
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW V_SALES_SUMMARY AS
SELECT s.SALE_ID, s.INVOICE_NO, s.SALE_DATE, s.PAYMENT_METHOD,
       s.CUSTOMER_ID, c.FULL_NAME AS CUSTOMER_NAME,
       s.EMPLOYEE_ID, e.FULL_NAME AS EMPLOYEE_NAME,
       COUNT(si.SALE_ITEM_ID)        AS LINE_COUNT,
       NVL(SUM(si.QUANTITY), 0)      AS UNIT_COUNT,
       s.TOTAL_AMOUNT,
       CASE WHEN s.TOTAL_AMOUNT = NVL(SUM(si.LINE_TOTAL), 0) THEN 'Y' ELSE 'N' END AS TOTAL_MATCHES
  FROM SALES s
  JOIN CUSTOMERS c ON c.CUSTOMER_ID = s.CUSTOMER_ID
  JOIN EMPLOYEES e ON e.EMPLOYEE_ID = s.EMPLOYEE_ID
  LEFT JOIN SALE_ITEMS si ON si.SALE_ID = s.SALE_ID
 GROUP BY s.SALE_ID, s.INVOICE_NO, s.SALE_DATE, s.PAYMENT_METHOD,
          s.CUSTOMER_ID, c.FULL_NAME, s.EMPLOYEE_ID, e.FULL_NAME, s.TOTAL_AMOUNT;

-- Verify: every seeded sale should show TOTAL_MATCHES = 'Y'
SELECT INVOICE_NO, CUSTOMER_NAME, LINE_COUNT, UNIT_COUNT, TOTAL_AMOUNT, TOTAL_MATCHES
  FROM V_SALES_SUMMARY ORDER BY SALE_ID;

-- ---------------------------------------------------------------------
-- 2. STORED PROCEDURE  SP_RESTOCK_PRODUCT(p_product_id, p_quantity)
-- Purpose: add received stock to a product under a row lock. Used by the
--          Flask "Restock" button. It does NOT commit - the caller owns
--          the transaction boundary.
-- Errors : ORA-20001 quantity not a positive whole number
--          ORA-20002 product does not exist
--          (ORA-01438 if the new stock would exceed NUMBER(8))
-- ---------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE SP_RESTOCK_PRODUCT (
  p_product_id IN NUMBER,
  p_quantity   IN NUMBER
) AS
  v_stock PRODUCTS.STOCK_QTY%TYPE;
BEGIN
  IF p_quantity IS NULL OR p_quantity <= 0 OR p_quantity <> TRUNC(p_quantity) THEN
    RAISE_APPLICATION_ERROR(-20001, 'Restock quantity must be a positive whole number.');
  END IF;

  SELECT STOCK_QTY INTO v_stock
    FROM PRODUCTS
   WHERE PRODUCT_ID = p_product_id
     FOR UPDATE;

  UPDATE PRODUCTS SET STOCK_QTY = v_stock + p_quantity
   WHERE PRODUCT_ID = p_product_id;
EXCEPTION
  WHEN NO_DATA_FOUND THEN
    RAISE_APPLICATION_ERROR(-20002, 'Product ' || p_product_id || ' does not exist.');
END SP_RESTOCK_PRODUCT;
/
SHOW ERRORS PROCEDURE SP_RESTOCK_PRODUCT

-- ---------------------------------------------------------------------
-- 3. STORED FUNCTION  FN_CUSTOMER_TOTAL_SPEND(p_customer_id)
-- Purpose: lifetime spend of a customer (0 if they have no sales); usable
--          in SQL (SELECT FN_CUSTOMER_TOTAL_SPEND(1) FROM DUAL) or PL/SQL.
-- Errors : ORA-20010 customer does not exist
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION FN_CUSTOMER_TOTAL_SPEND (
  p_customer_id IN NUMBER
) RETURN NUMBER AS
  v_exists NUMBER;
  v_total  NUMBER;
BEGIN
  SELECT COUNT(*) INTO v_exists FROM CUSTOMERS WHERE CUSTOMER_ID = p_customer_id;
  IF v_exists = 0 THEN
    RAISE_APPLICATION_ERROR(-20010, 'Customer ' || p_customer_id || ' does not exist.');
  END IF;
  SELECT NVL(SUM(TOTAL_AMOUNT), 0) INTO v_total
    FROM SALES WHERE CUSTOMER_ID = p_customer_id;
  RETURN v_total;
END FN_CUSTOMER_TOTAL_SPEND;
/
SHOW ERRORS FUNCTION FN_CUSTOMER_TOTAL_SPEND

-- ---------------------------------------------------------------------
-- 4. INTEGRITY TRIGGER  TRG_SALES_PROTECT_HISTORY
-- Purpose: posted sales are financial history. Block DELETE of a sale and
--          UPDATE of its customer, employee, invoice, date, total or payment.
--          (Stock deduction stays in the Flask service transaction; this
--          trigger touches no inventory.)
-- Errors : ORA-20030 delete blocked, ORA-20031 update blocked
-- Test hook: a session whose CLIENT_INFO is 'ITEST_CLEANUP' is exempt so the
--          integration tests can remove their own rows in a dedicated TEST
--          schema. The application never sets this value. Remove the first
--          IF in a production-style deployment.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TRIGGER TRG_SALES_PROTECT_HISTORY
BEFORE DELETE OR UPDATE OF CUSTOMER_ID, EMPLOYEE_ID, INVOICE_NO, SALE_DATE, TOTAL_AMOUNT, PAYMENT_METHOD
ON SALES
FOR EACH ROW
BEGIN
  IF SYS_CONTEXT('USERENV', 'CLIENT_INFO') = 'ITEST_CLEANUP' THEN
    RETURN;
  END IF;
  IF DELETING THEN
    RAISE_APPLICATION_ERROR(-20030, 'Sales records are historical and cannot be deleted.');
  ELSE
    RAISE_APPLICATION_ERROR(-20031, 'Posted sales cannot be modified.');
  END IF;
END TRG_SALES_PROTECT_HISTORY;
/
SHOW ERRORS TRIGGER TRG_SALES_PROTECT_HISTORY

-- =====================================================================
-- EXAMPLE EXECUTION + VERIFICATION (safe: each block is rolled back)
-- =====================================================================
-- Procedure: success, then three error conditions
DECLARE
  v_id    PRODUCTS.PRODUCT_ID%TYPE;
  v_before PRODUCTS.STOCK_QTY%TYPE;
  v_after  PRODUCTS.STOCK_QTY%TYPE;
BEGIN
  SELECT PRODUCT_ID, STOCK_QTY INTO v_id, v_before FROM PRODUCTS WHERE MODEL_NO = 'KP-MG75';
  SP_RESTOCK_PRODUCT(v_id, 10);
  SELECT STOCK_QTY INTO v_after FROM PRODUCTS WHERE PRODUCT_ID = v_id;
  DBMS_OUTPUT.PUT_LINE('restock OK: ' || v_before || ' -> ' || v_after || ' (expected +10)');
  ROLLBACK;
  BEGIN SP_RESTOCK_PRODUCT(v_id, 0);        EXCEPTION WHEN OTHERS THEN DBMS_OUTPUT.PUT_LINE('qty 0      -> ' || SQLERRM); END;
  BEGIN SP_RESTOCK_PRODUCT(v_id, 2.5);      EXCEPTION WHEN OTHERS THEN DBMS_OUTPUT.PUT_LINE('qty 2.5    -> ' || SQLERRM); END;
  BEGIN SP_RESTOCK_PRODUCT(-999, 5);        EXCEPTION WHEN OTHERS THEN DBMS_OUTPUT.PUT_LINE('bad product -> ' || SQLERRM); END;
  ROLLBACK;
END;
/

-- Function: success and error condition
SELECT c.FULL_NAME, FN_CUSTOMER_TOTAL_SPEND(c.CUSTOMER_ID) AS LIFETIME_SPEND
  FROM CUSTOMERS c ORDER BY c.CUSTOMER_ID;
BEGIN
  DBMS_OUTPUT.PUT_LINE(FN_CUSTOMER_TOTAL_SPEND(-999));
EXCEPTION WHEN OTHERS THEN DBMS_OUTPUT.PUT_LINE('bad customer -> ' || SQLERRM);
END;
/

-- Trigger: both attempts must be rejected (expected ORA-20030 / ORA-20031)
BEGIN
  DELETE FROM SALES WHERE INVOICE_NO = 'INV-000001';
EXCEPTION WHEN OTHERS THEN DBMS_OUTPUT.PUT_LINE('delete sale -> ' || SQLERRM);
END;
/
BEGIN
  UPDATE SALES SET TOTAL_AMOUNT = TOTAL_AMOUNT + 1 WHERE INVOICE_NO = 'INV-000001';
EXCEPTION WHEN OTHERS THEN DBMS_OUTPUT.PUT_LINE('update sale -> ' || SQLERRM);
END;
/
ROLLBACK;

-- Inspect object status (all four must be VALID)
SELECT OBJECT_NAME, OBJECT_TYPE, STATUS FROM USER_OBJECTS
 WHERE OBJECT_NAME IN ('V_SALES_SUMMARY','SP_RESTOCK_PRODUCT','FN_CUSTOMER_TOTAL_SPEND','TRG_SALES_PROTECT_HISTORY')
 ORDER BY OBJECT_TYPE;
