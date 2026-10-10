-- =====================================================================
-- schema.sql  -  Electronic Appliance Store Management System
-- Oracle Database 21c XE, pluggable DB XEPDB1, run AS appliance_app.
--
-- Run:  sqlplus appliance_app@localhost:1521/XEPDB1 @database/schema.sql
-- Order of the whole setup:
--   1 setup_user.sql (admin, once)  2 schema.sql  3 advanced_features.sql
--   4 seed.sql  5 queries.sql (optional, demo)
--
-- Re-runnable: every CREATE is wrapped so that ONLY "name already used"
-- (ORA-00955) is skipped; any other error aborts the script. No object is
-- dropped, so populated tables are never destroyed by this script.
--
-- Deletion behaviour: all foreign keys are NO ACTION (RESTRICT). Nothing
-- cascades, so historical sales can never vanish because a customer,
-- employee or product row was deleted; Oracle raises ORA-02292 instead and
-- the application reports "record is referenced by other records".
-- Monetary columns are NUMBER(p,2); quantities are whole NUMBERs.
-- =====================================================================
SET SQLBLANKLINES ON
SET DEFINE OFF
SET SERVEROUTPUT ON
WHENEVER SQLERROR EXIT FAILURE ROLLBACK

-- ---------------------------------------------------------------------
-- 1. Tables (parents first)
-- ---------------------------------------------------------------------
DECLARE
  PROCEDURE run_ddl(p_label IN VARCHAR2, p_sql IN VARCHAR2) IS
  BEGIN
    EXECUTE IMMEDIATE p_sql;
    DBMS_OUTPUT.PUT_LINE('created : ' || p_label);
  EXCEPTION
    WHEN OTHERS THEN
      IF SQLCODE = -955 THEN                       -- name already used
        DBMS_OUTPUT.PUT_LINE('exists  : ' || p_label || ' (skipped)');
      ELSE
        RAISE;
      END IF;
  END run_ddl;
BEGIN
  run_ddl('CATEGORIES', q'[
    CREATE TABLE CATEGORIES (
      CATEGORY_ID    NUMBER GENERATED ALWAYS AS IDENTITY,
      CATEGORY_NAME  VARCHAR2(60)  NOT NULL,
      DESCRIPTION    VARCHAR2(255),
      CONSTRAINT PK_CATEGORIES      PRIMARY KEY (CATEGORY_ID),
      CONSTRAINT UQ_CATEGORIES_NAME UNIQUE (CATEGORY_NAME)
    )]');

  run_ddl('SUPPLIERS', q'[
    CREATE TABLE SUPPLIERS (
      SUPPLIER_ID     NUMBER GENERATED ALWAYS AS IDENTITY,
      SUPPLIER_NAME   VARCHAR2(100) NOT NULL,
      CONTACT_PERSON  VARCHAR2(100),
      EMAIL           VARCHAR2(120),
      PHONE           VARCHAR2(20),
      ADDRESS         VARCHAR2(255),
      CONSTRAINT PK_SUPPLIERS      PRIMARY KEY (SUPPLIER_ID),
      CONSTRAINT UQ_SUPPLIERS_NAME UNIQUE (SUPPLIER_NAME)
    )]');

  run_ddl('CUSTOMERS', q'[
    CREATE TABLE CUSTOMERS (
      CUSTOMER_ID  NUMBER GENERATED ALWAYS AS IDENTITY,
      FULL_NAME    VARCHAR2(100) NOT NULL,
      EMAIL        VARCHAR2(120) NOT NULL,
      PHONE        VARCHAR2(20)  NOT NULL,
      ADDRESS      VARCHAR2(255),
      CREATED_AT   TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
      CONSTRAINT PK_CUSTOMERS       PRIMARY KEY (CUSTOMER_ID),
      CONSTRAINT UQ_CUSTOMERS_EMAIL UNIQUE (EMAIL)
    )]');

  run_ddl('EMPLOYEES', q'[
    CREATE TABLE EMPLOYEES (
      EMPLOYEE_ID  NUMBER GENERATED ALWAYS AS IDENTITY,
      FULL_NAME    VARCHAR2(100) NOT NULL,
      EMAIL        VARCHAR2(120) NOT NULL,
      PHONE        VARCHAR2(20),
      JOB_TITLE    VARCHAR2(60)  NOT NULL,
      HIRE_DATE    DATE NOT NULL,
      CONSTRAINT PK_EMPLOYEES       PRIMARY KEY (EMPLOYEE_ID),
      CONSTRAINT UQ_EMPLOYEES_EMAIL UNIQUE (EMAIL)
    )]');

  run_ddl('PRODUCTS', q'[
    CREATE TABLE PRODUCTS (
      PRODUCT_ID       NUMBER GENERATED ALWAYS AS IDENTITY,
      PRODUCT_NAME     VARCHAR2(120) NOT NULL,
      BRAND            VARCHAR2(60)  NOT NULL,
      MODEL_NO         VARCHAR2(40)  NOT NULL,
      CATEGORY_ID      NUMBER NOT NULL,
      SUPPLIER_ID      NUMBER NOT NULL,
      UNIT_PRICE       NUMBER(10,2) NOT NULL,
      STOCK_QTY        NUMBER(8)    DEFAULT 0 NOT NULL,
      REORDER_LEVEL    NUMBER(6)    DEFAULT 5 NOT NULL,
      WARRANTY_MONTHS  NUMBER(3)    DEFAULT 12 NOT NULL,
      CREATED_AT       TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
      CONSTRAINT PK_PRODUCTS          PRIMARY KEY (PRODUCT_ID),
      CONSTRAINT UQ_PRODUCTS_MODEL    UNIQUE (MODEL_NO),
      CONSTRAINT FK_PRODUCTS_CATEGORY FOREIGN KEY (CATEGORY_ID) REFERENCES CATEGORIES (CATEGORY_ID),
      CONSTRAINT FK_PRODUCTS_SUPPLIER FOREIGN KEY (SUPPLIER_ID) REFERENCES SUPPLIERS (SUPPLIER_ID),
      CONSTRAINT CK_PRODUCTS_PRICE    CHECK (UNIT_PRICE >= 0),
      CONSTRAINT CK_PRODUCTS_STOCK    CHECK (STOCK_QTY >= 0),
      CONSTRAINT CK_PRODUCTS_REORDER  CHECK (REORDER_LEVEL >= 0),
      CONSTRAINT CK_PRODUCTS_WARRANTY CHECK (WARRANTY_MONTHS BETWEEN 0 AND 120)
    )]');

  run_ddl('SEQ_INVOICE_NO',
    'CREATE SEQUENCE SEQ_INVOICE_NO START WITH 1000 INCREMENT BY 1 NOCACHE');

  run_ddl('SALES', q'[
    CREATE TABLE SALES (
      SALE_ID         NUMBER GENERATED ALWAYS AS IDENTITY,
      INVOICE_NO      VARCHAR2(20) NOT NULL,
      CUSTOMER_ID     NUMBER NOT NULL,
      EMPLOYEE_ID     NUMBER NOT NULL,
      SALE_DATE       TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
      PAYMENT_METHOD  VARCHAR2(20) NOT NULL,
      TOTAL_AMOUNT    NUMBER(12,2) NOT NULL,
      CONSTRAINT PK_SALES          PRIMARY KEY (SALE_ID),
      CONSTRAINT UQ_SALES_INVOICE  UNIQUE (INVOICE_NO),
      CONSTRAINT FK_SALES_CUSTOMER FOREIGN KEY (CUSTOMER_ID) REFERENCES CUSTOMERS (CUSTOMER_ID),
      CONSTRAINT FK_SALES_EMPLOYEE FOREIGN KEY (EMPLOYEE_ID) REFERENCES EMPLOYEES (EMPLOYEE_ID),
      CONSTRAINT CK_SALES_PAYMENT  CHECK (PAYMENT_METHOD IN ('CASH','CARD','UPI','BANK_TRANSFER')),
      CONSTRAINT CK_SALES_TOTAL    CHECK (TOTAL_AMOUNT > 0)
    )]');

  run_ddl('SALE_ITEMS', q'[
    CREATE TABLE SALE_ITEMS (
      SALE_ITEM_ID  NUMBER GENERATED ALWAYS AS IDENTITY,
      SALE_ID       NUMBER NOT NULL,
      PRODUCT_ID    NUMBER NOT NULL,
      QUANTITY      NUMBER(6)    NOT NULL,
      UNIT_PRICE    NUMBER(10,2) NOT NULL,
      LINE_TOTAL    NUMBER(12,2) NOT NULL,
      CONSTRAINT PK_SALE_ITEMS         PRIMARY KEY (SALE_ITEM_ID),
      CONSTRAINT UQ_SALE_ITEMS_LINE    UNIQUE (SALE_ID, PRODUCT_ID),
      CONSTRAINT FK_SALE_ITEMS_SALE    FOREIGN KEY (SALE_ID)    REFERENCES SALES (SALE_ID),
      CONSTRAINT FK_SALE_ITEMS_PRODUCT FOREIGN KEY (PRODUCT_ID) REFERENCES PRODUCTS (PRODUCT_ID),
      CONSTRAINT CK_SALE_ITEMS_QTY     CHECK (QUANTITY > 0),
      CONSTRAINT CK_SALE_ITEMS_PRICE   CHECK (UNIT_PRICE >= 0),
      CONSTRAINT CK_SALE_ITEMS_TOTAL   CHECK (LINE_TOTAL = QUANTITY * UNIT_PRICE)
    )]');
END;
/

-- ---------------------------------------------------------------------
-- 2. Indexes (foreign-key lookups and report filters).
--    PK/UNIQUE constraints already create their own indexes; SALE_ITEMS
--    (SALE_ID, PRODUCT_ID) is covered by UQ_SALE_ITEMS_LINE.
-- ---------------------------------------------------------------------
DECLARE
  PROCEDURE run_ddl(p_label IN VARCHAR2, p_sql IN VARCHAR2) IS
  BEGIN
    EXECUTE IMMEDIATE p_sql;
    DBMS_OUTPUT.PUT_LINE('created : ' || p_label);
  EXCEPTION
    WHEN OTHERS THEN
      IF SQLCODE = -955 THEN
        DBMS_OUTPUT.PUT_LINE('exists  : ' || p_label || ' (skipped)');
      ELSE
        RAISE;
      END IF;
  END run_ddl;
BEGIN
  run_ddl('IX_PRODUCTS_CATEGORY',  'CREATE INDEX IX_PRODUCTS_CATEGORY  ON PRODUCTS (CATEGORY_ID)');
  run_ddl('IX_PRODUCTS_SUPPLIER',  'CREATE INDEX IX_PRODUCTS_SUPPLIER  ON PRODUCTS (SUPPLIER_ID)');
  run_ddl('IX_SALES_CUSTOMER',     'CREATE INDEX IX_SALES_CUSTOMER     ON SALES (CUSTOMER_ID)');
  run_ddl('IX_SALES_EMPLOYEE',     'CREATE INDEX IX_SALES_EMPLOYEE     ON SALES (EMPLOYEE_ID)');
  run_ddl('IX_SALES_DATE',         'CREATE INDEX IX_SALES_DATE         ON SALES (SALE_DATE)');
  run_ddl('IX_SALE_ITEMS_PRODUCT', 'CREATE INDEX IX_SALE_ITEMS_PRODUCT ON SALE_ITEMS (PRODUCT_ID)');
END;
/

-- ---------------------------------------------------------------------
-- 3. Verification
-- ---------------------------------------------------------------------
SELECT TABLE_NAME FROM USER_TABLES ORDER BY TABLE_NAME;
SELECT TABLE_NAME, CONSTRAINT_NAME, CONSTRAINT_TYPE
  FROM USER_CONSTRAINTS
 WHERE TABLE_NAME IN ('CATEGORIES','SUPPLIERS','PRODUCTS','CUSTOMERS','EMPLOYEES','SALES','SALE_ITEMS')
 ORDER BY TABLE_NAME, CONSTRAINT_TYPE, CONSTRAINT_NAME;
