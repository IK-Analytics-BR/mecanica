-- ============================================================
-- FIX_COLUNAS_FALTANTES.sql
-- Adiciona colunas faltantes identificadas nos erros
-- ============================================================

USE supply_chain_mecanica;

-- 1. Verificar e adicionar coluna sku na tabela products
SET @col_exists = (SELECT COUNT(*) FROM information_schema.columns 
                   WHERE table_schema = DATABASE() 
                   AND table_name = 'products' 
                   AND column_name = 'sku');

SET @sql = IF(@col_exists = 0, 
              'ALTER TABLE products ADD COLUMN sku VARCHAR(50) UNIQUE', 
              'SELECT "Coluna sku já existe em products"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 2. Verificar e adicionar coluna status_nfce na tabela sales
SET @col_exists = (SELECT COUNT(*) FROM information_schema.columns 
                   WHERE table_schema = DATABASE() 
                   AND table_name = 'sales' 
                   AND column_name = 'status_nfce');

SET @sql = IF(@col_exists = 0, 
              'ALTER TABLE sales ADD COLUMN status_nfce VARCHAR(20) DEFAULT NULL', 
              'SELECT "Coluna status_nfce já existe em sales"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 3. Verificar e adicionar coluna xml_nfce na tabela sales (usada em nfce_routes)
SET @col_exists = (SELECT COUNT(*) FROM information_schema.columns 
                   WHERE table_schema = DATABASE() 
                   AND table_name = 'sales' 
                   AND column_name = 'xml_nfce');

SET @sql = IF(@col_exists = 0, 
              'ALTER TABLE sales ADD COLUMN xml_nfce TEXT DEFAULT NULL', 
              'SELECT "Coluna xml_nfce já existe em sales"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 4. Verificar e adicionar coluna protocolo_nfce na tabela sales
SET @col_exists = (SELECT COUNT(*) FROM information_schema.columns 
                   WHERE table_schema = DATABASE() 
                   AND table_name = 'sales' 
                   AND column_name = 'protocolo_nfce');

SET @sql = IF(@col_exists = 0, 
              'ALTER TABLE sales ADD COLUMN protocolo_nfce VARCHAR(50) DEFAULT NULL', 
              'SELECT "Coluna protocolo_nfce já existe em sales"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 5. Verificar e adicionar coluna protocolo_nfe na tabela sales
SET @col_exists = (SELECT COUNT(*) FROM information_schema.columns 
                   WHERE table_schema = DATABASE() 
                   AND table_name = 'sales' 
                   AND column_name = 'protocolo_nfe');

SET @sql = IF(@col_exists = 0, 
              'ALTER TABLE sales ADD COLUMN protocolo_nfe VARCHAR(50) DEFAULT NULL', 
              'SELECT "Coluna protocolo_nfe já existe em sales"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 6. Verificar e adicionar coluna empresa_id na tabela sales
SET @col_exists = (SELECT COUNT(*) FROM information_schema.columns 
                   WHERE table_schema = DATABASE() 
                   AND table_name = 'sales' 
                   AND column_name = 'empresa_id');

SET @sql = IF(@col_exists = 0, 
              'ALTER TABLE sales ADD COLUMN empresa_id INT DEFAULT NULL', 
              'SELECT "Coluna empresa_id já existe em sales"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 7. Verificar e adicionar coluna xml_nfe na tabela sales
SET @col_exists = (SELECT COUNT(*) FROM information_schema.columns 
                   WHERE table_schema = DATABASE() 
                   AND table_name = 'sales' 
                   AND column_name = 'xml_nfe');

SET @sql = IF(@col_exists = 0, 
              'ALTER TABLE sales ADD COLUMN xml_nfe TEXT DEFAULT NULL', 
              'SELECT "Coluna xml_nfe já existe em sales"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT 'Colunas verificadas e adicionadas com sucesso!' AS resultado;
