# 10-Minute Faculty Demonstration Guide

Presenter: Sanjiv Shine Fernandas · Subject: DBMS · Review 2

**Legend:** 🔌 = needs a live Oracle connection. 📄 = can be shown from local files/artifacts only (no database).

If Oracle is unreachable on the day, run only 📄 items and the unit tests; say clearly that live items were not demonstrated. Never claim a connection that `python -m services.database` did not report.

## Time plan

| Min | Section | Type |
|---|---|---|
| 0:00–0:45 | 1. Startup | 🔌 |
| 0:45–2:15 | 2. Schema, keys, constraints | 📄 + 🔌 |
| 2:15–3:00 | 3. Sample data | 🔌 |
| 3:00–4:45 | 4. Joins, subqueries, aggregations | 🔌 (queries in 📄) |
| 4:45–5:45 | 5. PL/SQL objects | 🔌 |
| 5:45–6:30 | 6. Flask ↔ Oracle connectivity | 🔌 |
| 6:30–7:15 | 7. CRUD | 🔌 |
| 7:15–8:30 | 8. Sale transaction and stock deduction | 🔌 |
| 8:30–9:15 | 9. Testing evidence | 📄 (unit) / 🔌 (integration) |
| 9:15–10:00 | 10. Questions | — |

## 1. Startup (0:45) 🔌

```powershell
.\.venv\Scripts\Activate.ps1
python -m services.database      # expect: OK: Connected as APPLIANCE_APP to service XEPDB1
python app.py                    # open http://127.0.0.1:5000
```
Say: configuration comes from `.env` (git-ignored); the app connects only as `appliance_app`.

## 2. Schema, keys, constraints (1:30) 📄 + 🔌

📄 Open `database/schema.sql`: seven tables, identity PKs, FKs, `CK_PRODUCTS_PRICE/STOCK`, `CK_SALE_ITEMS_TOTAL`, `UQ_*`.

🔌 In SQL*Plus as `appliance_app`:
```sql
SELECT table_name FROM user_tables ORDER BY 1;
SELECT constraint_name, constraint_type, table_name FROM user_constraints
 WHERE table_name IN ('PRODUCTS','SALES','SALE_ITEMS') ORDER BY table_name, constraint_type;
```
Constraint demonstrations (each fails; nothing is changed):
```sql
-- CHECK: negative price  -> ORA-02290
INSERT INTO PRODUCTS (PRODUCT_NAME,BRAND,MODEL_NO,CATEGORY_ID,SUPPLIER_ID,UNIT_PRICE)
 SELECT 'x','x','NEG-1',MIN(CATEGORY_ID),(SELECT MIN(SUPPLIER_ID) FROM SUPPLIERS),-5 FROM CATEGORIES;
-- FK: unknown category -> ORA-02291
INSERT INTO PRODUCTS (PRODUCT_NAME,BRAND,MODEL_NO,CATEGORY_ID,SUPPLIER_ID,UNIT_PRICE)
 VALUES ('x','x','FK-1',-1,(SELECT MIN(SUPPLIER_ID) FROM SUPPLIERS),10);
-- UNIQUE: duplicate model number -> ORA-00001
INSERT INTO PRODUCTS (PRODUCT_NAME,BRAND,MODEL_NO,CATEGORY_ID,SUPPLIER_ID,UNIT_PRICE)
 SELECT 'x','x','ARC-RF260',CATEGORY_ID,SUPPLIER_ID,10 FROM PRODUCTS WHERE MODEL_NO='ARC-RF260';
-- RESTRICT: customer with sales cannot be deleted -> ORA-02292
DELETE FROM CUSTOMERS WHERE EMAIL='anita.rao@demo-mail.example.com';
ROLLBACK;
```
Talking points: PK = unique identity of a row (identity column); FK = relationship integrity (Products→Categories, Sales→Customers, Sale_Items→Sales/Products); FKs never cascade, so sales history cannot disappear; `SALE_ITEMS.UNIT_PRICE` stores the price *at sale time* (3NF-safe history).

## 3. Sample data (0:45) 🔌

```sql
SELECT 'PRODUCTS' t, COUNT(*) FROM PRODUCTS UNION ALL SELECT 'SALES', COUNT(*) FROM SALES
UNION ALL SELECT 'SALE_ITEMS', COUNT(*) FROM SALE_ITEMS;   -- 14 / 8 / 15 on a fresh seed
```
Fictional data only (example.com e-mails). `seed.sql` is re-runnable (MERGE).

## 4. Joins, subqueries, aggregations (1:45) 🔌

Run from `database/queries.sql` (16 numbered queries; the file is a 📄 artifact). Suggested four: **Q7** (5-table join), **Q10** (GROUP BY … HAVING), **Q12** (correlated subquery), **Q13** (NOT EXISTS). Expected highlights: Q13 returns `VV-TV32` and `AU-EK18` (never sold); Q10 returns Televisions, Air Conditioners and Washing Machines.

## 5. PL/SQL objects (1:00) 🔌

```sql
SELECT INVOICE_NO, LINE_COUNT, TOTAL_AMOUNT, TOTAL_MATCHES FROM V_SALES_SUMMARY;   -- view
SELECT FULL_NAME, FN_CUSTOMER_TOTAL_SPEND(CUSTOMER_ID) FROM CUSTOMERS;             -- function
SELECT PRODUCT_ID, STOCK_QTY FROM PRODUCTS WHERE MODEL_NO='KP-MG75';           -- note the id
EXEC SP_RESTOCK_PRODUCT(&id, 10);   -- stock +10 (SQL*Plus prompts for the id)
SELECT STOCK_QTY FROM PRODUCTS WHERE MODEL_NO='KP-MG75';
ROLLBACK;
DELETE FROM SALES WHERE INVOICE_NO='INV-000001';   -- trigger -> ORA-20030
ROLLBACK;
```
Alternatively run `@database\advanced_features.sql`: its closing verification blocks exercise the procedure (success + 3 error cases), the function and the trigger, print the results, and roll back.

## 6. Flask ↔ Oracle connectivity (0:45) 🔌

Browser: `/health` → `{"database":"ok", …}`. Show `config.py` (env-only, rejects SYS/SYSTEM, placeholders count as missing) and `services/database.py` (bind variables, sanitized errors). Optional: stop the listener and reload `/health` → 503 with an honest message, no fake dashboard numbers.

## 7. CRUD (0:45) 🔌

Customers → add "Demo Student" → edit phone → delete (confirmation dialog). Try deleting "Anita Rao" → friendly 409 message (history protected). Try price `-5` on a product → 400 message.

## 8. Sale transaction (1:15) 🔌

1. Products page: note stock of *KitchenPro Mixer Grinder* (25) and *CoolBreeze Window AC* (2).
2. New Sale: customer + employee, add Mixer ×2 and Window AC ×1 → Record sale. Invoice page shows DB prices and total.
3. Products page: stock now 23 and 1 (deducted once, in the service transaction — the trigger touches no inventory).
4. New Sale: Window AC ×5 → rejected, HTTP 409 "Insufficient stock"; stock unchanged (rolled back).
5. SQL proof: `SELECT * FROM V_SALES_SUMMARY ORDER BY SALE_ID DESC;` → `TOTAL_MATCHES = Y`.

Explain: `SELECT … FOR UPDATE WAIT 10` in ascending product order (no deadlock), re-check stock after locks, insert sale + items, deduct stock, single `COMMIT`; any exception → `ROLLBACK`.

## 9. Testing evidence (0:45)

📄 `python -m pytest tests -v` → unit + route tests PASSED; live tests listed as BLOCKED if no test schema is configured.
🔌 With the test schema variables set (README §9): `python -m pytest tests\test_oracle_integration.py -v` — includes the 8-thread overselling test (exactly 5 of 8 purchases succeed when stock is 5).
Show the matrix in `docs/Review_2_Report.md` §24 — statuses are generated from the real result file.

## 10. Likely questions

- **Why is the total stored in SALES if it can be computed?** Historical snapshot + fast reporting; the view `V_SALES_SUMMARY` and the service verify it equals the sum of lines (a controlled, documented redundancy).
- **Why copy price into SALE_ITEMS?** Product prices change; history must not (otherwise a 2NF/3NF-looking design would silently rewrite old invoices).
- **How do you prevent overselling?** Row locks + stock re-check inside one transaction; CHECK `STOCK_QTY >= 0` is the last line of defence.
- **Why not a trigger for stock deduction?** One deduction point (service) avoids double deduction and keeps logic testable.
- **SQL injection?** Only bind variables; user text never concatenated; tested.
- **Why no login?** Out of academic scope; documented limitation — run on localhost.
- **Is it 3NF?** Yes — see report §14 for the functional dependencies per table.
- **What did you not verify?** Whatever the testing matrix labels BLOCKED/NOT RUN; be explicit.
