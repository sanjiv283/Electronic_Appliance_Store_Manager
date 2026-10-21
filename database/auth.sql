-- =====================================================================
-- auth.sql  -  REVIEW 3: application users and roles (8th table: USERS)
-- Run as appliance_app AFTER schema.sql:
--     sqlplus appliance_app@localhost:1521/XEPDB1 @database\auth.sql
--
-- Re-runnable (only ORA-00955 "name already used" is tolerated). No data is
-- inserted here: there are NO default accounts or passwords. Create the first
-- manager with  python manage.py create-user  (password typed at a hidden prompt).
--
-- Roles: MANAGER (everything) and CASHIER (sales, customers, read-only products).
-- Passwords are stored only as salted hashes (Werkzeug scrypt), never in clear text.
-- A user belongs to exactly one employee, so every sale is attributable.
-- =====================================================================
SET SQLBLANKLINES ON
SET DEFINE OFF
SET SERVEROUTPUT ON
SET LINESIZE 160
WHENEVER SQLERROR EXIT FAILURE ROLLBACK

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
  run_ddl('USERS', q'[
    CREATE TABLE USERS (
      USER_ID        NUMBER GENERATED ALWAYS AS IDENTITY,
      USERNAME       VARCHAR2(40)  NOT NULL,
      PASSWORD_HASH  VARCHAR2(255) NOT NULL,
      ROLE           VARCHAR2(10)  NOT NULL,
      EMPLOYEE_ID    NUMBER        NOT NULL,
      CREATED_AT     TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
      LAST_LOGIN     TIMESTAMP,
      CONSTRAINT PK_USERS          PRIMARY KEY (USER_ID),
      CONSTRAINT UQ_USERS_USERNAME UNIQUE (USERNAME),
      CONSTRAINT UQ_USERS_EMPLOYEE UNIQUE (EMPLOYEE_ID),
      CONSTRAINT FK_USERS_EMPLOYEE FOREIGN KEY (EMPLOYEE_ID) REFERENCES EMPLOYEES (EMPLOYEE_ID),
      CONSTRAINT CK_USERS_ROLE     CHECK (ROLE IN ('MANAGER','CASHIER')),
      CONSTRAINT CK_USERS_NAME     CHECK (USERNAME = LOWER(USERNAME))
    )]');
END;
/

-- Verification: expected 8 tables; USERS has PK, 2 UNIQUE, 1 FK and 2 CHECK constraints
COLUMN TABLE_NAME FORMAT A14
COLUMN CONSTRAINT_NAME FORMAT A24
SELECT TABLE_NAME FROM USER_TABLES ORDER BY TABLE_NAME;
SELECT CONSTRAINT_NAME, CONSTRAINT_TYPE FROM USER_CONSTRAINTS
 WHERE TABLE_NAME = 'USERS' AND CONSTRAINT_NAME NOT LIKE 'SYS_C%' ORDER BY CONSTRAINT_TYPE, CONSTRAINT_NAME;
