-- ============================================================
-- SHOW_ALL_TABLES_STRUCTURE.sql
-- Script para mostrar a estrutura de todas as tabelas do seed
-- Execute: mysql -u root -p supply_chain_mecanica < SHOW_ALL_TABLES_STRUCTURE.sql
-- ============================================================

USE supply_chain_mecanica;

-- Tabelas usadas no seed
SELECT '=== 1. product_categories ===' AS 'TABELA';
DESCRIBE product_categories;

SELECT '=== 2. product_brands ===' AS 'TABELA';
DESCRIBE product_brands;

SELECT '=== 3. suppliers ===' AS 'TABELA';
DESCRIBE suppliers;

SELECT '=== 4. customers ===' AS 'TABELA';
DESCRIBE customers;

SELECT '=== 5. equipment ===' AS 'TABELA';
DESCRIBE equipment;

SELECT '=== 6. technicians ===' AS 'TABELA';
DESCRIBE technicians;

SELECT '=== 7. sellers ===' AS 'TABELA';
DESCRIBE sellers;

SELECT '=== 8. products ===' AS 'TABELA';
DESCRIBE products;

SELECT '=== 9. sales_routes ===' AS 'TABELA';
DESCRIBE sales_routes;

SELECT '=== 10. service_orders ===' AS 'TABELA';
DESCRIBE service_orders;

SELECT '=== 11. service_order_items ===' AS 'TABELA';
DESCRIBE service_order_items;

SELECT '=== 12. accounts_receivable ===' AS 'TABELA';
DESCRIBE accounts_receivable;

SELECT '=== 13. accounts_payable ===' AS 'TABELA';
DESCRIBE accounts_payable;

SELECT '=== 14. sales ===' AS 'TABELA';
DESCRIBE sales;

SELECT '=== 15. kardex ===' AS 'TABELA';
DESCRIBE kardex;

SELECT '=== 16. chart_of_accounts ===' AS 'TABELA';
DESCRIBE chart_of_accounts;

SELECT '=== 17. cash_register ===' AS 'TABELA';
DESCRIBE cash_register;

SELECT '=== 18. cash_flow ===' AS 'TABELA';
DESCRIBE cash_flow;

SELECT '=== 19. commissions ===' AS 'TABELA';
DESCRIBE commissions;

SELECT '=== 20. warranties ===' AS 'TABELA';
DESCRIBE warranties;

SELECT '=== 21. maintenance_plans ===' AS 'TABELA';
DESCRIBE maintenance_plans;

SELECT '=== 22. hour_meter_readings ===' AS 'TABELA';
DESCRIBE hour_meter_readings;

SELECT '=== 23. time_entries ===' AS 'TABELA';
DESCRIBE time_entries;

SELECT '=== 24. invoices ===' AS 'TABELA';
DESCRIBE invoices;
