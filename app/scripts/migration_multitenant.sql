-- ============================================================
-- Migration: Multi-Tenant (company_id) — IKFlow Mecânica
-- Compatível com MySQL 5.7+
-- Executar: mysql -u ikflow -p'IkFl0w@2024!DB' supply_chain_mecanica < app/scripts/migration_multitenant.sql
-- ============================================================

DROP PROCEDURE IF EXISTS migration_multitenant;

DELIMITER //
CREATE PROCEDURE migration_multitenant()
BEGIN

  -- ── 1. Garante que a tabela companies existe ───────────────────────────────
  CREATE TABLE IF NOT EXISTS companies (
    id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(200) NOT NULL,
    cnpj        VARCHAR(20)  NULL,
    phone       VARCHAR(20)  NULL,
    email       VARCHAR(120) NULL,
    address     VARCHAR(300) NULL,
    logo_url    VARCHAR(300) NULL,
    active      TINYINT(1)   NOT NULL DEFAULT 1,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
  ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

  -- Insere empresa padrão se vazia
  INSERT IGNORE INTO companies (id, name) VALUES (1, 'Oficina Principal');

  -- ── 2. Tabelas críticas: adicionar company_id ──────────────────────────────

  -- customers
  IF NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='customers' AND COLUMN_NAME='company_id') THEN
    ALTER TABLE customers ADD COLUMN company_id INT UNSIGNED NOT NULL DEFAULT 1 AFTER id;
    ALTER TABLE customers ADD INDEX idx_customers_company (company_id);
    UPDATE customers SET company_id = 1 WHERE company_id IS NULL OR company_id = 0;
  END IF;

  -- equipment (veículos)
  IF NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='equipment' AND COLUMN_NAME='company_id') THEN
    ALTER TABLE equipment ADD COLUMN company_id INT UNSIGNED NOT NULL DEFAULT 1 AFTER id;
    ALTER TABLE equipment ADD INDEX idx_equipment_company (company_id);
    UPDATE equipment SET company_id = 1 WHERE company_id IS NULL OR company_id = 0;
  END IF;

  -- service_orders
  IF NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='service_orders' AND COLUMN_NAME='company_id') THEN
    ALTER TABLE service_orders ADD COLUMN company_id INT UNSIGNED NOT NULL DEFAULT 1 AFTER id;
    ALTER TABLE service_orders ADD INDEX idx_so_company (company_id);
    UPDATE service_orders SET company_id = 1 WHERE company_id IS NULL OR company_id = 0;
  END IF;

  -- technicians
  IF NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='technicians' AND COLUMN_NAME='company_id') THEN
    ALTER TABLE technicians ADD COLUMN company_id INT UNSIGNED NOT NULL DEFAULT 1 AFTER id;
    ALTER TABLE technicians ADD INDEX idx_technicians_company (company_id);
    UPDATE technicians SET company_id = 1 WHERE company_id IS NULL OR company_id = 0;
  END IF;

  -- inventory
  IF NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='inventory' AND COLUMN_NAME='company_id') THEN
    ALTER TABLE inventory ADD COLUMN company_id INT UNSIGNED NOT NULL DEFAULT 1 AFTER id;
    ALTER TABLE inventory ADD INDEX idx_inventory_company (company_id);
    UPDATE inventory SET company_id = 1 WHERE company_id IS NULL OR company_id = 0;
  END IF;

  -- sales
  IF NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='sales' AND COLUMN_NAME='company_id') THEN
    ALTER TABLE sales ADD COLUMN company_id INT UNSIGNED NOT NULL DEFAULT 1 AFTER id;
    ALTER TABLE sales ADD INDEX idx_sales_company (company_id);
    UPDATE sales SET company_id = 1 WHERE company_id IS NULL OR company_id = 0;
  END IF;

  -- accounts_receivable
  IF NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='accounts_receivable' AND COLUMN_NAME='company_id') THEN
    ALTER TABLE accounts_receivable ADD COLUMN company_id INT UNSIGNED NOT NULL DEFAULT 1 AFTER id;
    ALTER TABLE accounts_receivable ADD INDEX idx_ar_company (company_id);
    UPDATE accounts_receivable SET company_id = 1 WHERE company_id IS NULL OR company_id = 0;
  END IF;

  -- accounts_payable
  IF NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='accounts_payable' AND COLUMN_NAME='company_id') THEN
    ALTER TABLE accounts_payable ADD COLUMN company_id INT UNSIGNED NOT NULL DEFAULT 1 AFTER id;
    ALTER TABLE accounts_payable ADD INDEX idx_ap_company (company_id);
    UPDATE accounts_payable SET company_id = 1 WHERE company_id IS NULL OR company_id = 0;
  END IF;

  -- cash_register_sessions
  IF NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='cash_register_sessions' AND COLUMN_NAME='company_id') THEN
    ALTER TABLE cash_register_sessions ADD COLUMN company_id INT UNSIGNED NOT NULL DEFAULT 1 AFTER id;
    ALTER TABLE cash_register_sessions ADD INDEX idx_crs_company (company_id);
    UPDATE cash_register_sessions SET company_id = 1 WHERE company_id IS NULL OR company_id = 0;
  END IF;

  -- ── 3. Adicionar company_id na tabela users (FK para companies) ────────────
  IF NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='users' AND COLUMN_NAME='company_id') THEN
    ALTER TABLE users ADD COLUMN company_id INT UNSIGNED NOT NULL DEFAULT 1 AFTER id;
    ALTER TABLE users ADD INDEX idx_users_company (company_id);
    UPDATE users SET company_id = 1 WHERE company_id IS NULL OR company_id = 0;
  END IF;

  SELECT 'Migration multi-tenant concluída com sucesso.' AS resultado;

END //
DELIMITER ;

CALL migration_multitenant();
DROP PROCEDURE IF EXISTS migration_multitenant;
