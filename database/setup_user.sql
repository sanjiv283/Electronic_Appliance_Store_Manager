-- =====================================================================
-- setup_user.sql  -  ONE-TIME ADMINISTRATOR SETUP (manual, never run by Flask)
--
-- Run ONCE as an administrator (SYS AS SYSDBA or SYSTEM) from SQL*Plus:
--     sqlplus / as sysdba
--     SQL> @database/setup_user.sql
--
-- Creates the least-privilege application account in the PLUGGABLE
-- database XEPDB1 (not in CDB$ROOT). The password is typed at the prompt
-- (hidden) and is never stored in this file. Run again with another user
-- name (e.g. appliance_test) to create a separate schema for integration
-- tests. The account gets NO DBA / SYSDBA / ANY-privileges.
-- =====================================================================
WHENEVER SQLERROR EXIT FAILURE
ALTER SESSION SET CONTAINER = XEPDB1;

ACCEPT app_user CHAR DEFAULT 'appliance_app' PROMPT 'Application user name [appliance_app]: '
ACCEPT app_password CHAR PROMPT 'Password for the new user (hidden): ' HIDE

CREATE USER &&app_user IDENTIFIED BY "&&app_password"
  DEFAULT TABLESPACE USERS
  TEMPORARY TABLESPACE TEMP
  QUOTA UNLIMITED ON USERS;

-- Minimum rights: connect and create/own the objects in schema.sql and
-- advanced_features.sql (tables, indexes, sequence, view, procedure,
-- function, trigger). Identity columns need no extra privilege beyond these.
GRANT CREATE SESSION   TO &&app_user;
GRANT CREATE TABLE     TO &&app_user;
GRANT CREATE SEQUENCE  TO &&app_user;
GRANT CREATE VIEW      TO &&app_user;
GRANT CREATE PROCEDURE TO &&app_user;
GRANT CREATE TRIGGER   TO &&app_user;

UNDEFINE app_password
-- Verify (expected: only the six privileges above):
SELECT PRIVILEGE FROM DBA_SYS_PRIVS WHERE GRANTEE = UPPER('&&app_user') ORDER BY 1;
